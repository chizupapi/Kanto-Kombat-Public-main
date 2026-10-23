# ---------- Stage configuration ----------
# Every chapter has three stages: "Stage 1", "Stage 2" and a "Boss". Edit CHAPTER_STAGES below.
#
# Stage keys:
#   title, kind ("stage" or "boss"), background, music (None keeps menu music)
#   musicFx   "boss" = distort/vary the music track for this stage (see campaign.bossMusicVersion)
#   players      three (x, y) spots for your team, in team order
#   playerScale  size of your team (default 1.0)
#   enemies      3 per stage (a boss stage may have 1): {"name": "SK", "x": 840, "y": 400}
#                "name" is a key of entities.CHARACTER; optional "scale" and "hpMult"
#                optional "ultChance": 0..1 = how often the AI even considers its ult when it's available (0.3 = 30%).
#                A boss with "ultChance" never loses sanity (casting its ult is free, and nothing can drain it). Instead a
#                sanity-draining skill (Otab's) locks its ult for the next round -- see classes.ULT_LOCK_ROUNDS.
#
# Coordinates are battle-scene pixels (1284 x 702): your team on the left, enemies on the right.

DEFAULT_BACKGROUND = "assets/img/test_bg.jpg"

DEFAULT_PLAYER_SLOTS = [(240, 400), (440, 400), (330, 500)]

STAGES_PER_CHAPTER = 3

# Your team is always 3, so the enemy side is 3 too (3v3).
ENEMIES_PER_FIGHT = 3
BOSS_ENEMIES_ALLOWED = (3, 1)

# Playable characters you start with.
UNLOCKED_CHARACTERS = ["Sandugo", "Darit", "Otab"]

# Story / unlock order.
CHAPTER_ORDER = ["Barangay", "City", "Province", "Country"]

# Characters that join the roster once a chapter becomes available (i.e. every earlier chapter is finished).
# Chapter 2 (City) brings Nanay Ehta and Yombits. Edit this to move or add unlocks.
CHAPTER_CHARACTER_UNLOCKS = {
    "City": ["Nanay Ehta", "Yombits"],
}


# Battlefield art lives in assets/img/battle/.
import os

BATTLE_BG_DIR = "assets/img/battle"

def _firstExisting(*names):
    paths = [f"{BATTLE_BG_DIR}/{fileName}" for fileName in names]
    for candidatePath in paths:
        if os.path.exists(candidatePath):
            return candidatePath
    return paths[0]

BATTLE_MUSIC_DIR = "assets/sounds/battlemusic"

def _firstExistingMusic(*stems):
    for stem in stems:
        for ext in (".mp3", ".ogg", ".wav"):
            path = f"{BATTLE_MUSIC_DIR}/{stem}{ext}"
            if os.path.exists(path):
                return path
    return None


def battleMusic(chapter):
    return _firstExistingMusic(f"{chapter}_Battle", chapter)


def bossMusic(chapter):
    return _firstExistingMusic(f"{chapter}_Boss", chapter)


def battleBg(chapter):
    return _firstExisting(f"{chapter} Battle.png", f"{chapter} Battle.png")


def bossBg(chapter):
    return _firstExisting(f"{chapter} Boss Battle.png", f"{chapter} Boss.png")


