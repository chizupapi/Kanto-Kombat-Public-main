import math
import pygame

# ---------- Character (runtime stats + sprite) ----------
class Character:
    def __init__(self, name, hp, defense, sanity, image, scale = 1):
        self.owner = name
        self.maxHp = hp
        self.hp = hp
        self.defense = defense
        self.sanity = sanity
        self.stunned = False
        self.attackMult = 1.0
        loadedImage = pygame.image.load(image).convert_alpha()
        self.image = pygame.transform.scale(loadedImage, (loadedImage.get_width() * scale, loadedImage.get_height() * scale))
        self.rect = self.image.get_rect()

# ---------- Skill (queued runtime skill) ----------
class Skill:
    def __init__(self, name, speed, owner, damage = 0, effect = None):
        self.name = name
        self.speed = speed
        self.owner = owner
        self.damage = damage
        self.effect = effect
        self.target = None

# ---------- Target effect entry (TargetEffect) ----------
class TargetEffect:
    """One effect applied to a skill's TARGET(S) -- the enemy for a debuff/damage skill, an ally/self for a buff."""
    def __init__(self, effect, modifier = 1.0, duration = 0, requirement = None):
        self.effect = effect            # effect function, e.g. defenseDown
        self.modifier = modifier        # potency passed to `effect`
        self.duration = duration
        self.requirement = requirement

# ---------- Self effect entry (SelfEffect) ----------
class SelfEffect:
    """One effect applied to the CASTER of a skill."""
    def __init__(self, effect, modifier = 1.0, duration = 0, requirement = None):
        self.effect = effect            # effect function, e.g. attackUp
        self.modifier = modifier        # potency passed to `effect`
        self.duration = duration
        self.requirement = requirement  # optional callable(caster sprite) -> bool

# ---------- Skill definition (SkillDef) ----------
VALID_SKILL_KINDS = ("damage", "heal", "buff", "debuff")

class SkillDef:
    def __init__(self, name, speed, damage = 0, effect = None, icon = None, sanityCost = 0,
                 sanityRecover = 0, targetCount = 1, kind = "damage", effectModifier = 1.0,
                 effectDuration = 0, effectRequirement = None,
                 selfEffect = None, selfEffectModifier = 1.0, selfEffectDuration = 0,
                 selfEffectRequirement = None, selfEffects = None, effects = None, selfOnly = False):
        self.name = name
        self.speed = speed
        self.damage = damage
        self.effect = effect
        self.icon = icon
        self.sanityCost = sanityCost
        self.sanityRecover = sanityRecover
        if targetCount not in (1, 3):
            raise ValueError(f"SkillDef {name!r}: targetCount must be 1 or 3, got {targetCount!r}")
        self.targetCount = targetCount
        self.selfOnly = selfOnly    # True: the caster is always the target (no target click) -- self-heal / self-buff

        if kind not in VALID_SKILL_KINDS:
            raise ValueError(f"SkillDef {name!r}: kind must be one of {VALID_SKILL_KINDS}, got {kind!r}")
        self.kind = kind

        self.effectModifier = effectModifier
        self.effectDuration = effectDuration

        self.effectRequirement = effectRequirement

        self.selfEffect = selfEffect
        self.selfEffectModifier = selfEffectModifier   # potency passed to `selfEffect`, same
        self.selfEffectDuration = selfEffectDuration
        self.selfEffectRequirement = selfEffectRequirement   # optional callable(sprite) -> bool,

        # Dynamic list of self-effects.
        self.selfEffects = list(selfEffects) if selfEffects else []
        if selfEffect is not None:
            self.selfEffects.insert(0, SelfEffect(selfEffect, selfEffectModifier,
                                                  selfEffectDuration, selfEffectRequirement))

        # Same idea for the TARGET side: a dynamic list of TargetEffect entries.
        self.effects = list(effects) if effects else []
        if isinstance(effect, (list, tuple)):
            self.effects = list(effect) + self.effects
            effect = None
        if effect is not None:
            self.effects.insert(0, TargetEffect(effect, effectModifier,
                                                effectDuration, effectRequirement))

