# ---------- Shared settings ----------
# Volume sliders live here (not in start.py) so the in-battle pause menu and the main
# settings screen read and write the SAME dict. Importing start.py from battle code would
# re-run the whole main menu.

import json
import sys
import os
import pygame

GAME_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

volume_settings = {
    "Master Volume": 100,
    "Music Volume": 100,
    "Voice Effects": 100,
    "Play Speed": 100,
}
slider_order = ["Master Volume", "Music Volume", "Voice Effects", "Play Speed"]

# Other remembered choices (not sliders).
BATTLE_SPEEDS = (1.0, 1.5, 2.0)
preferences = {"battle_speed": 1.0}


# ---------- Remembering the settings between launches ----------
# Kept in their own file (settings.json), separate from the save slots: settings belong to the player,
# not to a particular save, so loading a slot doesn't change them.

def saveSettings():
    """Writes the sliders + battle speed to settings.json. True on success."""
    data = {"volume_settings": dict(volume_settings), "preferences": dict(preferences)}
    try:
        with open(SETTINGS_PATH + ".tmp", "w") as settingsFile:
            json.dump(data, settingsFile, indent=2)
        os.replace(SETTINGS_PATH + ".tmp", SETTINGS_PATH)     # never leaves a half-written file behind
    except OSError as err:
        print(f"[settings] couldn't save: {err}")
        return False
    return True


def loadSettings():
    """Applies settings.json if there is one. Unknown keys and bad values are ignored. True if a file was read."""
    try:
        with open(SETTINGS_PATH, "r") as settingsFile:
            data = json.load(settingsFile)
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    saved = data.get("volume_settings")
    if isinstance(saved, dict):
        for name in volume_settings:
            value = saved.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                volume_settings[name] = max(0, min(100, int(value)))
    prefs = data.get("preferences")
    if isinstance(prefs, dict) and prefs.get("battle_speed") in BATTLE_SPEEDS:
        preferences["battle_speed"] = float(prefs["battle_speed"])
    return True


loadSettings()      # runs once, the first time anything imports this module


def update_music_volume():
    """Scales music volume by both Master Volume and Music Volume sliders."""
    master = volume_settings["Master Volume"] / 100
    music = volume_settings["Music Volume"] / 100
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(max(0.0, min(1.0, master * music)))