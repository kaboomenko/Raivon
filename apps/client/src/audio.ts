// Tiny procedural SFX (canon §16.4: CC0 + procedural synthesis). No assets needed.

let ctx: AudioContext | null = null;
let muted = false;

function ac(): AudioContext | null {
  if (muted) return null;
  if (!ctx) {
    const C = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!C) return null;
    ctx = new C();
  }
  if (ctx.state === 'suspended') void ctx.resume();
  return ctx;
}

export function unlockAudio(): void {
  ac();
}

export function setMuted(m: boolean): void {
  muted = m;
}

function tone(freq: number, dur: number, type: OscillatorType, gain: number, delay = 0, slideTo?: number): void {
  const a = ac();
  if (!a) return;
  const t = a.currentTime + delay;
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(gain, t + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(a.destination);
  o.start(t);
  o.stop(t + dur + 0.02);
}

function noise(dur: number, gain: number, delay = 0, lowpass = 1200): void {
  const a = ac();
  if (!a) return;
  const t = a.currentTime + delay;
  const buf = a.createBuffer(1, Math.floor(a.sampleRate * dur), a.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
  const src = a.createBufferSource();
  src.buffer = buf;
  const f = a.createBiquadFilter();
  f.type = 'lowpass';
  f.frequency.value = lowpass;
  const g = a.createGain();
  g.gain.value = gain;
  src.connect(f).connect(g).connect(a.destination);
  src.start(t);
}

// Major pentatonic steps for the rising «pop» scale of the ceremony.
const SCALE = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24, 26, 28];

export const sfx = {
  tap: () => tone(660, 0.06, 'triangle', 0.08),
  attack: () => {
    tone(220, 0.12, 'sawtooth', 0.06, 0, 140);
    noise(0.12, 0.08, 0, 2000);
  },
  capture: () => {
    tone(523, 0.1, 'triangle', 0.1);
    tone(784, 0.14, 'triangle', 0.08, 0.06);
  },
  repelled: () => tone(180, 0.2, 'square', 0.05, 0, 110),
  card: () => {
    tone(392, 0.08, 'triangle', 0.08);
    tone(587, 0.1, 'triangle', 0.07, 0.05);
  },
  airstrike: () => {
    tone(900, 0.5, 'sawtooth', 0.04, 0, 200);
    noise(0.6, 0.18, 0.45, 600);
  },
  seal: () => {
    noise(0.25, 0.3, 0, 300);
    tone(90, 0.3, 'sine', 0.3, 0, 50);
  },
  pop: (i: number) => {
    const semi = SCALE[Math.min(i, SCALE.length - 1)]!;
    tone(392 * Math.pow(2, semi / 12), 0.18, 'triangle', 0.09);
  },
  fanfare: () => {
    [0, 4, 7, 12].forEach((s, i) => tone(523 * Math.pow(2, s / 12), 0.35, 'triangle', 0.08, i * 0.09));
  },
  warn: () => tone(330, 0.25, 'square', 0.05, 0, 220),
};

export function vibrate(ms: number | number[]): void {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* not supported (iOS Safari) */
  }
}
