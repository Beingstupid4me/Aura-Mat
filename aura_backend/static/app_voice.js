const socket = io();

const headlineStatus = document.getElementById("headlineStatus");
const stagePill = document.getElementById("stagePill");
const cardsRow = document.getElementById("cardsRow");
const cardsCount = document.getElementById("cardsCount");
const phaseMeta = document.getElementById("phaseMeta");
const phaseItems = Array.from(document.querySelectorAll(".phase-item"));

const micWindow = document.getElementById("micWindow");
const micTurn = document.getElementById("micTurn");
const micCountdown = document.getElementById("micCountdown");

const dialogueStream = document.getElementById("dialogueStream");
const stepLog = document.getElementById("stepLog");

const resetBtn = document.getElementById("resetBtn");
const simulateBtn = document.getElementById("simulateBtn");
const simTagInput = document.getElementById("simTag");

const errorBox = document.getElementById("errorBox");
const debugStatus = document.getElementById("debugStatus");
const debugQueue = document.getElementById("debugQueue");
const serialFeed = document.getElementById("serialFeed");

const TOTAL_PHASES = 4;
const MAX_STEPS = 120;
const MAX_SERIAL_ROWS = 60;

let currentStatus = "idle";
let currentPhase = 0;
let listeningTurn = 0;
let micTimer = null;
let micDeadlineMs = 0;

function setStatusText(text) {
  headlineStatus.textContent = text;
}

function setStagePill(text, variant) {
  stagePill.textContent = text.toUpperCase();
  stagePill.style.background = variant === "warm" ? "var(--warm-soft)" : "var(--accent-soft)";
  stagePill.style.color = variant === "warm" ? "#6d3a23" : "var(--accent)";
}

function appendStep(entry) {
  const row = document.createElement("li");
  const phaseLabel = entry.phase ? `P${entry.phase}` : "";
  const turnLabel = entry.turn ? `T${entry.turn}` : "";
  const prefix = [phaseLabel, turnLabel].filter(Boolean).join(" ");

  row.innerHTML = `<strong>${entry.step || "step"}</strong>${prefix ? ` (${prefix})` : ""}: ${entry.message || ""}`;
  stepLog.appendChild(row);

  while (stepLog.children.length > MAX_STEPS) {
    stepLog.removeChild(stepLog.firstChild);
  }

  stepLog.scrollTop = stepLog.scrollHeight;
}