# ---------- Live status effect record (EffectDef) ----------
class EffectDef:
    """A LIVE status effect currently sitting on a sprite -- see sprite["statusEffects"] in function.py."""
    def __init__(self, name, apply, modifier, duration, kind = None, basis = None, amount = None):
        self.name = name
        self.apply = apply
        self.modifier = modifier
        self.duration = duration
        self.kind = kind
        self.basis = basis
        self.amount = amount
        self.fresh = True

# ---------- Effect functions and their reverts ----------
def attackUp(sprite, modifier):
    sprite["stats"].attackMult *= modifier
    print(sprite["stats"].owner + "'s attack rises!")

def _revertAttackUp(sprite, modifier):
    sprite["stats"].attackMult /= modifier

def attackDown(sprite, modifier):
    sprite["stats"].attackMult *= modifier
    print(sprite["stats"].owner + "'s attack falls!")

def _revertAttackDown(sprite, modifier):
    sprite["stats"].attackMult /= modifier

def defenseUp(sprite, modifier):
    sprite["stats"].defense *= modifier
    print(sprite["stats"].owner + "'s defense rises!")

def _revertDefenseUp(sprite, modifier):
    sprite["stats"].defense /= modifier

def defenseDown(sprite, modifier):
    sprite["stats"].defense *= modifier
    print(sprite["stats"].owner + "'s defense falls!")

def _revertDefenseDown(sprite, modifier):
    sprite["stats"].defense /= modifier

def hpUp(sprite, modifier):
    stats = sprite["stats"]
    stats.hp = min(stats.maxHp, stats.hp * modifier)
    print(stats.owner + "'s HP rises!")

def poison(sprite, modifier):
    # Percentage-based: `modifier` is the FRACTION of the victim's MAX HP lost each round.
    print(sprite["stats"].owner, "is poisoned!")

def _revertPoison(sprite, modifier):
    # Nothing to undo: poison never changed a stat, it only ticked HP away.
    pass

def _tickPoison(sprite, modifier):
    """One round's poison damage: `modifier` (a fraction) of max HP, ignoring defense."""
    stats = sprite["stats"]
    amount = stats.maxHp * modifier
    dealt = min(amount, stats.hp)
    stats.hp = max(0, stats.hp - amount)
    print(stats.owner, "takes poison damage!")
    return dealt

def bleed(sprite, modifier):
    # PERCENT-OF-DAMAGE bleed: in a skill.
    print(sprite["stats"].owner, "starts bleeding!")

def _revertBleed(sprite, modifier):
    # Nothing to undo: bleed never changed a stat, it only ticked HP away.
    pass

def _tickBleed(sprite, modifier):
    """One round's bleed damage."""
    stats = sprite["stats"]
    dealt = min(modifier, stats.hp)
    stats.hp = max(0, stats.hp - modifier)
    print(stats.owner, "bleeds!")
    return dealt

def stun(sprite, modifier):
    sprite["stats"].stunned = True
    print(sprite["stats"].owner, "is stunned!")

def _revertStun(sprite, modifier):
    sprite["stats"].stunned = False

# ---------- Sanity effects: instant + tick versions ----------

# A boss ("ultChance" in stages.py) resists sanity drains (half strength, with a floor -- see BOSS_DRAIN_FACTOR below),
# and a drain aimed at it (Otab's) also locks its ult for this many round-ends (2 = the boss's next round of decisions).
ULT_LOCK_ROUNDS = 2

# Sanity drains also work on a boss, but weaker: it loses BOSS_DRAIN_FACTOR of the drain (0.5 = half) and can't be
# drained below BOSS_SANITY_FLOOR. (Bosses regain sanity every 1-2 rounds -- see regenBossSanity in function.py.)
BOSS_DRAIN_FACTOR = 0.5
BOSS_SANITY_FLOOR = 0.25

def _changeSanity(sprite, amount):
    """Shifts sprite's sanity by `amount`, clamped to 0..1. Returns the change actually made."""
    before = sprite.get("sanity", 0.5)
    if amount < 0 and sprite.get("ultChance") is not None:
        # A boss: the drain still locks its ult, AND now bites at reduced strength, but never below the floor.
        sprite["ultLock"] = ULT_LOCK_ROUNDS
        drained = max(BOSS_SANITY_FLOOR, before + amount * BOSS_DRAIN_FACTOR)
        sprite["sanity"] = min(before, drained)     # never RAISES a boss that is already under the floor
        return sprite["sanity"] - before
    sprite["sanity"] = max(0, min(before + amount, 1))
    return sprite["sanity"] - before

