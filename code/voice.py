# ---------- Skill voice / sound effects ----------
# One folder per character, named exactly like the character, e.g.
#
#   assets/sounds/voice/Sandugo/1.mp3
#   assets/sounds/voice/Sandugo/2.mp3
#   assets/sounds/voice/Sandugo/3.mp3
#   assets/sounds/voice/Sandugo/ult.mp3
#
#   Every non-ult skill (attacks, buffs, heals AND dodge/block) -> a RANDOM pick from the numbered files.
#   Ult skills                                                  -> always  ult.mp3  (fixed voice).
#   Getting hurt (any hit that lands on the character)          -> a RANDOM pick from  hurt1.mp3, hurt2.mp3,
#                                                                  hurt3.mp3 ... (hurt_1 / hurt 1 / plain hurt.mp3 work too)
#
# Add as many numbered files as you want (4.mp3, 5.mp3, hurt4.mp3 ... gaps like 1, 2, 5 are fine too). The folder is
# re-checked whenever it changes, so new files are picked up even while the game is running.
# .mp3 / .ogg / .wav all work. Missing folder or file = silent. Volume = Master Volume x Voice Effects.
#
# Voices play on their own reserved channel (so they're never dropped by other sounds) and the music
# dips while a voice is talking, then eases back up.

import os
import random
import re

import pygame

import settings

VOICE_DIR = "assets/sounds/voice"
AUDIO_EXTS = (".mp3", ".ogg", ".wav")

# ---------- VOICE CONFIG -- edit this ----------
# Final loudness of a voice = Master Volume x Voice Effects (the sliders) x the numbers below (0.0 - 1.0+).
VOICE_CONFIG = {
    "skillVolume": 1.0,       # normal skills (attacks, buffs, heals, dodge/block)
    "ultVolume": 1.0,         # ult.mp3
    "hurtVolume": 0.8,        # hurt1.mp3, hurt2.mp3 ...
    "characters": {           # per-character settings -- explained below
        "Sandugo":  {"volume": 0.8, "ultVolume": 1.5},
        "Darit":    {"volume": 3.8, "ultVolume": 3.8, "hurtVolume": 4.0},
        "Otab":     {"volume": 4.8, "ultVolume": 5.8, "hurtVolume": 4.0},
        "Nanay Etha":    {"volume": 3.8, "ultVolume": 3.8, "hurtVolume": 4.0},
        "Yombits":     {"volume": 4.8, "ultVolume": 5.8, "hurtVolume": 4.0},
    },
    "duckLevel": 0.35,        # music sits at this fraction of its volume while a voice talks (1.0 = no ducking)
    "waitForVoices": True,    # battle holds the next action / round end until every voice line has finished
    "waitForHurt": True,      # ...and also waits for hurt grunts
    "maxBoost": 6.0,          # loudest a voice can be amplified past its file's own volume (1.0 = no boosting)
    "maxWaitMs": 6000,        # safety: never wait longer than this for one voice, even if the file is huge
}

# Per-character voice settings. Put an entry in VOICE_CONFIG["characters"] under the character's name; every key is
# optional and a missing key falls back to the global value above. Example:
#   skillVolume   replaces the global skillVolume for this character
#   ultVolume     replaces the global ultVolume for this character
#   hurtVolume    replaces the global hurtVolume for this character
#   muted         True = this character never speaks (and is never waited for)
#   wait          False = the battle doesn't hold actions for this character's voice
#   maxWaitMs     replaces the global maxWaitMs for this character
#   duck          replaces duckLevel while this character is talking
def _char(character):
    return VOICE_CONFIG["characters"].get(character, {})


# Music ducking: while a voice plays, the music sits at this fraction of its normal volume.
DUCK_LEVEL = VOICE_CONFIG["duckLevel"]
DUCK_ATTACK = 0.45      # how fast the music dips (per frame, 0..1)
DUCK_RELEASE = 0.06     # how fast it comes back up (slower = smoother)

# Getting hurt: the same sprite can't grunt again within this many milliseconds (multi-hit skills, DoT ticks).
HURT_COOLDOWN_MS = 450
HURT_CHANNELS = 3       # a few hurt voices can overlap (e.g. an AOE hitting three characters)

