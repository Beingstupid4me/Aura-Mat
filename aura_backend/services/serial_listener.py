from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

import serial


class SerialListener:
    def __init__(
        self,
        port: str,
        baud_rate: int,
        timeout_sec: float,
        reconnect_sec: float,
        cooldown_sec: float,
        queue_max_size: int,
        poll_sleep_sec: float,
        on_tag: Callable[[str], None],
        on_stream_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._timeout_sec = timeout_sec
        self._reconnect_sec = reconnect_sec
        self._cooldown_sec = cooldown_sec
        self._queue_max_size = max(8, queue_max_size)
        self._poll_sleep_sec = max(0.001, poll_sleep_sec)
        self._on_tag = on_tag
        self._on_stream_event = on_stream_event
        self._logger = logger or logging.getLogger(__name__)

        self._stop_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._dispatcher_thread: Optional[threading.Thread] = None
        self._serial = None
        self._line_buffer = ""
        self._last_seen: Dict[str, float] = {}
        self._tag_queue: queue.Queue[str] = queue.Queue(maxsize=self._queue_max_size)

        self._stats_lock = threading.Lock()
        self._stats: Dict[str, int] = {
            "lines_read": 0,
            "tags_detected": 0,
            "tags_enqueued": 0,
            "queue_dropped": 0,
            "tags_dispatched": 0,
            "cooldown_filtered": 0,
        }
        self._last_queue_warning = 0.0

    def start(self) -> None:
        reader_alive = self._reader_thread and self._reader_thread.is_alive()
        dispatcher_alive = self._dispatcher_thread and self._dispatcher_thread.is_alive()
        if reader_alive or dispatcher_alive:
            return

        self._stop_event.clear()

        self._dispatcher_thread = threading.Thread(
            target=self._run_dispatcher,
            name="serial-dispatcher",
            daemon=True,
        )
        self._dispatcher_thread.start()

        self._reader_thread = threading.Thread(
            target=self._run_reader,
            name="serial-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass

        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)

        if self._dispatcher_thread and self._dispatcher_thread.is_alive():
            self._dispatcher_thread.join(timeout=2.0)

    def stats(self) -> Dict[str, int]:
        with self._stats_lock:
            snapshot = dict(self._stats)
        snapshot["queue_depth"] = self._tag_queue.qsize()
        snapshot["queue_capacity"] = self._queue_max_size
        return snapshot

    def _bump(self, key: str, amount: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + amount

    def _run_reader(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._serial = serial.Serial(
                    self._port,
                    self._baud_rate,
                    timeout=self._timeout_sec,
                )
                self._clear_serial_input_buffer()
                self._line_buffer = ""
                self._logger.info("Serial connected on %s @ %s", self._port, self._baud_rate)
                self._emit_stream_event(
                    {
                        "event": "serial_connected",
                        "message": f"Connected on {self._port} @ {self._baud_rate}",
                        "queue_depth": self._tag_queue.qsize(),
                    }
                )

                while not self._stop_event.is_set():
                    waiting = self._serial.in_waiting
                    if waiting <= 0:
                        time.sleep(self._poll_sleep_sec)
                        continue

                    raw = self._serial.read(waiting)
                    if not raw:
                        continue

                    self._ingest_raw_chunk(raw)

            except serial.SerialException as err:
                self._logger.warning("Serial unavailable (%s). Retrying in %.1fs", err, self._reconnect_sec)
                self._emit_stream_event(
                    {
                        "event": "serial_unavailable",
                        "message": str(err),
                        "queue_depth": self._tag_queue.qsize(),
                    }
                )
                time.sleep(self._reconnect_sec)
            except Exception:
                self._logger.exception("Serial listener crashed, retrying in %.1fs", self._reconnect_sec)
                self._emit_stream_event(
                    {
                        "event": "serial_reader_error",
                        "message": "Reader crashed; retrying.",
                        "queue_depth": self._tag_queue.qsize(),
                    }
                )
                time.sleep(self._reconnect_sec)
            finally:
                if self._serial is not None:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None

    def _clear_serial_input_buffer(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.reset_input_buffer()
        except Exception:
            try:
                self._serial.flushInput()
            except Exception:
                pass

    def _ingest_raw_chunk(self, raw_chunk: bytes) -> None:
        try:
            self._line_buffer += raw_chunk.decode("utf-8", errors="ignore")
        except Exception:
            return

        if "\n" not in self._line_buffer:
            return

        lines = self._line_buffer.split("\n")
        # Keep trailing partial line in the accumulator buffer.
        self._line_buffer = lines.pop()

        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                continue

            self._bump("lines_read")
            self._emit_stream_event(
                {
                    "event": "serial_line",
                    "line": clean_line,
                    "queue_depth": self._tag_queue.qsize(),
                }
            )

            tag_id = self._extract_tag_id(clean_line)
            if not tag_id:
                continue

            self._bump("tags_detected")
            self._emit_stream_event(
                {
                    "event": "tag_detected",
                    "tag_id": tag_id,
                    "queue_depth": self._tag_queue.qsize(),
                }
            )
            self._enqueue_tag(tag_id)

    def _enqueue_tag(self, tag_id: str) -> None:
        try:
            self._tag_queue.put_nowait(tag_id)
            self._bump("tags_enqueued")
            self._emit_stream_event(
                {
                    "event": "tag_enqueued",
                    "tag_id": tag_id,
                    "queue_depth": self._tag_queue.qsize(),
                }
            )
            return
        except queue.Full:
            self._bump("queue_dropped")

        # Drop oldest and enqueue newest to keep the stream moving.
        try:
            self._tag_queue.get_nowait()
            self._tag_queue.task_done()
        except queue.Empty:
            pass

        try:
            self._tag_queue.put_nowait(tag_id)
            self._bump("tags_enqueued")
            self._emit_stream_event(
                {
                    "event": "queue_drop_replace",
                    "tag_id": tag_id,
                    "queue_depth": self._tag_queue.qsize(),
                }
            )
        except queue.Full:
            self._bump("queue_dropped")

        now = time.monotonic()
        if now - self._last_queue_warning >= 5.0:
            self._last_queue_warning = now
            self._logger.warning(
                "Serial queue overflow. Increase AURA_SERIAL_QUEUE_MAX_SIZE if this continues."
            )

    def _run_dispatcher(self) -> None:
        while not self._stop_event.is_set() or not self._tag_queue.empty():
            try:
                tag_id = self._tag_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                if self._is_on_cooldown(tag_id):
                    self._bump("cooldown_filtered")
                    self._emit_stream_event(
                        {
                            "event": "tag_cooldown_filtered",
                            "tag_id": tag_id,
                            "queue_depth": self._tag_queue.qsize(),
                        }
                    )
                    continue

                self._on_tag(tag_id)
                self._bump("tags_dispatched")
                self._emit_stream_event(
                    {
                        "event": "tag_dispatched",
                        "tag_id": tag_id,
                        "queue_depth": self._tag_queue.qsize(),
                    }
                )
            except Exception:
                self._logger.exception("Error while dispatching queued serial tag")
                self._emit_stream_event(
                    {
                        "event": "serial_dispatch_error",
                        "message": "Failed while dispatching tag.",
                        "queue_depth": self._tag_queue.qsize(),
                    }
                )
            finally:
                self._tag_queue.task_done()

    def _emit_stream_event(self, payload: Dict[str, Any]) -> None:
        if not self._on_stream_event:
            return
        event_payload = dict(payload)
        event_payload["ts"] = time.time()
        try:
            self._on_stream_event(event_payload)
        except Exception:
            # Stream telemetry should never interrupt primary processing.
            pass

    def _extract_tag_id(self, line: str) -> str:
        if not line.startswith("TAG_ID:"):
            return ""
        raw_tag = line.split(":", 1)[1]
        return self._normalize_tag_id(raw_tag)

    @staticmethod
    def _normalize_tag_id(tag_id: str) -> str:
        return "".join(tag_id.strip().upper().split())

    def _is_on_cooldown(self, tag_id: str) -> bool:
        now = time.monotonic()
        last_seen = self._last_seen.get(tag_id)
        if last_seen is not None and (now - last_seen) < self._cooldown_sec:
            return True

        self._last_seen[tag_id] = now
        return False