# ---------- THE CONFIG -- edit this ----------
CHAPTER_STAGES = {
    "Barangay": [
        {
            "title": "Stage 1", "kind": "stage",
            "background": battleBg("Barangay"), "music": battleMusic("Barangay"),
            "tutorial": True,                                   # guided tutorial overlay (see tutorial.py)
            "tutorialTeam": ["Sandugo", "Darit", "Otab"],       # fixed team for the walkthrough
            "playerScale": 1.15,
            "players": [(190, 500), (470, 500), (320, 590)],
            "enemies": [
                {"name": "Tanod", "x": 770, "y": 500, "scale": 1.2},
                {"name": "Tanod", "x": 1050, "y": 500, "scale": 1.2},
                {"name": "Tanod", "x": 940, "y": 590, "scale": 1.2},
            ],
        },
        {
            "title": "Stage 2", "kind": "stage",
            "background": battleBg("Barangay"), "music": battleMusic("Barangay"),
            "playerScale": 1.2,
            "players": [(190, 500), (470, 500), (320, 590)],
            "enemies": [
                {"name": "SK", "x": 770, "y": 500, "scale": 1.2},
                {"name": "SK", "x": 1050, "y": 500, "scale": 1.2},
                {"name": "SK", "x": 940, "y": 590, "scale": 1.2},
            ],
        },
        {
            "title": "Boss", "kind": "boss",
            "background": bossBg("Barangay"), "music": bossMusic("Barangay"), "musicFx": "boss",
            "playerScale": 1.2,
            "players": [(135, 535), (330, 535), (525, 535)],
            "enemies": [
                {"name": "BrgyCapt", "x": 950, "y": 535, "scale": 1.6, "ultChance": 0.3},
            ],
        },
    ],
    "City": [
        {
            "title": "Stage 1", "kind": "stage",
            "background": battleBg("City"), "music": battleMusic("City"),
            "playerScale": 1.2,
            "players": [(190, 505), (470, 505), (300, 595)],
            "enemies": [
                {"name": "YormeAss", "x": 770, "y": 505, "scale": 1.2},
                {"name": "YormeAss", "x": 1050, "y": 505, "scale": 1.2},
                {"name": "YormeAss", "x": 940, "y": 595, "scale": 1.2},
            ],
        },
        {
            "title": "Stage 2", "kind": "stage",
            "background": battleBg("City"), "music": battleMusic("City"),
            "playerScale": 1.2,
            "players": [(135, 565), (330, 565), (525, 565)],
            "enemies": [
                {"name": "Vice Yorme", "x": 715, "y": 565, "scale": 1.2},
                {"name": "Vice Yorme", "x": 910, "y": 565, "scale": 1.2},
                {"name": "Vice Yorme", "x": 1105, "y": 565, "scale": 1.2},
            ],
        },
        {
            "title": "Boss", "kind": "boss",
            "background": bossBg("City"), "music": bossMusic("City"), "musicFx": "boss",
            "playerScale": 1.2,
            "players": [(135, 535), (330, 535), (525, 535)],
            "enemies": [
                {"name": "Yorme", "x": 950, "y": 535, "scale": 1.6, "ultChance": 0.3},
            ],
        },
    ],
    "Province": [
        {
            "title": "Stage 1", "kind": "stage",
            "background": battleBg("Province"), "music": battleMusic("Province"),
            "playerScale": 1.25,
            "players": [(190, 500), (470, 500), (300, 590)],
            "enemies": [
                {"name": "SK", "x": 770, "y": 500, "scale": 1.25},
                {"name": "SK", "x": 1050, "y": 500, "scale": 1.25},
                {"name": "SK", "x": 940, "y": 590, "scale": 1.25},
            ],
        },
        {
            "title": "Stage 2", "kind": "stage",
            "background": battleBg("Province"), "music": battleMusic("Province"),
            "playerScale": 1.25,
            "players": [(135, 560), (330, 560), (525, 560)],
            "enemies": [
                {"name": "SK", "x": 715, "y": 560, "scale": 1.25},
                {"name": "SK", "x": 910, "y": 560, "scale": 1.25},
                {"name": "SK", "x": 1105, "y": 560, "scale": 1.25},
            ],
        },
        {
            "title": "Boss", "kind": "boss",
            "background": bossBg("Province"), "music": bossMusic("Province"), "musicFx": "boss",
            "playerScale": 1.25,
            "players": [(135, 535), (330, 535), (525, 535)],
            "enemies": [
                {"name": "SK", "x": 780, "y": 465},
                {"name": "SK", "x": 780, "y": 605},
                {"name": "SK", "x": 980, "y": 535, "scale": 1.7, "hpMult": 3.0, "ultChance": 0.3},
            ],
        },
    ],
    "Country": [
        {
            "title": "Stage 1", "kind": "stage",
            "background": battleBg("Country"), "music": battleMusic("Country"),
            "playerScale": 1.0,
            "players": [(190, 555), (470, 555), (300, 610)],
            "enemies": [
                {"name": "SK", "x": 770, "y": 555},
                {"name": "SK", "x": 1050, "y": 555},
                {"name": "SK", "x": 940, "y": 610},
            ],
        },
        {
            "title": "Stage 2", "kind": "stage",
            "background": battleBg("Country"), "music": battleMusic("Country"),
            "playerScale": 1.0,
            "players": [(135, 600), (330, 600), (525, 600)],
            "enemies": [
                {"name": "SK", "x": 715, "y": 600},
                {"name": "SK", "x": 910, "y": 600},
                {"name": "SK", "x": 1105, "y": 600},
            ],
        },
        {
            "title": "Boss", "kind": "boss",
            "background": bossBg("Country"), "music": bossMusic("Country"), "musicFx": "boss",
            "playerScale": 1.0,
            "players": [(135, 580), (330, 580), (525, 580)],
            "enemies": [
                {"name": "SK", "x": 780, "y": 535, "scale": 0.9},
                {"name": "SK", "x": 780, "y": 625, "scale": 0.9},
                {"name": "SK", "x": 980, "y": 580, "scale": 1.35, "hpMult": 3.0, "ultChance": 0.3},
            ],
        },
    ],
}


# ---------- Lookups ----------
def getStages(chapterName):
    return CHAPTER_STAGES[chapterName]