_HURT_RE = re.compile(r"^hurt[ _\-]*(\d*)$")

_cache = {}             # path -> pygame.mixer.Sound
_pools = {}             # character -> (folder mtime, {"random": [paths], "ult": path or None})
_state = {"channel": None, "hurtChannels": None, "hurtNext": 0, "level": 1.0, "waitSince": None,
          "speaker": None, "hurtSpeakers": {}}


def _scan(character):
    folder = os.path.join(VOICE_DIR, character)
    pool = {"random": [], "ult": None, "hurt": []}
    if not os.path.isdir(folder):
        return pool
    numbered = []
    hurt = []
    for fileName in os.listdir(folder):
        stem, ext = os.path.splitext(fileName)
        if ext.lower() not in AUDIO_EXTS:
            continue
        stem = stem.strip().lower()
        path = os.path.join(folder, fileName)
        hurtMatch = _HURT_RE.match(stem)
        if hurtMatch:
            hurt.append((int(hurtMatch.group(1) or 0), path))
        elif stem == "ult":
            pool["ult"] = path
        elif stem.isdigit():
            numbered.append((int(stem), path))
    pool["random"] = [p for _n, p in sorted(numbered)]      # 1, 2, 3, ... 10, 11 (any gaps are fine)
    pool["hurt"] = [p for _n, p in sorted(hurt)]
    return pool


def _poolFor(character):
    folder = os.path.join(VOICE_DIR, character)
    try:
        stamp = os.path.getmtime(folder)
    except OSError:
        stamp = None
    cached = _pools.get(character)
    if cached is None or cached[0] != stamp:
        cached = (stamp, _scan(character))
        _pools[character] = cached
    return cached[1]


def _volume(kind="skillVolume", character=None):
    v = settings.volume_settings
    base = v["Master Volume"] / 100 * v["Voice Effects"] / 100
    cfg = _char(character)
    trim = cfg.get(kind, VOICE_CONFIG.get(kind, 1.0)) * cfg.get("volume", 1.0)
    return max(0.0, base * trim)          # NOT clamped to 1.0 here: above 1.0 means "amplify the file" (see _load)


def _voiceChannel():
    if _state["channel"] is None:
        pygame.mixer.set_reserved(1 + HURT_CHANNELS)  # channels 0..N are only ever used for voices
        _state["channel"] = pygame.mixer.Channel(0)
        _state["hurtChannels"] = [pygame.mixer.Channel(1 + i) for i in range(HURT_CHANNELS)]
    return _state["channel"]


_boosted = {}           # (path, gain) -> amplified pygame.mixer.Sound
_warnedNoNumpy = [False]


def _amplified(path, gain):
    """A copy of the sound with its samples multiplied by `gain` (>1) and clipped. None if that isn't possible."""
    key = (path, round(gain, 2))
    if key in _boosted:
        return _boosted[key]
    sound = None
    try:
        import numpy as np
        arr = pygame.sndarray.array(_cache[path])
        if arr.dtype.kind == "i":
            info = np.iinfo(arr.dtype)
            out = np.clip(arr.astype(np.float32) * gain, info.min, info.max).astype(arr.dtype)
        else:
            out = np.clip(arr * gain, -1.0, 1.0).astype(arr.dtype)
        sound = pygame.sndarray.make_sound(np.ascontiguousarray(out))
    except Exception as err:           # no numpy / odd mixer format: fall back to normal (max 1.0) volume
        if not _warnedNoNumpy[0]:
            print(f"[voice] can't boost voices above 100% ({err})")
            _warnedNoNumpy[0] = True
    _boosted[key] = sound
    return sound


def _load(path, kind="skillVolume", character=None):
    if path not in _cache:
        _cache[path] = pygame.mixer.Sound(path)
    total = _volume(kind, character)
    sound = _cache[path]
    if total > 1.0 and VOICE_CONFIG.get("maxBoost", 1.0) > 1.0:
        boosted = _amplified(path, min(total, VOICE_CONFIG["maxBoost"]))
        if boosted is not None:
            sound = boosted
    sound.set_volume(min(1.0, total))
    return sound


