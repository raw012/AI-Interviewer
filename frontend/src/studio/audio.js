/** Interviewer speech playback with mouth-level metering, and microphone recording. */
import { api } from "./api";

let context;
function audioContext() {
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  if (!context) context = new Ctor();
  if (context.state === "suspended") context.resume().catch(() => {});
  return context;
}

/** Unlock audio on the first user gesture (required by mobile Safari). */
export function primeAudio() {
  audioContext();
  if (window.speechSynthesis) window.speechSynthesis.getVoices();
}

function meter(analyser, onLevel) {
  const data = new Uint8Array(analyser.fftSize);
  let frame;
  const tick = () => {
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    onLevel(Math.min(1, Math.sqrt(sum / data.length) * 4.5));
    frame = requestAnimationFrame(tick);
  };
  tick();
  return () => cancelAnimationFrame(frame);
}

function browserVoice(gender) {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  const english = voices.filter((v) => v.lang && v.lang.startsWith("en"));
  const wanted = gender === "male" ? /(daniel|alex|fred|male|guy|david|mark|aaron|arthur)/i : /(samantha|karen|female|zira|victoria|ava|allison|susan|serena|moira)/i;
  return english.find((v) => wanted.test(v.name)) || english.find((v) => /natural|premium|enhanced/i.test(v.name)) || english[0];
}

function speakWithBrowser(text, gender, onLevel, signal) {
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    if (!synth) { resolve(); return; }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = browserVoice(gender);
    if (voice) utterance.voice = voice;
    utterance.rate = 1.02;
    let timer;
    const stop = () => { clearInterval(timer); onLevel(0); resolve(); };
    utterance.onstart = () => {
      // No audio stream to meter: animate the mouth on a natural rhythm instead.
      timer = setInterval(() => onLevel(0.25 + Math.random() * 0.6), 110);
    };
    utterance.onboundary = () => onLevel(0.9);
    utterance.onend = stop;
    utterance.onerror = stop;
    signal?.addEventListener("abort", () => { synth.cancel(); stop(); });
    synth.speak(utterance);
  });
}

/**
 * Speak a line as the interviewer. Uses server TTS (persona voice) and falls back
 * to the device voice. Resolves when speech ends. `onLevel` gets 0..1 for lip-sync.
 */
export async function speak(text, { persona, voice, gender = "female", onLevel = () => {}, signal } = {}) {
  if (!text) return;
  if (voice !== "browser") {
    try {
      const response = await api.audio("/studio/speak", { text, persona, voice });
      const blob = await response.blob();
      if (signal?.aborted) return;
      await playBlob(blob, onLevel, signal);
      return;
    } catch (error) {
      if (signal?.aborted) return;
    }
  }
  await speakWithBrowser(text, gender, onLevel, signal);
}

function playBlob(blob, onLevel, signal) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    let stopMeter = () => {};
    const ctx = audioContext();
    if (ctx) {
      try {
        const source = ctx.createMediaElementSource(audio);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        source.connect(analyser);
        analyser.connect(ctx.destination);
        stopMeter = meter(analyser, onLevel);
      } catch { /* metering is optional */ }
    }
    const done = () => { stopMeter(); onLevel(0); URL.revokeObjectURL(url); resolve(); };
    audio.onended = done;
    audio.onerror = done;
    signal?.addEventListener("abort", () => { audio.pause(); done(); });
    audio.play().catch(done);
  });
}

/** Record from the microphone; returns a controller with stop() -> Blob. */
export async function startRecording(onLevel = () => {}) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  const mimeType = types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || "";
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  let stopMeter = () => {};
  const ctx = audioContext();
  if (ctx) {
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    stopMeter = meter(analyser, onLevel);
  }
  recorder.start(250);
  const startedAt = Date.now();
  return {
    startedAt,
    stop: () => new Promise((resolve) => {
      recorder.onstop = () => {
        stopMeter();
        onLevel(0);
        stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      };
      recorder.stop();
    }),
    cancel: () => {
      stopMeter();
      onLevel(0);
      try { recorder.stop(); } catch { /* already stopped */ }
      stream.getTracks().forEach((t) => t.stop());
    },
  };
}

export async function transcribe(blob) {
  const form = new FormData();
  const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", blob, `answer.${ext}`);
  const { text } = await api.upload("/studio/transcribe", form);
  return text;
}