function appendDialogue(speaker, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${speaker}`;
  bubble.textContent = text;
  dialogueStream.appendChild(bubble);
  dialogueStream.scrollTop = dialogueStream.scrollHeight;
}

function renderCards(scannedCards, cardsNeeded) {
  cardsRow.innerHTML = "";
  for (let i = 0; i < cardsNeeded; i += 1) {
    const slot = document.createElement("div");
    slot.className = "card-slot";

    const card = scannedCards[i];
    if (card) {
      slot.classList.add("filled");
      slot.textContent = card.label;
    } else {
      slot.textContent = `Card ${i + 1}`;
    }

    cardsRow.appendChild(slot);
  }

  cardsCount.textContent = `${scannedCards.length} / ${cardsNeeded}`;
}

function parseStatus(status) {
  const result = {
    phase: 0,
    listeningTurn: 0,
    label: "Idle",
    message: "Ready. Tap 3 cards to begin.",
    variant: "cool",
  };

  if (!status || status === "idle") {
    return result;
  }

  if (status === "collecting") {
    result.label = "Collecting";
    result.message = "Collecting cards...";
    return result;
  }

  if (status === "complete") {
    result.phase = TOTAL_PHASES;
    result.label = "Complete";
    result.message = "Story completed. Reset to start a new round.";
    return result;
  }

  const phaseMatch = status.match(/phase_(\d+)/);
  const turnMatch = status.match(/turn_(\d+)/);

  if (phaseMatch) {
    result.phase = Number(phaseMatch[1]);
  }
  if (turnMatch) {
    result.listeningTurn = Number(turnMatch[1]);
    if (!result.phase) {
      result.phase = result.listeningTurn;
    }
  }

  if (status.startsWith("generating_phase_")) {
    result.label = "Generating";
    result.message = `Generating story text for phase ${result.phase}.`;
    return result;
  }

  if (status.startsWith("synthesizing_phase_")) {
    result.label = "Synthesizing";
    result.message = `Building audio for phase ${result.phase}.`;
    return result;
  }

  if (status.startsWith("narrating_phase_")) {
    result.label = "Playing";
    result.message = `Playing audio for phase ${result.phase}.`;
    result.variant = "warm";
    return result;
  }

  if (status.startsWith("listening_turn_")) {
    result.label = "Listening";
    result.message = `Listening to child input for turn ${result.listeningTurn}.`;
    result.variant = "warm";
    return result;
  }

  if (status === "error") {
    result.label = "Error";
    result.message = "Pipeline error. Check logs below.";
    result.variant = "warm";
    return result;
  }

  return result;
}

function renderPhaseTrack(phase, turn) {
  phaseMeta.textContent = `Phase ${phase} / ${TOTAL_PHASES}`;

  phaseItems.forEach((item) => {
    const itemPhase = Number(item.dataset.phase);
    item.classList.remove("done", "active", "listening");

    if (itemPhase < phase) {
      item.classList.add("done");
    } else if (itemPhase === phase) {
      item.classList.add("active");
    }

    if (turn > 0 && itemPhase === turn) {
      item.classList.add("listening");
    }
  });
}

function startMicCountdown(turn, timeoutSec) {
  stopMicCountdown();

  listeningTurn = turn;
  micTurn.textContent = String(turn);
  micWindow.classList.remove("hidden");

  micDeadlineMs = Date.now() + timeoutSec * 1000;
  const tick = () => {
    const remainingMs = micDeadlineMs - Date.now();
    const remaining = Math.max(0, Math.ceil(remainingMs / 1000));
    micCountdown.textContent = String(remaining);

    if (remainingMs <= 0) {
      stopMicCountdown();
    }
  };

  tick();
  micTimer = window.setInterval(tick, 250);
}

function stopMicCountdown() {
  if (micTimer) {
    window.clearInterval(micTimer);
    micTimer = null;
  }
  micWindow.classList.add("hidden");
  listeningTurn = 0;
}

function appendSerial(payload) {
  const row = document.createElement("div");
  row.className = "serial-row";

  const eventName = payload.event || "event";
  const line = payload.line ? ` ${payload.line}` : "";
  const tag = payload.tag_id ? ` tag=${payload.tag_id}` : "";
  row.textContent = `${eventName}${tag}${line}`.trim();

  serialFeed.appendChild(row);
  while (serialFeed.children.length > MAX_SERIAL_ROWS) {
    serialFeed.removeChild(serialFeed.firstChild);
  }

  serialFeed.scrollTop = serialFeed.scrollHeight;

  if (typeof payload.queue_depth === "number") {
    debugQueue.textContent = String(payload.queue_depth);
  }
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function applySnapshot(snapshot) {
  currentStatus = snapshot.status || "idle";
  debugStatus.textContent = currentStatus;

  renderCards(snapshot.scanned_cards || [], snapshot.cards_needed || 3);

  const parsed = parseStatus(currentStatus);
  currentPhase = parsed.phase;

  setStatusText(parsed.message);
  setStagePill(parsed.label, parsed.variant);
  renderPhaseTrack(parsed.phase, parsed.listeningTurn || listeningTurn);
}

socket.on("connect", () => {
  appendStep({ step: "socket_connected", message: "Connected to backend websocket." });
});

socket.on("disconnect", () => {
  appendStep({ step: "socket_disconnected", message: "Disconnected from backend websocket." });
});

socket.on("state_snapshot", (snapshot) => {
  applySnapshot(snapshot);
});

socket.on("pipeline_step", (payload) => {
  appendStep(payload);

  if (payload.step === "mic_listen_start") {
    const timeoutSec = Number(payload.timeout_sec || 30);
    const turn = Number(payload.turn || 1);
    startMicCountdown(turn, timeoutSec);
  }

  if (payload.step === "mic_listen_done") {
    stopMicCountdown();
  }
});

socket.on("dialogue_entry", (payload) => {
  appendDialogue(payload.speaker || "system", payload.text || "");
});

socket.on("tag_scanned", (payload) => {
  appendStep({ step: "tag_scanned", message: `Scanned ${payload.label || "tag"}.` });
});

socket.on("tag_ignored", (payload) => {
  appendStep({ step: "tag_ignored", message: payload.message || "Duplicate or extra tag ignored." });
});

socket.on("unknown_tag", (payload) => {
  appendStep({ step: "unknown_tag", message: payload.message || "Unknown tag." });
});

socket.on("mic_result", (payload) => {
  if (!payload.captured) {
    appendDialogue("system", "No speech detected in this listening window.");
  }
});

socket.on("serial_stream", (payload) => {
  appendSerial(payload);
});

socket.on("backend_error", (payload) => {
  const msg = payload.message || "Unknown backend error";
  showError(msg);
  appendStep({ step: "backend_error", message: msg });
});

resetBtn.addEventListener("click", async () => {
  clearError();
  try {
    const response = await fetch("/api/reset", { method: "POST" });
    const body = await response.json();
    if (!response.ok || !body.ok) {
      throw new Error(body.error || "Reset failed");
    }

    stopMicCountdown();
    dialogueStream.innerHTML = "";
    appendDialogue("system", "Round reset. Tap cards to start again.");
    appendStep({ step: "ui_reset", message: "Round reset requested from UI." });
  } catch (error) {
    showError(`Reset failed: ${error.message}`);
  }
});

simulateBtn.addEventListener("click", async () => {
  clearError();
  const tagId = simTagInput.value.trim();
  if (!tagId) {
    showError("Enter a tag ID first.");
    return;
  }

  try {
    const response = await fetch("/api/simulate-tag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag_id: tagId }),
    });

    const body = await response.json();
    if (!response.ok || !body.ok) {
      throw new Error(body.error || "Simulation failed");
    }

    simTagInput.value = "";
  } catch (error) {
    showError(`Simulate failed: ${error.message}`);
  }
});

window.addEventListener("DOMContentLoaded", async () => {
  appendDialogue("system", "Ready. Scan three cards to begin the turn-by-turn story.");

  try {
    const response = await fetch("/api/state");
    const snapshot = await response.json();
    applySnapshot(snapshot);
  } catch (error) {
    showError(`Failed to load initial state: ${error.message}`);
  }
});
