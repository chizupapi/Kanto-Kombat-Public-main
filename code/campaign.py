# ---------- Campaign flow ----------
# Chapter card -> team select -> Stage 1 -> Stage 2 -> Boss. Team select shows before every stage;
# losing a stage repeats it.

import os
import pygame

import saves
import stages
import tutorial


# Optional music for the Chapter 1 cutscenes. Missing file = silence (the menu music is faded out either way).
CUTSCENE_MUSIC = "assets/sounds/Chapter1_Cutscene.mp3"


_chapter1StoryShown = [False]     # True once the story has played for the current new game


def resetStory():
    """Called when a new game starts: the Chapter 1 story will play again."""
    _chapter1StoryShown[0] = False


def _playMusic(path):
    if path and os.path.exists(path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            return True
        except pygame.error as err:
            print(f"[campaign] couldn't play {path}: {err}")
    return False


# ---------- Boss music: distortion + variation ----------
# pygame can't distort music live, so the boss version of a chapter's track is rendered once (needs numpy,
# which pygame.sndarray needs anyway) into  <track>_bossfx.wav  next to the original, then played like any
# other music -- volume sliders, fades and looping all keep working. Delete the _bossfx.wav to rebuild it.
# What it does to the track:
#   - tape-wobble: slow pitch drift (about +-2%) that loops cleanly
#   - 30 Hz ring-mod growl, soft-clip overdrive, 6-bit bitcrush and a sample-rate-reduced layer, blended
#   - heartbeat pulse in the volume (1.2 Hz)
#   - glitch stutters: every ~9 s a 70 ms slice repeats 4 times
BOSS_FX_SUFFIX = "_bossfx"


def _distortTrack(audioSamples, sampleRate):
    """x: float32 (frames, channels) in -1..1  ->  the boss-fight version (same shape)."""
    import numpy as np

    frameCount, channelCount = audioSamples.shape
    durationSeconds = frameCount / sampleRate
    timeSeconds = np.arange(frameCount, dtype=np.float64) / sampleRate

    def cycles(targetHz):                       # a frequency with a whole number of cycles per loop -> no click at the loop point
        return max(1, round(targetHz * durationSeconds)) / durationSeconds

    frameIndices = np.arange(frameCount, dtype=np.float64)
    pitchWarpIndices = np.clip(frameIndices + 600 * np.sin(2 * np.pi * cycles(0.25) * timeSeconds), 0, frameCount - 1)
    ringModulation = np.sin(2 * np.pi * cycles(30) * timeSeconds).astype(np.float32)
    heartbeatPulse = (0.88 + 0.12 * np.sin(2 * np.pi * cycles(1.2) * timeSeconds)).astype(np.float32)
    overdriveAmount = 3.2
    stutterLengthFrames = int(0.07 * sampleRate)

    distortedSamples = np.empty_like(audioSamples)
    for channelIndex in range(channelCount):
        warpedChannel = np.interp(pitchWarpIndices, frameIndices, audioSamples[:, channelIndex]).astype(np.float32)
        warpedChannel *= 0.75 + 0.25 * ringModulation
        overdrivenChannel = np.tanh(overdriveAmount * warpedChannel) / np.tanh(overdriveAmount)
        bitcrushedChannel = np.round(overdrivenChannel * 24) / 24
        sampleHeldChannel = np.repeat(overdrivenChannel[::4], 4)[:frameCount]
        blendedChannel = 0.55 * overdrivenChannel + 0.25 * bitcrushedChannel + 0.20 * sampleHeldChannel
        blendedChannel *= heartbeatPulse
        for stutterStartSeconds in np.arange(5.0, durationSeconds - 1, 9.0):
            stutterStartFrame = int(stutterStartSeconds * sampleRate)
            if stutterStartFrame + 4 * stutterLengthFrames < frameCount:
                blendedChannel[stutterStartFrame:stutterStartFrame + 4 * stutterLengthFrames] = np.tile(blendedChannel[stutterStartFrame:stutterStartFrame + stutterLengthFrames], 4)
        distortedSamples[:, channelIndex] = blendedChannel

    # Keep it from getting much louder than the original.
    peakLevel = float(np.max(np.abs(distortedSamples))) or 1.0
    originalLoudness = float(np.sqrt(np.mean(audioSamples.astype(np.float64) ** 2))) or 1e-6
    distortedLoudness = float(np.sqrt(np.mean(distortedSamples.astype(np.float64) ** 2))) or 1e-6
    loudnessMatchGain = min(0.9 / peakLevel, 1.3 * originalLoudness / distortedLoudness)
    return np.clip(distortedSamples * loudnessMatchGain, -1.0, 1.0)


def bossMusicVersion(path):
    """The distorted boss version of `path` (built + cached on first use). Falls back to `path` on any problem."""
    if not path or not os.path.exists(path):
        return path
    trackPathWithoutExtension, _ext = os.path.splitext(path)
    if "_Boss" in os.path.basename(trackPathWithoutExtension) or trackPathWithoutExtension.endswith(BOSS_FX_SUFFIX):
        return path                      # a hand-made boss track: play it as is
    bossMusicPath = trackPathWithoutExtension + BOSS_FX_SUFFIX + ".wav"
    if os.path.exists(bossMusicPath) and os.path.getmtime(bossMusicPath) >= os.path.getmtime(path):
        return bossMusicPath
    try:
        import wave
        import numpy as np

        mixerSettings = pygame.mixer.get_init()
        if not mixerSettings:
            return path
        sampleRate, _fmt, _chans = mixerSettings
        rawSamples = pygame.sndarray.array(pygame.mixer.Sound(path))
        if rawSamples.dtype.kind == "i":
            floatSamples = rawSamples.astype(np.float32) / float(np.iinfo(rawSamples.dtype).max + 1)
        else:
            floatSamples = rawSamples.astype(np.float32)
        if floatSamples.ndim == 1:
            floatSamples = floatSamples[:, None]
        distortedSamples = _distortTrack(floatSamples, sampleRate)
        pcm16Samples = np.ascontiguousarray((distortedSamples * 32767).astype("<i2"))
        with wave.open(bossMusicPath + ".tmp", "wb") as wavFile:
            wavFile.setnchannels(pcm16Samples.shape[1])
            wavFile.setsampwidth(2)
            wavFile.setframerate(sampleRate)
            wavFile.writeframes(pcm16Samples.tobytes())
        os.replace(bossMusicPath + ".tmp", bossMusicPath)
        return bossMusicPath
    except Exception as err:             # no numpy, unreadable file, disk full...: just use the normal track
        print(f"[campaign] couldn't build the boss music ({err}); using {path}")
        return path


def playChapter(window, chapterName, background=None, menuMusic=None, onProgress=None,
                onSave=None, onLoad=None):
    """Plays a chapter from the first uncleared stage. Returns "back" (left or boss beaten), "menu" (quit from the pause menu) or "quit".
    onSave(slot)/onLoad(slot) are the battle's save/load icon handlers (each returns True/False)."""
    # Imported here: battle code loads assets, so the display must exist first.
    from battle_ui import runBattle, battleMusicState
    from entities import CHARACTER
    from voice import resetVoiceDucking

    stages.validateConfig(CHARACTER)

    index = stages.stagesCleared(chapterName)
    if index >= stages.STAGES_PER_CHAPTER:
        index = 0   # already finished: replay from the start

    while index < stages.STAGES_PER_CHAPTER:
        stage = stages.getStage(chapterName, index)

        # Every NEW game (Barangay Stage 1 with nothing cleared) opens with the Chapter 1 story, once per new game.
        if stages.stagesCleared(chapterName) > 0:
            _chapter1StoryShown[0] = False                      # progress exists -> the next new game may show it again
        if (index == 0 and stage.get("tutorial") and stages.stagesCleared(chapterName) == 0
                and not _chapter1StoryShown[0]):
            from Chapter1 import run_chapter1
            if pygame.mixer.get_init():
                pygame.mixer.music.fadeout(600)          # menu music stops for the cutscenes
            if os.path.exists(CUTSCENE_MUSIC):
                _playMusic(CUTSCENE_MUSIC)
            if run_chapter1(window, pygame.time.Clock()) is False:
                return "quit"                            # window closed mid-story: will replay next time
            _chapter1StoryShown[0] = True
            if not stage.get("music"):
                _playMusic(menuMusic)
        stageMusic = stage.get("music")
        if stage.get("musicFx") == "boss":
            stageMusic = bossMusicVersion(stageMusic)      # first boss fight: a short pause while it's built
        switchedMusic = _playMusic(stageMusic)

        # Team select (re-shown every stage) -> battle.
        battleMusicState["menuFaded"] = False
        result = runBattle(window, chapterName, index, onSave=onSave, onLoad=onLoad)
        resetVoiceDucking()      # never leave the music dipped after a battle

        if result == "victory_quit":
            # Window closed on the victory screen: the win still counts.
            if stages.markStageCleared(chapterName, index) and onProgress is not None:
                onProgress()
            return "quit"
        if result == "quit":
            return "quit"
        if switchedMusic or battleMusicState["menuFaded"]:
            _playMusic(menuMusic)
        if result == "load":
            # Progress was just reloaded from a save slot: carry on from wherever THAT save resumes, even when it
            # is in a different chapter than the one being played (otherwise the wrong stage would start).
            chapterToResume, _stageTitle = saves.resumePoint(stages.exportProgress())
            if chapterToResume is None:
                return "back"    # the loaded save has every chapter cleared: back to the chapter screen
            chapterName = chapterToResume
            index = stages.stagesCleared(chapterName)
            continue
        if result in ("back", "menu"):
            return result        # retreated / quit to main menu: progress so far is kept
        if result == "victory":
            if stages.markStageCleared(chapterName, index) and onProgress is not None:
                onProgress()
            index += 1           # next stage -> team select again

    return "back"