import io
import os
import random
import re
import wave

import pygame

import settings

DEATH_DIR = "assets/sounds/death"  # folder checked for your own death sound recordings
AUDIO_EXTS = (".mp3", ".ogg", ".wav")  # file types accepted as recordings

DEATH_VOLUME = {"butterfly": 0.9, "moth": 0.9}      # per kind, 0.0 - 1.0
SYNTH_VARIANTS = 3  # how many slightly different synthesized takes are built per sound
SYNTH_RATE = 44100  # sample rate (Hz) of the synthesized sounds

FILE_NAMES = {"butterfly": "butterfly", "moth": "gamogamo"}  # sound kind -> file name to look for in DEATH_DIR (butterfly = players, moth = enemies)

_cache = {}        # kind -> (folder mtime, [pygame.mixer.Sound])


# ---------- Synthesis helpers ----------
def _bandNoise(sampleCount, sampleRate, lowHz, highHz, randomGenerator):
    """White noise keep only between `lo` and `hi` Hz (FFT filter)."""
    import numpy as np
    spectrum = np.fft.rfft(randomGenerator.standard_normal(sampleCount))
    frequencies = np.fft.rfftfreq(sampleCount, 1.0 / sampleRate)
    spectrum[(frequencies < lowHz) | (frequencies > highHz)] = 0
    filteredNoise = np.fft.irfft(spectrum, sampleCount)
    return filteredNoise / (np.max(np.abs(filteredNoise)) or 1.0)


def _fadeOut(sampleCount, sampleRate, fadeSeconds):
    import numpy as np
    fadeEnvelope = np.ones(sampleCount)
    fadeSamples = min(sampleCount, int(fadeSeconds * sampleRate))
    fadeEnvelope[sampleCount - fadeSamples:] = np.linspace(1.0, 0.0, fadeSamples) ** 2
    return fadeEnvelope


def _butterflySound(sampleRate, randomGenerator):
    """Rising glassy chimes (the soul lifting off), a soft falling sigh underneath and a fluttering breath of air."""
    import numpy as np
    durationSeconds = 1.25
    sampleCount = int(durationSeconds * sampleRate)
    timeSeconds = np.arange(sampleCount) / sampleRate
    mixedSound = np.zeros(sampleCount)

    notes = [1319, 1568, 1760, 2093, 2637]                  # E6 G6 A6 C7 E7
    noteStartTimes = [0.00, 0.12, 0.26, 0.42, 0.60]
    for noteFrequency, noteStartTime in zip(notes, noteStartTimes):
        noteStartTime += randomGenerator.uniform(-0.015, 0.015)
        noteFrequency *= randomGenerator.uniform(0.992, 1.008)
        timeSinceNoteStart = np.clip(timeSeconds - noteStartTime, 0, None)
        noteEnvelope = np.where(timeSeconds >= noteStartTime, np.exp(-timeSinceNoteStart * 5.0), 0.0) * np.minimum(1.0, timeSinceNoteStart * 400)
        mixedSound += 0.22 * noteEnvelope * (np.sin(2 * np.pi * noteFrequency * timeSeconds) + 0.25 * np.sin(2 * np.pi * 2 * noteFrequency * timeSeconds))

    sighPitch = 520 - 190 * (timeSeconds / durationSeconds)                           # a quiet falling "sigh"
    sighPhase = 2 * np.pi * np.cumsum(sighPitch) / sampleRate
    mixedSound += 0.16 * np.sin(sighPhase) * np.sin(np.pi * np.clip(timeSeconds / durationSeconds, 0, 1)) ** 1.5

    flutterPulse = (0.5 + 0.5 * np.sin(2 * np.pi * randomGenerator.uniform(8.0, 10.0) * timeSeconds)) ** 2
    mixedSound += 0.10 * _bandNoise(sampleCount, sampleRate, 2500, 7000, randomGenerator) * flutterPulse * np.sin(np.pi * np.clip(timeSeconds / durationSeconds, 0, 1))

    mixedSound *= _fadeOut(sampleCount, sampleRate, 0.30)
    return mixedSound


