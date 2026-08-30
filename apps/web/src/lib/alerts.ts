import type { ExtremeAlert, Signal } from "../types";

export function playSignalTone(signal: Signal): void {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  const ctx = new AudioContextClass();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = signal.direction === "buy" ? "sine" : "triangle";
  oscillator.frequency.value = signal.direction === "buy" ? 740 : 420;
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start();
  oscillator.stop(ctx.currentTime + 0.38);
}

export function speakSignal(signal: Signal): void {
  if (!("speechSynthesis" in window) || signal.direction === "hold") return;
  const utterance = new SpeechSynthesisUtterance(
    `${signal.symbol} ${signal.direction} signal. Confidence ${Math.round(signal.confidence * 100)} percent.`
  );
  utterance.rate = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

export function playExtremeAlert(alert: ExtremeAlert): void {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  const ctx = new AudioContextClass();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  const upper = alert.level === "upper_85";
  oscillator.type = upper ? "triangle" : "sine";
  oscillator.frequency.value = upper ? 420 : 740;
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.55);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start();
  oscillator.stop(ctx.currentTime + 0.58);
}

export function speakExtremeAlert(alert: ExtremeAlert): void {
  if (!("speechSynthesis" in window)) return;
  const level = alert.level === "upper_85" ? "85" : "15";
  const recommendation = alert.level === "upper_85" ? "sell watch" : "buy watch";
  const utterance = new SpeechSynthesisUtterance(
    `${alert.symbol} reached composite level ${level}. ${recommendation}. Score ${Math.round(alert.score)}.`
  );
  utterance.rate = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}