def sanityUp(sprite, modifier):
    _changeSanity(sprite, modifier)
    print(sprite["stats"].owner + "'s sanity increases!")

def sanityDown(sprite, modifier):
    _changeSanity(sprite, -modifier)
    print(sprite["stats"].owner + "'s sanity drops!")

def sanityUpTick(sprite, modifier):
    # Landing it does nothing by itself.
    print(sprite["stats"].owner + " starts to calm down!")

def _revertSanityUpTick(sprite, modifier):
    pass

def _tickSanityUp(sprite, modifier):
    """One round of regen. Returns the sanity actually gained (not HP)."""
    gained = _changeSanity(sprite, modifier)
    print(sprite["stats"].owner + "'s sanity recovers!")
    return gained

def sanityDownTick(sprite, modifier):
    print(sprite["stats"].owner + " starts to unravel!")

def _revertSanityDownTick(sprite, modifier):
    pass

def _tickSanityDown(sprite, modifier):
    """One round of drain. Returns the (negative) sanity change actually made."""
    lost = _changeSanity(sprite, -modifier)
    print(sprite["stats"].owner + "'s sanity drains!")
    return lost

# ---------- Cleanse ----------
NEGATIVE_EFFECTS = {attackDown, defenseDown, stun, bleed, poison, sanityDownTick}

def cleanse(sprite, modifier = 1.0):
    """Removes (and reverts) every negative status effect on `sprite`."""
    removed = []
    remaining = []
    for entry in sprite.get("statusEffects", []):
        if entry.apply in NEGATIVE_EFFECTS:
            revert = EFFECT_REVERTS.get(entry.apply)
            if revert is not None:
                revert(sprite, entry.modifier)
            removed.append(entry)
        else:
            remaining.append(entry)
    sprite["statusEffects"] = remaining
    if removed:
        print(sprite["stats"].owner + " is cleansed!")
    else:
        print(sprite["stats"].owner + " has nothing to cleanse.")
    return removed

# ---------- Effect revert table ----------
EFFECT_REVERTS = {
    attackUp: _revertAttackUp,
    attackDown: _revertAttackDown,
    defenseUp: _revertDefenseUp,
    defenseDown: _revertDefenseDown,
    stun: _revertStun,
    bleed: _revertBleed,
    poison: _revertPoison,
    sanityUpTick: _revertSanityUpTick,
    sanityDownTick: _revertSanityDownTick,
}

# ---------- Delayed-countdown table ----------
EFFECT_COUNTDOWN_NEXT_ROUND = {
    attackUp,
    defenseUp,
    attackDown,
    defenseDown,
    stun,
}

# ---------- Effect tick table ----------
EFFECT_TICKS = {
    bleed: _tickBleed,     # flat HP per round
    poison: _tickPoison,   # % of max HP per round
    sanityUpTick: _tickSanityUp,
    sanityDownTick: _tickSanityDown,
}

EFFECT_PERCENT_OF_DAMAGE = {bleed}

# Tick effects whose tick changes SANITY rather than HP.
SANITY_TICK_EFFECTS = {sanityUpTick, sanityDownTick}

# ---------- Effect visual routing ----------
EFFECT_VISUAL_KIND = {
    attackUp: "buff",
    defenseUp: "buff",
    hpUp: "buff",
    sanityUp: "buff",
    sanityUpTick: "buff",
    attackDown: "debuff",
    defenseDown: "debuff",
    sanityDown: "debuff",
    sanityDownTick: "debuff",
    stun: "stun",
    cleanse: "cleanse",
    poison: "dot",
    bleed: "bleed",
}

# ---------- Effect strength (for overlapping timed effects) ----------
_MULTIPLIER_EFFECTS = {attackUp, attackDown, defenseUp, defenseDown}

def effectStrength(effectFn, modifier, basis = None):
    if effectFn in _MULTIPLIER_EFFECTS and modifier > 0:
        return abs(math.log(modifier))
    if effectFn in EFFECT_PERCENT_OF_DAMAGE and basis is not None:
        return abs(modifier * basis)   # the actual HP lost per round
    return abs(modifier)