def _gamugamoSound(sampleRate, randomGenerator):
    """A muffled thud, then a dusty, jittery wing-rustle over a low buzz that sags and dies."""
    import numpy as np
    durationSeconds = 1.15
    sampleCount = int(durationSeconds * sampleRate)
    timeSeconds = np.arange(sampleCount) / sampleRate
    mixedSound = np.zeros(sampleCount)

    thudPitch = 95 - 50 * np.clip(timeSeconds / 0.15, 0, 1)               # body thump
    mixedSound += 0.55 * np.sin(2 * np.pi * np.cumsum(thudPitch) / sampleRate) * np.exp(-timeSeconds * 18)

    jitter = np.convolve(randomGenerator.standard_normal(sampleCount), np.ones(900) / 900, mode="same") * 6
    buzzPitch = 190 * (1 - 0.5 * timeSeconds / durationSeconds) * (1 + 0.04 * jitter)
    buzzPhase = 2 * np.pi * np.cumsum(buzzPitch) / sampleRate
    sawtoothBuzz = sum(np.sin(harmonic * buzzPhase) / harmonic for harmonic in range(1, 9))
    flapPulse = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * (34 + 4 * jitter) * np.cumsum(np.ones(sampleCount)) / sampleRate))
    mixedSound += 0.16 * sawtoothBuzz * flapPulse * np.minimum(1.0, timeSeconds * 30) * np.exp(-timeSeconds * 1.6)

    rustleSpeed = randomGenerator.uniform(26, 32)
    rustlePulse = (0.45 + 0.55 * np.abs(np.sin(np.pi * rustleSpeed * timeSeconds + 1.7 * jitter))) ** 1.5
    mixedSound += 0.30 * _bandNoise(sampleCount, sampleRate, 1200, 6500, randomGenerator) * rustlePulse * np.exp(-timeSeconds * 2.2) * np.minimum(1.0, timeSeconds * 60)

    crackleClicks = (randomGenerator.random(sampleCount) < 0.0009 * np.exp(-timeSeconds * 1.8)).astype(float)       # dry crackle
    mixedSound += 0.45 * np.convolve(crackleClicks * randomGenerator.choice([-1.0, 1.0], sampleCount), np.exp(-np.arange(220) / 30.0), mode="same")

    mixedSound *= _fadeOut(sampleCount, sampleRate, 0.25)
    return mixedSound


_SYNTH = {"butterfly": _butterflySound, "moth": _gamugamoSound}


def _toSound(samples, sampleRate):
    """float array -> pygame Sound (through an in-memory 16-bit WAV, so any mixer format works)."""
    import numpy as np
    peakLevel = float(np.max(np.abs(samples))) or 1.0
    pcm16Samples = np.ascontiguousarray((samples / peakLevel * 0.85 * 32767).astype("<i2"))
    wavBuffer = io.BytesIO()
    with wave.open(wavBuffer, "wb") as wavFile:
        wavFile.setnchannels(1)
        wavFile.setsampwidth(2)
        wavFile.setframerate(sampleRate)
        wavFile.writeframes(pcm16Samples.tobytes())
    wavBuffer.seek(0)
    return pygame.mixer.Sound(wavBuffer)


def synthesizeWav(kind, path, seed=0):
    """Writes the synthesized sound for `kind` ("butterfly" / "moth") to a .wav, so you can listen to it or edit it."""
    import numpy as np
    samples = _SYNTH[kind](SYNTH_RATE, np.random.default_rng(seed))
    pcm16Samples = np.ascontiguousarray((samples / (float(np.max(np.abs(samples))) or 1.0) * 0.85 * 32767).astype("<i2"))
    with wave.open(path, "wb") as wavFile:
        wavFile.setnchannels(1)
        wavFile.setsampwidth(2)
        wavFile.setframerate(SYNTH_RATE)
        wavFile.writeframes(pcm16Samples.tobytes())


# ---------- Finding / building the sounds ----------
def _fileSounds(kind):
    wantedStemPattern = re.compile(rf"^{FILE_NAMES[kind]}\d*$")
    loadedSounds = []
    if os.path.isdir(DEATH_DIR):
        for fileName in sorted(os.listdir(DEATH_DIR)):
            fileStem, fileExtension = os.path.splitext(fileName)
            if fileExtension.lower() not in AUDIO_EXTS:
                continue
            if wantedStemPattern.match(re.sub(r"[^a-z0-9]", "", fileStem.lower())):
                try:
                    loadedSounds.append(pygame.mixer.Sound(os.path.join(DEATH_DIR, fileName)))
                except pygame.error as err:
                    print(f"[deathsound] couldn't load {fileName}: {err}")
    return loadedSounds


def _synthSounds(kind):
    try:
        import numpy as np
        return [_toSound(_SYNTH[kind](SYNTH_RATE, np.random.default_rng(seed)), SYNTH_RATE)
                for seed in range(SYNTH_VARIANTS)]
    except Exception as err:         # no numpy / odd mixer: stay silent rather than crash the battle
        print(f"[deathsound] couldn't synthesize the {kind} sound ({err})")
        return []


def _soundsFor(kind):
    try:
        stamp = os.path.getmtime(DEATH_DIR)
    except OSError:
        stamp = None
    cached = _cache.get(kind)
    if cached is None or cached[0] != stamp:
        sounds = _fileSounds(kind) or _synthSounds(kind)
        cached = _cache[kind] = (stamp, sounds)
    return cached[1]


def warmUp():
    """Optional: build both sounds now (e.g. while a loading screen shows) so the first death never hitches."""
    if pygame.mixer.get_init():
        for kind in FILE_NAMES:
            _soundsFor(kind)


def playDeathSound(kind):
    """kind: "butterfly" (a player died) or "moth" (an enemy died)."""
    if kind not in FILE_NAMES or not pygame.mixer.get_init():
        return
    sounds = _soundsFor(kind)
    if not sounds:
        return
    volumeSliders = settings.volume_settings
    volume = volumeSliders["Master Volume"] / 100 * volumeSliders["Voice Effects"] / 100 * DEATH_VOLUME.get(kind, 1.0)
    sound = random.choice(sounds)
    sound.set_volume(max(0.0, min(1.0, volume)))
    try:
        sound.play()
    except pygame.error as err:
        print(f"[deathsound] couldn't play the {kind} sound: {err}")
