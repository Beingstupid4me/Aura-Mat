const statusText = document.getElementById("statusText");
const progressText = document.getElementById("progressText");
const slotsContainer = document.getElementById("slots");
const storyText = document.getElementById("storyText");
const transcriptText = document.getElementById("transcriptText");
const serialFeed = document.getElementById("serialFeed");
const serialMeta = document.getElementById("serialMeta");
const phaseTimeline = document.getElementById("phaseTimeline");
const turnStatus = document.getElementById("turnStatus");
const turnInputWrap = document.getElementById("turnInputWrap");
const turnPromptText = document.getElementById("turnPromptText");
const turnCountdown = document.getElementById("turnCountdown");
const errorText = document.getElementById("errorText");
const resetBtn = document.getElementById("resetBtn");
const simulateBtn = document.getElementById("simulateBtn");
const simTagInput = document.getElementById("simTag");

// Browser microphone controls
const startRecordBtn = document.getElementById("startRecordBtn");
const stopRecordBtn = document.getElementById("stopRecordBtn");
const manualTranscriptInput = document.getElementById("manualTranscriptInput");
const submitManualBtn = document.getElementById("submitManualBtn");
const audioVisualizer = document.getElementById("audioVisualizer");
const turnListenText = document.getElementById("turnListenText");

const MAX_SERIAL_ROWS = 120;
const TOTAL_PHASES = 4;
const TOTAL_TURNS = 3;

let lastSnapshot = {
  cards_needed: 3,
  scanned_cards: [],
  story: "",
  transcript: "",
  status: "idle",
  error: ""
};

let activePhase = 0;
let completedPhase = 0;
let listeningPhase = 0;
let listeningEndsAtMs = 0;
let countdownTimer = null;

// Browser microphone recording state
let mediaRecorder = null;
let audioChunks = [];
let currentTurnNumber = 0;
let isRecording = false;

function renderSlots(scannedCards, totalSlots) {
  slotsContainer.innerHTML = "";

  for (let i = 0; i < totalSlots; i += 1) {
    const card = scannedCards[i];
    const slot = document.createElement("div");
    slot.className = "slot";

    if (card) {
      slot.classList.add("filled");
      slot.textContent = card.label;
    } else {
      slot.textContent = `Slot ${i + 1}`;
    }

    slotsContainer.appendChild(slot);
  }
}

function render(snapshot) {
  lastSnapshot = snapshot;
  statusText.textContent = snapshot.status || "idle";
  progressText.textContent = `${snapshot.count || 0} / ${snapshot.cards_needed || 3}`;
  storyText.textContent = snapshot.story || "Waiting for tags...";
  transcriptText.textContent = snapshot.transcript || "";
  errorText.textContent = snapshot.error || "";
  renderSlots(snapshot.scanned_cards || [], snapshot.cards_needed || 3);
  syncTimelineFromStatus(snapshot.status || "idle");
}

function updateTurnStatus(text) {
  if (turnStatus) {
    turnStatus.textContent = text;
  }
}

function renderPhaseTimeline() {
  if (!phaseTimeline) {
    return;
  }

  const chips = phaseTimeline.querySelectorAll(".phase-chip");
  chips.forEach((chip) => {
    const phase = Number(chip.getAttribute("data-phase"));
    chip.classList.remove("done", "active", "listening");

    if (phase <= completedPhase) {
      chip.classList.add("done");
    }
    if (phase === activePhase) {
      chip.classList.add("active");
    }
    if (phase === listeningPhase) {
      chip.classList.add("listening");
    }
  });
}

function stopTurnCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function startTurnCountdown(timeoutSec) {
  stopTurnCountdown();
  listeningEndsAtMs = Date.now() + Math.max(1, timeoutSec) * 1000;

  const tick = () => {
    const remainingMs = listeningEndsAtMs - Date.now();
    const sec = Math.max(0, Math.ceil(remainingMs / 1000));
    if (turnCountdown) {
      turnCountdown.textContent = `${sec}s`;
    }
    if (remainingMs <= 0) {
      stopTurnCountdown();
    }
  };

  tick();
  countdownTimer = setInterval(tick, 250);
}

function showTurnInput(phase, timeoutSec, promptMessage) {
  listeningPhase = phase;
  completedPhase = Math.max(completedPhase, phase);
  activePhase = Math.min(phase + 1, TOTAL_PHASES);
  updateTurnStatus(`Turn ${Math.min(phase, TOTAL_TURNS)} / ${TOTAL_TURNS}`);

  if (turnPromptText) {
    turnPromptText.textContent = promptMessage || `Listening for turn ${phase}...`;
  }
  if (turnInputWrap) {
    turnInputWrap.classList.remove("hidden");
  }
  startTurnCountdown(timeoutSec || 30);
  renderPhaseTimeline();
}

function clearTurnInput() {
  listeningPhase = 0;
  stopTurnCountdown();
  if (turnInputWrap) {
    turnInputWrap.classList.add("hidden");
  }
  stopBrowserMicRecording();
  renderPhaseTimeline();
}