def getStage(chapterName, stageIndex):
    return CHAPTER_STAGES[chapterName][stageIndex]


def allEnemyNames():
    """Every character name used as an enemy in any stage (so the team-select roster can exclude them)."""
    return {enemyConfig["name"] for stages in CHAPTER_STAGES.values() for stageConfig in stages for enemyConfig in stageConfig["enemies"]}


def validateConfig(characterTable=None):
    """Raises ValueError on a malformed config."""
    for chapter in CHAPTER_ORDER:
        if chapter not in CHAPTER_STAGES:
            raise ValueError(f"CHAPTER_STAGES is missing chapter {chapter!r}")
        stages = CHAPTER_STAGES[chapter]
        if len(stages) != STAGES_PER_CHAPTER:
            raise ValueError(f"{chapter}: expected {STAGES_PER_CHAPTER} stages, got {len(stages)}")
        for stageIndex, stageConfig in enumerate(stages):
            where = f"{chapter} stage {stageIndex + 1}"
            if not stageConfig.get("enemies"):
                raise ValueError(f"{where}: needs at least one enemy")
            allowed = BOSS_ENEMIES_ALLOWED if stageConfig.get("kind") == "boss" else (ENEMIES_PER_FIGHT,)
            if len(stageConfig["enemies"]) not in allowed:
                raise ValueError(
                    f"{where}: {len(stageConfig['enemies'])} enemies, but a "
                    f"{'boss' if stageConfig.get('kind') == 'boss' else 'normal'} stage must have "
                    f"{' or '.join(map(str, allowed))} (fights are 3v3, boss may be 3v1)")
            players = stageConfig.get("players", DEFAULT_PLAYER_SLOTS)
            if len(players) < 3:
                raise ValueError(f"{where}: 'players' needs 3 (x, y) slots")
            for enemyConfig in stageConfig["enemies"]:
                if characterTable is not None and enemyConfig["name"] not in characterTable:
                    raise ValueError(f"{where}: unknown enemy {enemyConfig['name']!r}")


# ---------- Battle layout builder ----------
def buildBattleLayout(stage, team):
    """Turns a stage config + the chosen 3-name team into the flat layout list battle_ui spawns sprites from."""
    # Team-select cards run left to right, so hand out the spots left to right too: card 1 -> leftmost spot,
    # card 2 -> middle, card 3 -> rightmost (a triangle formation no longer puts the third card up front).
    slots = sorted(stage.get("players", DEFAULT_PLAYER_SLOTS), key=lambda pos: pos[0])
    layout = [
        {"name": name, "x": x, "y": y, "side": "left"}
        for name, (x, y) in zip(team, slots)
    ]
    if stage.get("playerScale", 1) != 1:
        for entry in layout:
            entry["scale"] = stage["playerScale"]
    for enemyConfig in stage["enemies"]:
        entry = {"name": enemyConfig["name"], "x": enemyConfig["x"], "y": enemyConfig["y"], "side": "right"}
        for key in ("hpMult", "scale", "ultChance"):
            if key in enemyConfig:
                entry[key] = enemyConfig[key]
        layout.append(entry)
    return layout


# ---------- Progress ----------
_progress = {name: 0 for name in CHAPTER_ORDER}


def stagesCleared(chapterName):
    return _progress.get(chapterName, 0)


def isChapterCompleted(chapterName):
    return stagesCleared(chapterName) >= STAGES_PER_CHAPTER


def isChapterUnlocked(chapterName):
    """Same rule as the chapter screen: every earlier chapter (story order) must be completed."""
    story = CHAPTER_ORDER.index(chapterName)
    return all(isChapterCompleted(earlierChapterName) for earlierChapterName in CHAPTER_ORDER[:story])


def unlockedCharacters():
    """Starting characters + everyone a currently-unlocked chapter hands out (recomputed from progress each call)."""
    names = list(UNLOCKED_CHARACTERS)
    for chapter, joiners in CHAPTER_CHARACTER_UNLOCKS.items():
        if chapter in CHAPTER_ORDER and isChapterUnlocked(chapter):
            names += [characterName for characterName in joiners if characterName not in names]
    return names


def markStageCleared(chapterName, stageIndex):
    """Call on victory. Only advances progress if this was the next new stage."""
    if stageIndex == stagesCleared(chapterName):
        _progress[chapterName] = stageIndex + 1
        return True
    return False


def chapterCompletedList():
    """[bool, ...] in CHAPTER_ORDER -- drop-in for the old CHAPTER_COMPLETED."""
    return [isChapterCompleted(name) for name in CHAPTER_ORDER]


def exportProgress():
    return dict(_progress)


def importProgress(data):
    for name in CHAPTER_ORDER:
        value = data.get(name, 0) if isinstance(data, dict) else 0
        _progress[name] = max(0, min(STAGES_PER_CHAPTER, int(value)))