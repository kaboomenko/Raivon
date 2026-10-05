"""Procedural music for Raivon: a calm map theme and a driving battle theme (seamless loops).
Pads (detuned saws through a one-pole low-pass), a Karplus-Strong lute melody, frame drums and horn swells,
D dorian. Pure numpy, then ffmpeg → Ogg Vorbis.  Run: python3 tools/audio/make_music.py game/assets/audio"""
import os
import subprocess
import sys

import numpy as np

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else "game/assets/audio"
rng = np.random.default_rng(7)

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def freq(name: str) -> float:
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octave + 1) - 69) / 12)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # small arrays only (per note)
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def env(n, attack, release):
    e = np.ones(n)
    a = min(n, int(attack * SR))
    r = min(n - a, int(release * SR))
    if a > 0:
        e[:a] = np.linspace(0, 1, a)
    if r > 0:
        e[n - r:] = np.linspace(1, 0, r)
    return e


def pad(chord, dur, vol=0.12):
    """Warm pad: additive, 6 harmonics at 1/h², three slightly detuned voices (no aliasing, no buzz)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for note in chord:
        f = freq(note)
        for det in (-0.003, 0.0, 0.004):
            for h in range(1, 7):
                out += np.sin(2 * np.pi * f * (1 + det) * h * t + h) / h ** 2
    out /= len(chord) * 3 * 1.6
    trem = 1 + 0.06 * np.sin(2 * np.pi * 0.25 * t)
    return out * trem * env(n, 0.8, 1.0) * vol


def pluck(note, dur, vol=0.32, bright=0.996):
    n = int(dur * SR)
    f = freq(note)
    period = max(2, int(SR / f))
    buf = np.convolve(rng.uniform(-1, 1, period + 8), np.ones(8) / 8, mode="valid")[:period] * 2.0  # softer attack
    out = np.empty(n)
    for i in range(n):
        v = buf[i % period]
        out[i] = v
        buf[i % period] = bright * 0.5 * (v + buf[(i + 1) % period])
    return out * env(n, 0.002, 0.08) * vol


def horn(note, dur, vol=0.16):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq(note)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5 * t)
    x = sum(np.sin(2 * np.pi * f * h * vib * t) / h ** 1.3 for h in range(1, 7))
    return x * env(n, 0.25, 0.5) * vol / 2


def drum(dur, vol=0.5, low=70.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * low * t * (1 + 0.6 * np.exp(-t * 30))) * np.exp(-t * 9)
    skin = np.convolve(rng.uniform(-1, 1, n), np.ones(10) / 10, mode="same") * np.exp(-t * 40) * 0.6
    return (body + skin) * vol


def place(track, sig, at):
    i = int(at * SR)
    j = min(len(track), i + len(sig))
    track[i:j] += sig[: j - i]


def render(bpm, bars, chords, melody, drums, horns, pad_vol, pluck_vol):
    beat = 60.0 / bpm
    total = bars * 4 * beat
    n = int(total * SR)
    left = np.zeros(n + SR * 2)
    right = np.zeros(n + SR * 2)
    for b in range(bars):
        ch = chords[b % len(chords)]
        p = pad(ch, 4 * beat + 0.8, pad_vol)
        place(left, p, b * 4 * beat)
        place(right, p * 0.95, b * 4 * beat + 0.012)
    for (bar, step, note, length) in melody:
        s = pluck(note, length * beat + 0.4, pluck_vol)
        place(left, s * 0.8, (bar * 4 + step) * beat)
        place(right, s, (bar * 4 + step) * beat + 0.006)
    for (bar, step, v, low) in drums:
        d = drum(0.6, v, low)
        place(left, d, (bar * 4 + step) * beat)
        place(right, d, (bar * 4 + step) * beat)
    for (bar, note, length) in horns:
        h = horn(note, length * beat)
        place(left, h * 0.9, bar * 4 * beat)
        place(right, h, bar * 4 * beat + 0.01)
    # wrap the tail into the start so the loop is seamless
    for ch_ in (left, right):
        tail = ch_[n:].copy()
        ch_[: len(tail)] += tail
    st = np.stack([left[:n], right[:n]], axis=1)
    st /= max(1e-6, np.abs(st).max()) / 0.85
    return st


def write_ogg(st, name):
    raw = (st * 32767).astype("<i2").tobytes()
    path = os.path.join(OUT, name + ".ogg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "libvorbis", "-q:a", "3", path], input=raw, check=True)
    print(path, os.path.getsize(path) // 1024, "KB")


def map_theme():
    chords = [["D3", "A3", "F4"], ["C3", "G3", "E4"], ["A#2", "F3", "D4"], ["C3", "G3", "E4"],
              ["D3", "A3", "F4"], ["F3", "C4", "A4"], ["C3", "G3", "E4"], ["D3", "A3", "D4"]]
    phrase = [("D5", 1), ("E5", 0.5), ("F5", 0.5), ("A5", 1.5), ("G5", 0.5), ("F5", 1), ("E5", 1), ("C5", 1), ("D5", 1),
              ("E5", 0.5), ("F5", 0.5), ("G5", 1), ("F5", 0.5), ("E5", 0.5), ("D5", 2)]
    melody = []
    for rep, start_bar in ((0, 0), (1, 8)):
        pos = 0.0
        for note, ln in phrase:
            bar, step = divmod(pos, 4)
            n2 = note if rep == 0 else note.replace("5", "4") if note in ("A5", "G5") else note
            melody.append((start_bar + int(bar), step, n2, ln))
            pos += ln * 1.75
    # gentle arpeggio under the second half
    for b in range(8, 16):
        for k, nt in enumerate(["D4", "A4", "F4", "A4"]):
            melody.append((b, k, nt, 0.9))
    drums = [(b, s, 0.32 if s == 0 else 0.16, 62.0) for b in range(16) for s in (0, 2)]
    horns = [(0, "D4", 6), (8, "F4", 6), (12, "C4", 4)]
    return render(84, 16, chords, melody, drums, horns, 0.14, 0.26)


def battle_theme():
    chords = [["D3", "A3", "D4"], ["D3", "A3", "D4"], ["A#2", "F3", "D4"], ["C3", "G3", "E4"]]
    riff = ["D4", "D4", "F4", "D4", "G4", "F4", "E4", "C4"]
    melody = [(b, s * 0.5, riff[(s + b * 2) % len(riff)], 0.45) for b in range(8) for s in range(8)]
    drums = []
    for b in range(8):
        for s in range(4):
            drums.append((b, s, 0.55 if s % 2 == 0 else 0.3, 58.0 if s % 2 == 0 else 95.0))
            drums.append((b, s + 0.5, 0.14, 140.0))
    horns = [(0, "D4", 4), (2, "A#3", 4), (4, "D4", 4), (6, "C4", 4)]
    return render(128, 8, chords, melody, drums, horns, 0.12, 0.22)


os.makedirs(OUT, exist_ok=True)
write_ogg(map_theme(), "music_map")
write_ogg(battle_theme(), "music_battle")
