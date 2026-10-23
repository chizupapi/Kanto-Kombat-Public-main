#  This entry might have a bit to much text but bear with it.
#  This contains all the neccessary information for addition and modication of characters
#  ENTITIES -- every character (players AND enemies), their skills, and their animations

#  HOW TO ADD A CHARACTER
#    1. Add an entry to CHARACTER below (copy a similar one).
#    2. Put its idle frames in   assets/animations/<Key>/idle/idle_1.png, idle_2.png ...
#       and its skill frames in  assets/animations/<Key>/<folder>/<folder>_1.png ...  (folders listed in section D).
#    3. Add one SKILL_ANIMATIONS_CONFIG["<Key>"]["<icon>"].update({...}) block per skill icon (section E).
#    4. Players only: add the name to stages.UNLOCKED_CHARACTERS (or CHAPTER_CHARACTER_UNLOCKS).
#       Enemies only: use the key as "name" in stages.py.
#
# ----- A. CHARACTER ENTRY  (CHARACTER["Key"] = {...}) ----------------------------------------------------
#    "make"        builds the live Character: Character(displayName, hp, defense, sanity, image, scale)
#        displayName   name shown in the battle (the dict key is what stages.py refers to)
#        hp            max health
#        defense       damage taken is reduced by this fraction (0.5 = takes half; 1 = takes none)
#        sanity        starting sanity, 0..1 (0.5 = half bar)
#        image         first idle frame, also used on the team-select card
#        scale         sprite size multiplier (stages.py "scale" multiplies this again)
#    "skills"      list of SkillDef (section B). Enemies pick their moves from this list.
#    "buttonSlots" PLAYERS ONLY. 2 rows of 2 skill names = the 4 on-screen buttons. Top row = basic move + dodge/block,
#                  bottom row = second skill + ult. Names must match a SkillDef name above.
#
# ----- B. SKILLDEF  (SkillDef("name", speed=..., ...)) ---------------------------------------------------
#    name             the skill's name (must be unique inside one character)
#    speed            turn order: LOWER acts FIRST. Dodge/block ("dodge"/"block" icons) always act before everything.
#    damage           damage dealt (heal skills: HP restored; 0 = no damage)
#    icon             which button art + animation folder it uses: skill1, skill2, ult, heal, dodge, block
#    kind             "damage" (default), "heal", "buff" or "debuff" -- decides the popup/animation style and who can be targeted
#    targetCount      1 = one target (default), 3 = hits the whole side
#    selfOnly         True = the caster is always the target (no clicking a target)
#    sanityCost       sanity spent to use it, 0..1 (the ult usually costs the most)
#    sanityRecover    sanity gained when used (dodge/block usually give some back)
#    effects          list of TargetEffect(...) applied to the target(s) -- see section C
#    selfEffects      list of SelfEffect(...) applied to the caster -- see section C
#    effect=[...]     older spelling of effects=[...]; works the same
#
# ----- C. EFFECTS  (TargetEffect / SelfEffect = (effectFunction, modifier, duration=rounds)) ------------------
#    modifier means different things per effect; duration 0 (or left out) = happens once, instantly.
#      attackUp / attackDown      modifier = multiplier on damage dealt    (1.25 = +25%, 0.75 = -25%)
#      defenseUp / defenseDown    modifier = multiplier on defense          (1.25 = +25%, 0.75 = -25%)
#      hpUp                       modifier = multiplier on current HP
#      poison                     modifier = fraction of MAX HP lost every round (0.05 = 5%)
#      bleed                      modifier = HP lost every round (fixed number)
#      stun                       target skips its turn; modifier is ignored (use 1)
#      sanityUp / sanityDown      modifier = sanity added / removed once (0.1 = 10% of the bar)
#      sanityUpTick / sanityDownTick   same, but every round for `duration` rounds
#      cleanse                    removes all negative effects; modifier is ignored (use 1)
#    requirement=callable(sprite) -> bool  (optional) only apply the effect when this returns True.
#    Boss note: bosses resist sanity drains (see classes.BOSS_DRAIN_FACTOR) and a drain locks their ult.
#
# ----- D. SKILL ANIMATION FOLDERS  (icon -> folder under assets/animations/<Key>/) -------------------------
#      skill1 -> first     skill2 -> second     heal -> heal     ult -> ult     dodge -> dodge     block -> block
#      Frames are named  <folder>_1.png, <folder>_2.png ...   (ult expects 16 frames, the others 8 -- see SKILL_FRAME_COUNT)
#
# ----- E. SKILL ANIMATION SETTINGS  (SKILL_ANIMATIONS_CONFIG["Key"]["icon"].update({...})) ----------------
#    category      how the effect moves:
#                    "direct"      plays right on the target
#                    "projectile"  flies from the caster to the target
#                    "charge"      the caster runs up to the target, hits, and runs back
#                    "replace_idle" (dodge) the caster's idle is swapped for the animation
#                    "envelop"     (block) plays over the caster, scaled by envelop_scale
#    -- timing (milliseconds) --
#    frame_time    how long each frame shows
#    hold_time     extra time the animation lingers (charge: lingers at the target)
#    travel_time   projectile only: flight time
#    impact_time   projectile: when damage lands | direct/charge: ms after the start (0 = use impact_frame)
#    impact_frame  direct/charge: which frame is the hit moment (0 = first frame)
#    ticks         how many times the damage number is split/applied over the animation (multi-hit look)
#    loop          False = play the frames once; True = keep cycling during the hold
#    count         number of frames to load (default 8)
#    -- size and position --
#    max_size      (width, height) the frames are shrunk to fit
#    scale         multiplies the frames' own size instead of using max_size
#    skillOffset   pixels the effect sits in front of the target (0 = centred on it)
#    charOffset    charge only: pixels in front of the target where the caster stops
#    splashEffect  False = no splash on the other targets of a 3-target skill
#    -- trail (projectile) --
#    trail         number of ghost copies behind the projectile
#    trail_gap     pixels between ghosts       trail_fade   ghost opacity falloff (0..1)
#    trail_shrink  size falloff per ghost (1 = no shrink)
#    -- motion defaults (SKILL_MOTION_CONFIG) --
#    drift         pixels the effect wobbles sideways    shake   pixels the effect jitters
#
# ----- F. OTHER TABLES IN THIS FILE ---------------------------------------------------------------------
#    EFFECTS                    lookup of effect functions by name (for tools / menus)
#    IDLE_ANIMATIONS_CONFIG     idle frame folder per character (built automatically from CHARACTER)
#    DODGE_BLOCK_CONFIG         shared animation settings for dodge and block
#    SKILL_MOTION_CONFIG        default drift / shake for skill1, skill2, ult
#    SKILL_FRAME_COUNT          frames per icon (default 8; ult 16)
#    BATTLE_LAYOUT              fallback starting positions when stages.py gives none