def playSkillVoice(action):
    """Plays the voice for an action's skill. Only fires once per action."""
    if action.get("_voicePlayed"):
        return
    action["_voicePlayed"] = True
    if not pygame.mixer.get_init():
        return

    name = action["sprite"]["name"]
    if _char(name).get("muted"):
        return
    pool = _poolFor(name)
    isUlt = getattr(action["skillDef"], "icon", None) == "ult"
    if isUlt:
        path = pool["ult"]
    else:
        path = random.choice(pool["random"]) if pool["random"] else None
    if path is None:
        return
    try:
        _voiceChannel().play(_load(path, "ultVolume" if isUlt else "skillVolume", name))
        _state["waitSince"] = None
        _state["speaker"] = name
    except pygame.error as err:
        print(f"[voice] couldn't play {path}: {err}")


def playHurtVoice(sprite):
    """Plays a random 'hurt' voice for the sprite that just got hit (see triggerHitFlash in function.py)."""
    if not pygame.mixer.get_init():
        return
    if _char(sprite["name"]).get("muted"):
        return
    now = pygame.time.get_ticks()
    if now - sprite.get("_lastHurtVoice", -10_000) < HURT_COOLDOWN_MS:
        return
    pool = _poolFor(sprite["name"])
    if not pool["hurt"]:
        return
    sprite["_lastHurtVoice"] = now
    try:
        _voiceChannel()
        slot = _state["hurtNext"] % HURT_CHANNELS
        channel = _state["hurtChannels"][slot]
        _state["hurtSpeakers"][slot] = sprite["name"]
        _state["hurtNext"] += 1
        channel.play(_load(random.choice(pool["hurt"]), "hurtVolume", sprite["name"]))
        _state["waitSince"] = None
    except pygame.error as err:
        print(f"[voice] couldn't play a hurt voice: {err}")


# ---------- Waiting for voices ----------
def _speakers():
    """Names of the characters whose voice is playing right now (skill voice + hurt grunts)."""
    names = []
    if _state["channel"] is not None and _state["channel"].get_busy():
        names.append(_state["speaker"])
    if VOICE_CONFIG["waitForHurt"]:
        for slot, channel in enumerate(_state["hurtChannels"] or []):
            if channel.get_busy():
                names.append(_state["hurtSpeakers"].get(slot))
    return names


def voicesPlaying():
    """True while a voice line is still talking (battle_ui holds the next action until this is False).
    Characters with "wait": False are ignored. Gives up after maxWaitMs (global or per character) so a
    broken / very long file can never freeze the battle."""
    if not VOICE_CONFIG["waitForVoices"] or not pygame.mixer.get_init() or _state["channel"] is None:
        return False
    waited = [n for n in _speakers() if _char(n).get("wait", True)]
    if not waited:
        _state["waitSince"] = None
        return False
    now = pygame.time.get_ticks()
    if _state["waitSince"] is None:
        _state["waitSince"] = now
    limit = max(_char(n).get("maxWaitMs", VOICE_CONFIG["maxWaitMs"]) for n in waited)
    return now - _state["waitSince"] < limit


# ---------- Music ducking ----------
def updateVoiceDucking():
    """Call once per frame: dips the music while a voice is playing and eases it back afterwards."""
    if not pygame.mixer.get_init():
        return
    talking = _state["channel"] is not None and (
        _state["channel"].get_busy() or any(c.get_busy() for c in _state["hurtChannels"]))
    level = _state["level"]
    duck = DUCK_LEVEL
    if talking:
        duck = min([_char(n).get("duck", DUCK_LEVEL) for n in _speakers()] or [DUCK_LEVEL])
    target = duck if talking else 1.0
    if level == target:
        return
    rate = DUCK_ATTACK if talking else DUCK_RELEASE
    level += (target - level) * rate
    if abs(level - target) < 0.01:
        level = target
    _state["level"] = level

    master = settings.volume_settings["Master Volume"] / 100
    music = settings.volume_settings["Music Volume"] / 100
    pygame.mixer.music.set_volume(max(0.0, min(1.0, master * music * level)))


def resetVoiceDucking():
    """Puts the music back to its normal volume (call when leaving a battle)."""
    _state["level"] = 1.0
    settings.update_music_volume()