async function startBrowserMicRecording(turnNumber) {
  currentTurnNumber = turnNumber;
  audioChunks = [];
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    
    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      await sendAudioToBackend(audioBlob, turnNumber);
      // Stop all tracks
      stream.getTracks().forEach(track => track.stop());
    };
    
    mediaRecorder.start();
    isRecording = true;
    
    if (startRecordBtn) startRecordBtn.classList.add("hidden");
    if (stopRecordBtn) stopRecordBtn.classList.remove("hidden");
    if (turnListenText) turnListenText.textContent = "🎤 Recording...browser mic";
    
    startAudioVisualization(stream);
  } catch (error) {
    console.error("❌ Microphone access denied:", error);
    alert("Microphone access denied. Please allow microphone access or type your response manually.");
  }
}

function stopBrowserMicRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    if (startRecordBtn) startRecordBtn.classList.remove("hidden");
    if (stopRecordBtn) stopRecordBtn.classList.add("hidden");
    if (turnListenText) turnListenText.textContent = "Processing audio...";
  }
}

async function sendAudioToBackend(audioBlob, turnNumber) {
  try {
    // For now, we'll send the audio blob to the backend for transcription
    // The backend would typically use a speech-to-text service
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.wav");
    formData.append("turn", turnNumber);
    
    // First, let the user know we're processing
    if (turnListenText) turnListenText.textContent = "Transcribing...";
    
    // For now, just send a placeholder transcription
    // In a real implementation, you'd send to a speech-to-text API
    const transcribedText = `[Browser microphone audio from turn ${turnNumber}]`;
    await submitTurnInput(turnNumber, transcribedText, "browser-mic");
  } catch (error) {
    console.error("❌ Error sending audio to backend:", error);
    if (turnListenText) turnListenText.textContent = "Error processing audio";
  }
}

function startAudioVisualization(stream) {
  // Simple audio visualization using analyzer
  try {
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const draw = () => {
      if (!isRecording) return;
      
      requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);
      
      // Update visualizer
      audioVisualizer.innerHTML = "";
      const step = Math.floor(dataArray.length / 16);
      for (let i = 0; i < 16; i++) {
        const bar = document.createElement("div");
        bar.className = "audio-bar";
        const height = (dataArray[i * step] / 255) * 30 + 2;
        bar.style.height = height + "px";
        audioVisualizer.appendChild(bar);
      }
    };
    draw();
  } catch (error) {
    console.warn("Audio visualization not available:", error);
  }
}

async function submitTurnInput(turnNumber, text, source) {
  try {
    const response = await fetch("/api/submit-turn-input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        turn: turnNumber,
        text: text,
        source: source
      })
    });
    
    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
    
    const result = await response.json();
    console.log("✅ Turn input submitted:", result);
    if (turnListenText) turnListenText.textContent = "Response received ✓";
  } catch (error) {
    console.error("❌ Error submitting turn input:", error);
  }
}

function syncTimelineFromStatus(status) {
  if (status === "idle") {
    activePhase = 0;
    completedPhase = 0;
    clearTurnInput();
    updateTurnStatus("Turn 0 / 3");
    renderPhaseTimeline();
    return;
  }

  if (status === "complete") {
    completedPhase = TOTAL_PHASES;
    activePhase = 0;
    clearTurnInput();
    updateTurnStatus(`Turn ${TOTAL_TURNS} / ${TOTAL_TURNS}`);
    renderPhaseTimeline();
    return;
  }

  const match = status.match(/(generating|narrating|listening)_phase_(\d+)/);
  if (match) {
    const mode = match[1];
    const phase = Number(match[2]);

    if (mode === "generating" || mode === "narrating") {
      activePhase = phase;
      completedPhase = Math.max(completedPhase, phase - 1);
      renderPhaseTimeline();
      return;
    }

    if (mode === "listening") {
      completedPhase = Math.max(completedPhase, phase);
      activePhase = Math.min(phase + 1, TOTAL_PHASES);
      renderPhaseTimeline();
      return;
    }
  }
}

function formatSerialEvent(payload) {
  const eventName = payload.event || "event";
  const tag = payload.tag_id ? ` tag=${payload.tag_id}` : "";
  const line = payload.line ? ` ${payload.line}` : "";
  const message = payload.message ? ` ${payload.message}` : "";
  return `${eventName}${tag}${line}${message}`.trim();
}

function appendSerialRow(payload) {
  if (!serialFeed) {
    return;
  }

  const row = document.createElement("div");
  const eventName = payload.event || "event";
  const text = formatSerialEvent(payload);
  const ts = new Date((payload.ts || Date.now() / 1000) * 1000).toLocaleTimeString();

  row.className = "stream-row";
  if (eventName.includes("error") || eventName.includes("drop") || eventName.includes("unavailable")) {
    row.classList.add("warn");
  }
  row.textContent = `[${ts}] ${text}`;

  serialFeed.appendChild(row);
  serialFeed.scrollTop = serialFeed.scrollHeight;

  while (serialFeed.children.length > MAX_SERIAL_ROWS) {
    serialFeed.removeChild(serialFeed.firstChild);
  }

  if (serialMeta) {
    const depth = Number.isFinite(payload.queue_depth) ? payload.queue_depth : 0;
    serialMeta.textContent = `Queue: ${depth}`;
  }
}