from classes import *

# ---------- Characters ----------

CHARACTER = {
    "Sandugo": {
        "make": lambda: Character(
            "Sandugo", hp=100, defense=0.50, sanity=0.5,
            image="assets/img/player/sandugoph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("ibalik", speed=1, damage=15, icon="skill1"),
            SkillDef("dinurog", speed=2, damage=0, icon="skill2", kind="buff", sanityCost=0.1,
                     effects=[
                         TargetEffect(attackUp, 1.25, duration=3),
                     ]),
            SkillDef("pinaikot", speed=4, damage=60, icon="ult", kind="damage", sanityCost=0.3,
                     selfEffects=[
                         SelfEffect(attackUp, 1.5, duration=3),
                     ]),
            SkillDef("ilag", speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["ibalik", "ilag"],
            ["dinurog", "pinaikot"],
        ],
    },
    "Darit": {
        "make": lambda: Character(
            "Darit", hp=80, defense=0.35, sanity=0.5,
            image="assets/img/player/daritph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("bato", speed=2, damage=35, icon="skill1",sanityRecover=0.1),
            SkillDef("bukol", speed=3, damage=55, icon="skill2", sanityCost=0.1, targetCount=3),
            SkillDef("pares", speed=4, damage=75, icon="ult", sanityCost=0.3, targetCount=3),
            SkillDef("kalasag", speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["bato", "kalasag"],
            ["bukol", "pares"],
        ],
    },
    "Otab": {
        "make": lambda: Character(
            "Otab", hp=90, defense=0.3, sanity=0.5,
            image="assets/img/player/otabph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("disapir", speed=1, damage=20, icon="skill1",
                     effects=[
                         TargetEffect(sanityDown, 0.3),
                     ]),
            SkillDef("apir", speed=2, damage=25, icon="skill2", sanityCost=0.1,
                     effects=[
                         TargetEffect(defenseDown, 0.75, duration=2),
                     ]),
            SkillDef("bulaga", speed=4, damage=100, icon="ult", sanityCost=0.2),
            SkillDef("ilag", speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["disapir", "ilag"],
            ["apir", "bulaga"],
        ],
    },
    "Gulok": {
        "make": lambda: Character(
            "Gulok", hp=170, defense=0.5, sanity=0.5,
            image="assets/img/player/gulokph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("saksak", speed=1, damage=20, icon="skill1", kind="damage",
                     effects=[
                         TargetEffect(bleed, 0.25, duration=3)
                     ]),
            SkillDef("tigas", speed=3, damage=0, icon="skill2", kind="buff", sanityCost=0.2,
                     effects=[
                         TargetEffect(defenseUp, 1.25, duration=3),
                     ]),
            SkillDef("harang taga", speed=4, damage=50, icon="ult", kind="damage", sanityCost=0.4,
                     selfEffects=[
                         SelfEffect(defenseUp, 1.25, duration=3),
                     ],
                     effect=[
                         TargetEffect(bleed, 0.2, duration=3),
                     ]),
            SkillDef("kalasag", speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["saksak", "kalasag"],
            ["tigas", "harang taga"],
        ],
    },
    "Nanay Ehta": {
        "make": lambda: Character(
            "Nanay Ehta", hp=150, defense=0.5, sanity=0.5,
            image="assets/img/player/nanayehtaph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("talak", speed=2, damage=15, icon="skill1", kind="damage", targetCount=3,
                     effects=[
                         TargetEffect(sanityDown, 0.2)
                     ]),
            SkillDef("tulog na", speed=3, damage=20, icon="skill2", kind="damage", targetCount=3, sanityCost=0.2,
                     effect=[
                         TargetEffect(stun, 1, duration=1)
                     ]),
            SkillDef("bangis", speed=4,  damage=0, icon="ult", kind="buff", sanityCost=0.4,
                     effect=[
                         TargetEffect(attackUp, 1.50, duration=3),
                         TargetEffect(defenseUp, 1.50, duration=3),
                     ]),
            SkillDef("kalasag",   speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["talak", "kalasag"],
            ["tulog na", "bangis"],
        ],
    },
    "Popper": {
        "make": lambda: Character(
            "Popper", hp=120, defense=0.45, sanity=0.5,
            image="assets/img/player/popperph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("putok", speed=3, damage=10, icon="heal", kind="heal", sanityCost=0.15,
                     effect=[
                         TargetEffect(sanityUp, 0.1),
                     ]),
            SkillDef("pumalupot", speed=2, damage=35, icon="skill2", kind="damage", sanityCost=0.1,
                     effect=[
                         TargetEffect(stun, 1, duration=1),
                     ]),
            SkillDef("ibuka",  speed=4, damage=25, icon="ult", kind="heal", sanityCost=0.4,
                     effect=[
                         TargetEffect(attackUp, 1.25, duration=3),
                         TargetEffect(defenseUp, 1.25, duration=3),
                    ]),
            SkillDef("ilag",   speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["putok", "ilag"],
            ["pumalupot", "ibuka"],
        ],
    },
    "Sampaguita": {
        "make": lambda: Character(
            "Sampaguita", hp=90, defense=0.55, sanity=0.5,
            image="assets/img/player/sampaguitaph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("liwanag", speed=2, damage=20, icon="skill1", kind="damage",
                     effect=[
                         TargetEffect(stun, 1, duration=1),
                     ]),
            SkillDef("basbas",  speed=3, damage=25, icon="heal", kind="heal", targetCount=3, sanityCost=0.25,
                     effect=[
                         TargetEffect(cleanse, 1)
                     ]),
            SkillDef("gabay",  speed=4, damage=50, icon="ult", kind="heal", targetCount=3, sanityCost=0.5,
                     effect=[
                         TargetEffect(defenseUp, 1.25, duration=3),
                         TargetEffect(sanityUpTick, 0.10, duration=3),
                         TargetEffect(cleanse, 1),
                     ]),
            SkillDef("ilag",   speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["liwanag", "ilag"],
            ["basbas", "gabay"],
        ],
    },
    "Salmonega": {
        "make": lambda: Character(
            "Salmonega", hp=100, defense=0.5, sanity=0.5,
            image="assets/img/player/salmonegaph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("skill1", speed=2, damage=25, icon="skill1"),
            SkillDef("skill2", speed=3, damage=25, icon="skill2"),
            SkillDef("panis",  speed=4, damage=80, icon="ult", sanityCost=0.2),
            SkillDef("ilag",   speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["skill1", "ilag"],
            ["skill2", "panis"],
        ],
    },
    "Doflaminguard": {
        "make": lambda: Character(
            "Doflaminguard", hp=100, defense=0.75, sanity=0.5,
            image="assets/img/player/doflaminguardph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("skill1", speed=3, damage=20, icon="skill1"),
            SkillDef("skill2", speed=2, damage=25, icon="skill2"),
            SkillDef("kaltok", speed=4, damage=60, icon="ult", sanityCost=0.2),
            SkillDef("ilag",   speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["skill1", "ilag"],
            ["skill2", "kaltok"],
        ],
    },
    "Por": {
        "make": lambda: Character(
            "Por", hp=120, defense=1, sanity=0.5,
            image="assets/img/player/porph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("skill1",    speed=2, damage=15, icon="skill1"),
            SkillDef("skill2",    speed=2, damage=20, icon="skill2"),
            SkillDef("hinanakit", speed=4, damage=70, icon="ult", sanityCost=0.2),
            SkillDef("ilag",      speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["skill1", "ilag"],
            ["skill2", "hinanakit"],
        ],
    },
    "Yombits": {
        "make": lambda: Character(
            "Yombits", hp=110, defense=0.5, sanity=0.5,
            image="assets/img/player/yombitsph.png", scale=0.35,
        ),
        "skills": [
            SkillDef("day-old", speed=1, damage=25, icon="skill1",
                                 effects=[
                                     TargetEffect(defenseDown, 0.75),
                                 ]),
            SkillDef("sting",     speed=3, damage=15, icon="heal", kind="heal", sanityCost=0.2, selfOnly=True,
                     effects=[
                         TargetEffect(attackUp, 1.50, duration=2),
                     ]),
            SkillDef("lalaki ako", speed=4, damage=120, icon="ult", sanityCost=0.3),
            SkillDef("ilag",       speed=1, damage=0,  icon="dodge", sanityRecover=0.15),
        ],
        "buttonSlots": [
            ["day-old", "ilag"],
            ["sting", "lalaki ako"],
        ],
    },
        "Tanod": {
        "make": lambda: Character(
            "Tanod", hp=100, defense=0.4, sanity=0.5,
            image="assets/animations/Tanod/idle/idle_1.png", scale=0.75,
        ),
        "skills": [
            SkillDef("batuta", speed=1, damage=18, icon="skill1"),
            SkillDef("sangga", speed=1, damage=0, icon="block", sanityRecover=0.1),
        ],
    },
        "SK": {
        "make": lambda: Character(
            "SK Kagawad", hp=150, defense=0.45, sanity=0.5,
            image="assets/animations/SK/idle/idle_1.png", scale=0.75,
        ),
        "skills": [
            SkillDef("walis",     speed=1, damage=20, icon="skill1"),
            SkillDef("ebas",     speed=2, damage=15, icon="skill2", kind="damage",  targetCount=3, sanityCost=0.2,
                     effects=[
                         TargetEffect(sanityDown, 0.025)
                     ]),
            SkillDef("kalasag",       speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
    },
        "BrgyCapt": {
        "make": lambda: Character(
            "Barangay Captain", hp=500, defense=0.65, sanity=0.5,
            image="assets/animations/BrgyCapt/idle/idle_1.png", scale=0.85,
        ),
        "skills": [
            SkillDef("inom",     speed=2, damage=25, icon="skill1"),
            SkillDef("balde",     speed=3, damage=15, icon="skill2", kind="damage", targetCount=3, sanityCost=0.25,
                     effects=[
                         TargetEffect(stun, 1),
                     ]),
            SkillDef("dribble",     speed=4, damage=40, icon="ult", kind="damage", targetCount=3, sanityCost=0.35,
                     effects=[
                         TargetEffect(defenseDown, 0.75, duration=3),
                         TargetEffect(sanityDown, 0.1, duration=3)
                     ]),
            SkillDef("kalasag",       speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
    },
        "YormeAss": {
        "make": lambda: Character(
            "Yorme Assisstant", hp=100, defense=0.4, sanity=0.5,
            image="assets/animations/Tanod/idle/idle_1.png", scale=0.75,
        ),
        "skills": [
            SkillDef("papeles", speed=1, damage=18, icon="skill1", targetCount=3,
                     effects=[
                        TargetEffect(sanityDown, 0.015)
                     ]),
            SkillDef("sangga", speed=1, damage=0, icon="block", sanityRecover=0.1),
        ],
    },
        "Vice Yorme": {
        "make": lambda: Character(
            "SK Kagawad", hp=150, defense=0.45, sanity=0.5,
            image="assets/animations/SK/idle/idle_1.png", scale=0.75,
        ),
        "skills": [
            SkillDef("bigas",     speed=1, damage=20, icon="skill1"),
            SkillDef("delata",     speed=2, damage=15, icon="skill2", kind="damage",  targetCount=3, sanityCost=0.2,
                     effects=[
                         TargetEffect(defenseDown, 0.65),
                         TargetEffect(bleed, 0.05, duration=2)
                     ]),
            SkillDef("kalasag",       speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
    },
        "Yorme": {
        "make": lambda: Character(
            "Yorme", hp=500, defense=0.65, sanity=0.5,
            image="assets/animations/BrgyCapt/idle/idle_1.png", scale=0.85,
        ),
        "skills": [
            SkillDef("inom",     speed=2, damage=25, icon="skill1"),
            SkillDef("balde",     speed=3, damage=15, icon="skill2", kind="damage", targetCount=3, sanityCost=0.25,
                     effects=[
                         TargetEffect(stun, 1),
                     ]),
            SkillDef("dribble",     speed=4, damage=40, icon="ult", kind="damage", targetCount=3, sanityCost=0.35,
                     effects=[
                         TargetEffect(defenseDown, 0.75, duration=3),
                         TargetEffect(sanityDown, 0.1, duration=3)
                     ]),
            SkillDef("kalasag",       speed=1, damage=0,  icon="block", sanityRecover=0.15),
        ],
    },
}

# ---------- Effects ----------
EFFECTS = {
    "buffs": {
        "attackUp": attackUp,
        "defenseUp": defenseUp,
        "hpUp": hpUp,
    },
    "dots": {
        "poison": poison,
        "bleed": bleed,
        "stun": stun,
    },
    "debuffs": {
        "attackDown": attackDown,
        "defenseDown": defenseDown,
    },
    "selfDebuffs": {
        "sanityDown": sanityDown,
    },
    "sanityInstant": {
        "sanityUp": sanityUp,
        "sanityDown": sanityDown,
    },
    "sanityTick": {
        "sanityUpTick": sanityUpTick,
        "sanityDownTick": sanityDownTick,
    },
}

# ---------- Idle animation ----------
IDLE_ANIMATIONS_CONFIG = {
    name: {
        "folder_path": f"assets/animations/{name}/idle",
        "prefix": "idle",
    }
    for name in CHARACTER
}

# ---------- Skill animations ----------
_ICON_TO_ANIMATION_FOLDER = {"skill1": "first", "skill2": "second", "heal": "heal", "ult": "ult", "dodge": "dodge", "block": "block"}

# Frames are expected at: assets/animations/<CharacterName>/<key>/<key>_1.png ...

# ---------- Dodge / block animation defaults ----------
DODGE_BLOCK_CONFIG = {
    "dodge": {
        "category": "replace_idle",
    },
    "block": {
        "category": "envelop",
        "envelop_scale": 1.6,
    },
}

# ---------- Skill motion defaults (drift / shake) ----------
SKILL_MOTION_CONFIG = {
    "skill1": {"drift": 4, "shake": 2},
    "skill2": {"drift": 4, "shake": 2},
    "ult":    {"drift": 8, "shake": 5},
}

# ---------- Skill frame counts ----------
SKILL_FRAME_COUNT = {
    "ult": 16,
}


# ---------- Per-character skill animation config ----------
SKILL_ANIMATIONS_CONFIG = {}
for characterName, characterEntry in CHARACTER.items():
    iconsUsedBySkills = {getattr(skill, "icon", None) for skill in characterEntry["skills"]} & _ICON_TO_ANIMATION_FOLDER.keys()
    if iconsUsedBySkills:
        SKILL_ANIMATIONS_CONFIG[characterName] = {
            icon: {
                "folder_path": f"assets/animations/{characterName}/{_ICON_TO_ANIMATION_FOLDER[icon]}",
                "prefix": _ICON_TO_ANIMATION_FOLDER[icon],
                "category": "direct",
                # DIRECT effects default to landing right on the target's own center.
                "skillOffset": 0,
                "charOffset": 0,
                # Damage fires at "impact_frame".
                "impact_frame": 0,
                "count": SKILL_FRAME_COUNT.get(icon, 8),
                **DODGE_BLOCK_CONFIG.get(icon, {}),
                **SKILL_MOTION_CONFIG.get(icon, {}),
            }
            for icon in iconsUsedBySkills
        }

# ---------- Sandugo ----------

SKILL_ANIMATIONS_CONFIG["Sandugo"]["skill1"].update({
    "category": "projectile",
    "travel_time": 500,
    "hold_time": 300,
    "impact_time": 450,
    "frame_time": 60,
    "max_size": (120, 120),
    "ticks": 3,
    "trail": 10,
    "trail_gap": 25,
    "trail_fade": 0.65,
})

SKILL_ANIMATIONS_CONFIG["Sandugo"]["skill2"].update({
    "category": "projectile",
    "travel_time": 500,
    "hold_time": 300,
    "impact_time": 450,
    "frame_time": 60,
    "max_size": (180, 180),
    "trail": 6,
    "trail_gap": 25,
    "trail_fade": 0.6,
    "trail_shrink": 0.9,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Sandugo"]["ult"].update({
    "category": "projectile",
    "travel_time": 500,
    "hold_time": 600,
    "impact_time": 450,
    "frame_time": 60,
    "max_size": (180, 180),
    "ticks": 15,
    "trail": 15,
    "trail_gap": 20,
    "trail_fade": 0.55,
    "trail_shrink": 0.88,
})

# ---------- Darit ----------

SKILL_ANIMATIONS_CONFIG["Darit"]["skill1"].update({
    "category": "direct",
    "hold_time": 300,
    "impact_frame": 0,
    "frame_time": 60,
    "max_size": (360, 360),
    "ticks": 5,
    "skillOffset": 0,
})

SKILL_ANIMATIONS_CONFIG["Darit"]["skill2"].update({
    "category": "direct",
    "impact_frame": 0,
    "frame_time": 80,
    "max_size": (260, 260),
    "ticks": 3,
    "skillOffset": 0,
})

SKILL_ANIMATIONS_CONFIG["Darit"]["ult"].update({
    "category": "direct",
    "hold_time": 20,
    "impact_frame": 3,
    "frame_time": 80,
    "max_size": (500, 500),
    "ticks": 6,
    "skillOffset": 0,
    "splashEffect": False,
    "loop": False,
})

# ---------- Otab ----------

SKILL_ANIMATIONS_CONFIG["Otab"]["skill1"].update({
    "category": "direct",
    "impact_frame": 50,
    "frame_time": 60,
    "max_size": (360, 360),
    "skillOffset": 0,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Otab"]["skill2"].update({
    "category": "projectile",
    "travel_time": 500,
    "impact_time": 600,
    "frame_time": 120,
    "max_size": (180, 180),
    "ticks": 2,
    "trail": 6,
    "trail_gap": 25,
    "trail_fade": 0.6,
    "trail_shrink": 0.9,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Otab"]["ult"].update({
    "category": "direct",
    "impact_time": 450,
    "frame_time": 180,
    "max_size": (180, 180),
    "ticks": 15,
    "skillOffset": 0,
    "loop": False,
})

# ---------- Gulok ----------

SKILL_ANIMATIONS_CONFIG["Gulok"]["skill1"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 400,
    "impact_time": 450,
    "frame_time": 120,
    "max_size": (120, 120),
    "charOffset": 120,
    "skillOffset": 120,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Gulok"]["skill2"].update({
    "category": "projectile",
    "travel_time": 300,
    "hold_time": 400,
    "impact_time": 450,
    "frame_time": 60,
    "max_size": (180, 180),
    "trail": 3,
    "trail_gap": 10,
    "trail_fade": 0.5,
    "trail_shrink": 0.9,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Gulok"]["ult"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 700,
    "impact_time": 250,
    "frame_time": 80,
    "max_size": (300, 300),
    "ticks": 13,
    "charOffset": 120,
    "skillOffset": 120,
})

# ---------- Nanay Ehta ----------

SKILL_ANIMATIONS_CONFIG["Nanay Ehta"]["skill1"].update({
    "category": "direct",
    "hold_time": 200,
    "impact_time": 0,
    "frame_time": 120,
    "max_size": (160, 160),
    "ticks": 3,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Nanay Ehta"]["skill2"].update({
    "category": "direct",
    "hold_time": 200,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (220, 220),
    "trail": 3,
    "trail_gap": 10,
    "trail_fade": 0.5,
    "trail_shrink": 0.9,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Nanay Ehta"]["ult"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 500,
    "impact_time": 250,
    "frame_time": 80,
    "max_size": (350, 350),
    "charOffset": 120,
    "skillOffset": 120,
})

# ---------- Popper ----------

SKILL_ANIMATIONS_CONFIG["Popper"]["heal"].update({
    "category": "direct",
    "hold_time": 350,
    "impact_time": 0,
    "frame_time": 120,
    "max_size": (250, 250),
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Popper"]["skill2"].update({
    "category": "direct",
    "hold_time": 350,
    "impact_time": 0,
    "frame_time": 120,
    "max_size": (300, 300),
    "ticks": 5,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Popper"]["ult"].update({
    "category": "direct",
    "hold_time": 500,
    "impact_time": 0,
    "frame_time": 160,
    "max_size": (650, 650),
    "ticks": 10,
    "splashEffect": False,
    "loop": False,
})

# ---------- Sampaguita ----------

SKILL_ANIMATIONS_CONFIG["Sampaguita"]["skill1"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 400,
    "impact_time": 450,
    "frame_time": 120,
    "max_size": (240, 240),
    "ticks": 5,
    "charOffset": 80,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Sampaguita"]["heal"].update({
    "category": "direct",
    "hold_time": 400,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (180, 180),
})

SKILL_ANIMATIONS_CONFIG["Sampaguita"]["ult"].update({
    "category": "direct",
    "travel_time": 500,
    "hold_time": 700,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (500, 500),
    "ticks": 15,
})

# ----------  Yombits ----------

SKILL_ANIMATIONS_CONFIG["Yombits"]["skill1"].update({
    "category": "projectile",
    "travel_time": 500,
    "impact_time": 600,
    "frame_time": 120,
    "max_size": (180, 180),
    "ticks": 2,
    "trail": 6,
    "trail_gap": 25,
    "trail_fade": 0.6,
    "trail_shrink": 0.9,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Yombits"]["heal"].update({
    "category": "direct",
    "impact_frame": 50,
    "frame_time": 60,
    "max_size": (360, 360),
    "skillOffset": 0,
    "loop": False,
})

SKILL_ANIMATIONS_CONFIG["Yombits"]["ult"].update({
    "category": "direct",
    "impact_time": 450,
    "frame_time": 180,
    "scale": 1.5,           # multiplies the native frame size; raise/lower to taste
    "ticks": 15,
    "skillOffset": 0,
    "loop": False,
})

# ---------- Tanod ----------

SKILL_ANIMATIONS_CONFIG["Tanod"]["skill1"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 300,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (300, 300),
    "charOffset": 120,
    "ticks": 2,
    "loop": False,
})

# ---------- SK ----------

SKILL_ANIMATIONS_CONFIG["SK"]["skill1"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 400,
    "impact_time": 0,
    "frame_time": 60,
    "max_size": (300, 300),
    "charOffset": 120,
    "ticks": 3,
})

SKILL_ANIMATIONS_CONFIG["SK"]["skill2"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 300,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (300, 300),
    "charOffset": 120,
    "ticks": 5,
    "loop": False,
})

# ---------- Barangay Captain ----------

SKILL_ANIMATIONS_CONFIG["BrgyCapt"]["skill1"].update({
    "category": "direct",
    "hold_time": 300,
    "impact_time": 0,
    "frame_time": 60,
    "max_size": (500, 500),
    "ticks": 15,
})

SKILL_ANIMATIONS_CONFIG["BrgyCapt"]["skill2"].update({
    "category": "charge",
    "travel_time": 500,
    "hold_time": 200,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (500, 500),
    "ticks": 3,
})

SKILL_ANIMATIONS_CONFIG["BrgyCapt"]["ult"].update({
    "category": "direct",
    "count": 8,
    "hold_time": 700,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (625, 625),
    "ticks": 5,
})

# ---------- YormeAss ----------

SKILL_ANIMATIONS_CONFIG["YormeAss"]["skill1"].update({
    "category": "direct",
    "hold_time": 300,
    "impact_time": 0,
    "frame_time": 80,
    "max_size": (250, 250),
    "ticks": 3,
    "loop": False,
})

# ---------- Battle layout ----------
BATTLE_LAYOUT = [
    {"name": "Sandugo", "x": 240, "y": 400, "side": "left"},
    {"name": "Darit", "x": 440, "y": 400, "side": "left"},
    {"name": "Otab", "x": 330, "y": 500, "side": "left"},
    {"name": "SK", "x": 840, "y": 400, "side": "right"},
    {"name": "SK", "x": 1040, "y": 400, "side": "right"},
    {"name": "SK", "x": 940, "y": 500, "side": "right"},
]