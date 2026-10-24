import glob
import sys
import json
import os
import re
import time

import settings
import stages

GAME_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))

SLOT_COUNT = 3
SAVE_DIR = os.path.join(GAME_DIR, "save_data")          # the dedicated folder for every save file
AUTOSAVE_PATH = os.path.join(SAVE_DIR, "savegame.json")  # the autosave (start.py reads and writes it)


def ensureSaveDir():
    """Creates the save folder if it doesn't exist yet. False if it can't be created."""
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
    except OSError as err:
        print(f"[saves] couldn't create the save folder {SAVE_DIR}: {err}")
        return False
    return True


def moveOldSavesIntoSaveDir():
    """One-time tidy-up: save files from older versions (loose next to the game) move into save_data/.
    A file is never moved over one that already exists in the folder."""
    oldPaths = glob.glob(os.path.join(GAME_DIR, "savegame*.json"))
    if not oldPaths or not ensureSaveDir():
        return
    for oldPath in oldPaths:
        newPath = os.path.join(SAVE_DIR, os.path.basename(oldPath))
        if os.path.exists(newPath):
            continue
        try:
            os.replace(oldPath, newPath)
        except OSError as err:
            print(f"[saves] couldn't move {oldPath} into the save folder: {err}")


moveOldSavesIntoSaveDir()      # runs once, the first time anything imports this module


def _clean(text):
    return re.sub(r"[^A-Za-z0-9]+", "", str(text))


def resumePoint(progress):
    """(chapter, stage title) a save resumes at: the first chapter that isn't finished, at its first
    uncleared stage -- exactly where campaign.playChapter restarts after a load. (None, None) = all clear."""
    for name in stages.CHAPTER_ORDER:
        cleared = progress.get(name, 0)
        if cleared < stages.STAGES_PER_CHAPTER:
            return name, stages.getStage(name, cleared).get("title", f"Stage {cleared + 1}")
    return None, None


def slotFileName(slot, progress):
    chapter, stage = resumePoint(progress)
    if chapter is None:
        return f"savegame_slot{slot}_AllClear.json"
    return f"savegame_slot{slot}_{_clean(chapter)}_{_clean(stage)}.json"


def slotPaths(slot):
    """Every existing file belonging to this slot (the current name, plus any older name / legacy file)."""
    found = glob.glob(os.path.join(SAVE_DIR, f"savegame_slot{slot}_*.json"))
    legacy = os.path.join(SAVE_DIR, f"savegame_slot{slot}.json")
    if os.path.exists(legacy):
        found.append(legacy)
    return sorted(found, key=os.path.getmtime, reverse=True)     # newest first


def slotPath(slot):
    """The slot's current save file, or None if the slot is empty."""
    paths = slotPaths(slot)
    return paths[0] if paths else None


def readSlot(slot):
    """The slot's saved dict, or None if it's empty / unreadable."""
    path = slotPath(slot)
    if path is None:
        return None
    try:
        with open(path, "r") as saveFile:
            data = json.load(saveFile)
    except (OSError, ValueError) as err:
        print(f"[saves] couldn't read slot {slot}: {err}")
        return None
    return data if isinstance(data, dict) else None


def writeSlot(slot, extra=None):
    """Saves volume settings + stage progress (+ anything in `extra`) to the slot. True on success."""
    data = {
        "volume_settings": dict(settings.volume_settings),
        "stage_progress": stages.exportProgress(),
        "saved_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    data.update(extra or {})
    path = os.path.join(SAVE_DIR, slotFileName(slot, data["stage_progress"]))
    if not ensureSaveDir():
        return False
    try:
        with open(path + ".tmp", "w") as saveFile:
            json.dump(data, saveFile, indent=2)
        os.replace(path + ".tmp", path)      # never leaves a half-written slot behind
    except OSError as err:
        print(f"[saves] couldn't save slot {slot}: {err}")
        return False
    for oldSavePath in slotPaths(slot):              # the progress changed -> the name did too: drop the old file
        if os.path.abspath(oldSavePath) != os.path.abspath(path):
            try:
                os.remove(oldSavePath)
            except OSError:
                pass
    return True


def _summary(data):
    chapter, stage = resumePoint(data.get("stage_progress", {}))
    if chapter is None:
        return "All chapters cleared"
    return f"{chapter} - {stage}"


def slotInfo(slot):
    """None for an empty slot, else {"summary": ..., "time": ...} for the menu."""
    data = readSlot(slot)
    if data is None:
        return None
    return {"summary": _summary(data), "time": data.get("saved_at", "")}


def allSlotInfo():
    return [slotInfo(i) for i in range(1, SLOT_COUNT + 1)]