async function fetchState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  render(data);
}

async function resetRound() {
  errorText.textContent = "";
  const res = await fetch("/api/reset", { method: "POST" });
  const data = await res.json();
  if (!data.ok) {
    errorText.textContent = "Failed to reset round.";
    return;
  }
  render(data.state);
}

async function simulateTag() {
  const tag = (simTagInput.value || "").trim().toUpperCase();
  if (!tag) {
    errorText.textContent = "Enter a tag ID before simulating.";
    return;
  }

  errorText.textContent = "";
  const res = await fetch("/api/simulate-tag", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_id: tag })
  });
  const data = await res.json();

  if (!data.ok) {
    errorText.textContent = data.error || "Simulation failed.";
    return;
  }

  simTagInput.value = "";
  render(data.state || lastSnapshot);
}

const socket = io();

socket.on("connect", () => {
  errorText.textContent = "";
});

socket.on("state_snapshot", (snapshot) => {
  render(snapshot);
});

socket.on("story_generated", (data) => {
  storyText.textContent = data.story || "";
});

socket.on("story_word", (data) => {
  transcriptText.textContent = data.transcript || "";
});

socket.on("backend_error", (payload) => {
  errorText.textContent = payload.message || "Unknown backend error.";
});

socket.on("unknown_tag", (payload) => {
  errorText.textContent = `Unknown tag: ${payload.tag_id}`;
});

socket.on("tag_ignored", (payload) => {
  errorText.textContent = payload.message || "Duplicate scan ignored.";
});

socket.on("serial_stream", (payload) => {
  appendSerialRow(payload || {});
});

socket.on("phase_event", (payload) => {
  appendSerialRow({
    event: `phase_${payload.phase}_${payload.event}`,
    message: "",
    ts: Date.now() / 1000,
    queue_depth: 0
  });

  const phase = Number(payload.phase || 0);
  const eventName = payload.event || "";
  if (eventName === "generating" || eventName === "narrating") {
    activePhase = phase;
    completedPhase = Math.max(completedPhase, phase - 1);
    renderPhaseTimeline();
  }
});

socket.on("mic_prompt", (payload) => {
  appendSerialRow({
    event: `mic_prompt_phase_${payload.phase}`,
    message: `timeout=${payload.timeout_sec}s`,
    ts: Date.now() / 1000,
    queue_depth: 0
  });

  const turnNumber = Number(payload.turn || 0);
  currentTurnNumber = turnNumber;
  showTurnInput(Number(payload.phase || 0), Number(payload.timeout_sec || 30), payload.message || "Recording from laptop microphone...");
});

socket.on("mic_result", (payload) => {
  appendSerialRow({
    event: payload.captured ? `mic_captured_phase_${payload.phase}` : `mic_timeout_phase_${payload.phase}`,
    message: payload.captured ? payload.text : (payload.message || "no speech captured"),
    ts: Date.now() / 1000,
    queue_depth: 0
  });

  const phase = Number(payload.phase || 0);
  completedPhase = Math.max(completedPhase, phase);
  activePhase = Math.min(phase + 1, TOTAL_PHASES);
  updateTurnStatus(`Turn ${Math.min(phase, TOTAL_TURNS)} / ${TOTAL_TURNS}`);
  clearTurnInput();
  renderPhaseTimeline();
});

resetBtn.addEventListener("click", resetRound);
simulateBtn.addEventListener("click", simulateTag);

simTagInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    simulateTag();
  }
});

// Browser microphone event listeners
startRecordBtn.addEventListener("click", () => {
  startBrowserMicRecording(currentTurnNumber);
});

stopRecordBtn.addEventListener("click", () => {
  stopBrowserMicRecording();
});

submitManualBtn.addEventListener("click", async () => {
  const text = manualTranscriptInput.value.trim();
  if (!text) {
    alert("Please enter some text or record audio.");
    return;
  }
  await submitTurnInput(currentTurnNumber, text, "browser-manual");
  manualTranscriptInput.value = "";
  submitManualBtn.classList.add("hidden");
});

manualTranscriptInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    const text = manualTranscriptInput.value.trim();
    if (text) {
      await submitTurnInput(currentTurnNumber, text, "browser-manual");
      manualTranscriptInput.value = "";
      submitManualBtn.classList.add("hidden");
    }
  }
});

manualTranscriptInput.addEventListener("input", () => {
  if (manualTranscriptInput.value.trim()) {
    submitManualBtn.classList.remove("hidden");
  } else {
    submitManualBtn.classList.add("hidden");
  }
});


renderPhaseTimeline();
fetchState();
