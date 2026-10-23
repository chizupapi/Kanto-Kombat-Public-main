import colorsys
import math
import os
import pygame
import random
import sys
from deathsound import playDeathSound
from function import FONT, DAMAGE_POPUP_FONT, COMBO_HITS_FONT, COMBO_TOTAL_FONT, drawCharacterGlow, drawCharacterShadow, clashWinner

# ---------- Animation type constants ----------
ATTACK = "attack"
SKILL1 = "skill1"
SKILL2 = "skill2"
ULT = "ult"


# ---------- Legacy blocking skill animation ----------
class SkillAnimation:
    def __init__(self, folder_path, prefix, count, ext="png", frame_time=80,
                 loop=False, bg_color=None, max_size=None):

        self.folder_path = folder_path
        self.prefix = prefix
        self.count = count
        self.ext = ext
        self.frame_time = frame_time
        self.loop = loop
        self.bg_color = bg_color
        self.max_size = max_size
        self.frames = self._load_frames()

    def _load_frames(self):
        frames = []
        for i in range(1, self.count + 1):
            path = f"{self.folder_path}/{self.prefix}_{i}.{self.ext}"
            image = pygame.image.load(path).convert_alpha()
            if self.max_size is not None:
                image = self._fitToSize(image, self.max_size)
            frames.append(image)
        return frames

    @staticmethod
    def _fitToSize(image, max_size):
        max_w, max_h = max_size
        imageWidth, imageHeight = image.get_size()
        scale = min(max_w / imageWidth, max_h / imageHeight, 1.0)  # never upscale past native size
        if scale >= 1.0:
            return image
        new_size = (max(1, int(imageWidth * scale)), max(1, int(imageHeight * scale)))
        return pygame.transform.smoothscale(image, new_size)

    def play(self, screen, clock, position=None, frame_time=None, bg_color=None, loop=None, redraw_callback=None):

        frame_time = self.frame_time if frame_time is None else frame_time
        bg_color = self.bg_color if bg_color is None else bg_color
        loop = self.loop if loop is None else loop

        if not self.frames:
            return

        if position is None:
            width, height = screen.get_size()
            position = (width // 2, height // 2)

        current_frame = 0
        last_update = pygame.time.get_ticks()

        playing = True
        while playing:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            now = pygame.time.get_ticks()
            if now - last_update > frame_time:
                current_frame += 1
                last_update = now

                if current_frame >= len(self.frames):
                    if loop:
                        current_frame = 0
                    else:
                        current_frame = len(self.frames) - 1
                        playing = False

            frame = self.frames[current_frame]
            frame_rect = frame.get_rect(center=position)

            if redraw_callback is not None:
                redraw_callback()
            elif bg_color is not None:
                screen.fill(bg_color)
            screen.blit(frame, frame_rect)
            pygame.display.update()

            clock.tick(60)


class CharacterAnimations:
    def __init__(self, animations):
        self.animations = animations

    def play(self, skill_type, screen, clock, position=None, redraw_callback=None, **overrides):
        anim = self.animations.get(skill_type)
        if anim is None:
            print(f"[animation missing] no animation registered for '{skill_type}'")
            return
        anim.play(screen, clock, position=position, redraw_callback=redraw_callback, **overrides)


def load_character_animations(config):
    result = {}
    for char_name, skills in config.items():
        anims = {}
        for skill_type, kwargs in skills.items():
            anims[skill_type] = SkillAnimation(**kwargs)
        result[char_name] = CharacterAnimations(anims)
    return result


# ---------- Idle animation ----------

class IdleFrames:
    """The loaded frame surfaces for one animation folder."""

    _cache = {}

    def __init__(self, folder_path, prefix, count=8, ext="png", size=None):
        self.frames = self._load_frames(folder_path, prefix, count, ext, size)

    @staticmethod
    def _load_frames(folder_path, prefix, count, ext, size):
        frames = []
        for i in range(1, count + 1):
            path = f"{folder_path}/{prefix}_{i}.{ext}"
            image = pygame.image.load(path).convert_alpha()
            if size is not None and image.get_size() != tuple(size):
                image = pygame.transform.smoothscale(image, size)
            frames.append(image)
        return frames

    @classmethod
    def get(cls, folder_path, prefix, count=8, ext="png", size=None):
        """Cached load: the same (folder_path, prefix, size) only ever hits disk once, no matter how many sprites/characters ask for it."""
        key = (folder_path, prefix, count, ext, tuple(size) if size is not None else None)
        cachedFrames = cls._cache.get(key)
        if cachedFrames is None:
            cachedFrames = cls(folder_path, prefix, count, ext, size)
            cls._cache[key] = cachedFrames
        return cachedFrames


class IdleAnimation:
    """One sprite's own playback of a (possibly shared) IdleFrames -- its own current frame index and elapsed time."""

    def __init__(self, folder_path, prefix, count=8, ext="png", frame_time=160,
                 size=None, skip_first=True, loop=True):
        self.framesObj = IdleFrames.get(folder_path, prefix, count, ext, size)
        self.frame_time = frame_time
        self.skip_first = skip_first
        self.loop = loop
        self.index = 0
        self.elapsed = 0

    def update(self, dt):
        """Call once per frame with the same dt as everything else (clock.tick(FPS))."""
        frames = self.framesObj.frames
        if len(frames) < 2:
            return
        if not self.loop and self.index >= len(frames) - 1:
            return
        loopStart = 1 if (self.skip_first and len(frames) > 1) else 0
        self.elapsed += dt
        while self.elapsed >= self.frame_time:
            self.elapsed -= self.frame_time
            self.index += 1
            if self.index >= len(frames):
                if self.loop:
                    self.index = loopStart
                else:
                    self.index = len(frames) - 1
                    self.elapsed = 0
                    break

    @property
    def frame(self):
        """The current frame's surface, or None if nothing loaded."""
        frames = self.framesObj.frames
        return frames[self.index] if frames else None


def loadIdleAnimations(config, sprites):
    """Builds one IdleAnimation *per sprite* -- not per character name -- so duplicate characters on the field never share a timer."""
    result = {}
    for sprite in sprites:
        animationConfig = config.get(sprite["name"])
        if animationConfig is None:
            continue
        kwargs = dict(animationConfig)
        kwargs.setdefault("size", sprite["stats"].image.get_size())
        result[id(sprite)] = IdleAnimation(**kwargs)
    return result


def updateIdleAnimations(sprites, idleAnimations, dt):
    """Call once per frame, before drawing."""
    for sprite in sprites:
        if sprite.get("dead"):
            continue
        anim = idleAnimations.get(id(sprite))
        if anim is None or anim.frame is None:
            continue
        anim.update(dt)
        sprite["stats"].image = anim.frame


# ---------- Legacy action animation playback ----------
SKILL_ANIMATION_FORWARD_OFFSET = 150


def _animationPosition(attacker):

    stats = attacker.get("stats")
    if stats is None:
        return None
    x, y = stats.rect.center
    if attacker.get("side") == "left":
        x += SKILL_ANIMATION_FORWARD_OFFSET
    else:
        x -= SKILL_ANIMATION_FORWARD_OFFSET
    return (x, y)


def playActionAnimation(action, character_animations, screen, clock, redraw_callback=None):

    if action is None:
        return

    if action.get("_animationPlayed"):
        return

    attacker = action.get("sprite")
    skillName = action.get("skillName")
    skillDef = action.get("skillDef")

    if attacker is None:
        return

    char_name = attacker.get("name")
    anims = character_animations.get(char_name)
    if anims is None:
        return

    position = _animationPosition(attacker)

    if skillName is not None and skillName in anims.animations:
        action["_animationPlayed"] = True
        anims.play(skillName, screen, clock, position=position, redraw_callback=redraw_callback)
        return

    if skillDef is not None and getattr(skillDef, "icon", None) in anims.animations:
        action["_animationPlayed"] = True
        anims.play(skillDef.icon, screen, clock, position=position, redraw_callback=redraw_callback)
        return

    print(f"[animation missing] no animation registered for {char_name}'s '{skillName}'")


# ---------- Skill effects (configurable, non-blocking) ----------

# ---------- Effect categories ----------
CHARGE = "charge"
PROJECTILE = "projectile"
DIRECT = "direct"
BUFF = "buff"
REPLACE_IDLE = "replace_idle"
ENVELOP = "envelop"

# ---------- Dash look (CHARGE: speed lines + slight motion blur while the attacker rushes in / back) ----------
DASH_LINES_PER_FRAME = 2        # speed lines spawned each frame the sprite is moving
DASH_LINE_LIFE_MS = 180         # how long a speed line lingers (it fades out)
DASH_LINE_LENGTH = (50, 130)    # px, min/max
DASH_LINE_WIDTH = (2, 3)        # px, min/max
DASH_LINE_COLOR = (235, 245, 255)
DASH_LINE_ALPHA = 200
DASH_BLUR_COPIES = 4            # faint copies of the sprite smeared behind it
DASH_BLUR_MAX_LEN = 20          # px, smear length at full speed ("a little blur")
DASH_BLUR_ALPHA = 105           # opacity of the nearest smear copy
DASH_BLUR_FULL_SPEED = 2.0      # px/ms at which the blur reaches its full length

# ---------- Cast pose (DIRECT: a generic attack motion for characters with no action animation of their own) ----------
CAST_WINDUP_MS = 90             # lean back
CAST_THRUST_MS = 70             # snap forward
CAST_RETURN_MS = 170            # ease back home
CAST_WINDUP_DIST = 10           # px back
CAST_THRUST_DIST = 28           # px forward (past home)
CAST_FLASH_ALPHA = 190          # peak opacity of the white flash on the sprite
CAST_FLASH_COLOR = (255, 244, 214)

# Categories that, like BUFF, play on the attacker rather than the target.
_SELF_ANCHORED = (BUFF, REPLACE_IDLE, ENVELOP)


# ---------- Skill frame loading ----------
def _hueMatrix(degrees):
    """3x3 RGB matrix that rotates every color's hue by `degrees` around the grey axis (1,1,1)."""
    angleRadians = math.radians(degrees)
    cosAngle, sinAngle = math.cos(angleRadians), math.sin(angleRadians)
    equalMixShare = (1.0 - cosAngle) / 3.0
    rotationTerm = math.sqrt(1.0 / 3.0) * sinAngle
    return [
        [cosAngle + equalMixShare, equalMixShare - rotationTerm, equalMixShare + rotationTerm],
        [equalMixShare + rotationTerm, cosAngle + equalMixShare, equalMixShare - rotationTerm],
        [equalMixShare - rotationTerm, equalMixShare + rotationTerm, cosAngle + equalMixShare],
    ]


_warnedNoNumpy = False


class SkillFrames:
    """The loaded frame surfaces for one skill animation folder."""

    _cache = {}

    def __init__(self, folder_path, prefix, count=8, ext="png", size=None, max_size=None,
                 flip=False, tint=None, hue_shift=0, scale=1.0):
        self.frames = self._load_frames(folder_path, prefix, count, ext, size, max_size,
                                        flip, tint, hue_shift, scale)

    @staticmethod
    def _load_frames(folder_path, prefix, count, ext, size, max_size,
                     flip=False, tint=None, hue_shift=0, scale=1.0):
        frames = []
        for i in range(1, count + 1):
            path = f"{folder_path}/{prefix}_{i}.{ext}"
            image = pygame.image.load(path).convert_alpha()
            if size is not None and image.get_size() != tuple(size):
                image = pygame.transform.smoothscale(image, size)
            elif max_size is not None:
                image = SkillFrames._fitToSize(image, max_size)
            # "scale" multiplies the frame (aspect kept) and, unlike max_size, CAN enlarge it
            if scale and scale != 1.0:
                imageWidth, imageHeight = image.get_size()
                image = pygame.transform.smoothscale(image, (max(1, round(imageWidth * scale)), max(1, round(imageHeight * scale))))
            # recolor AFTER scaling (fewer pixels to touch), flip last
            if hue_shift:
                image = SkillFrames._hueShift(image, hue_shift)
            if tint is not None:
                image = SkillFrames._tint(image, tint)
            if flip:
                image = pygame.transform.flip(image, True, False)
            frames.append(image)
        return frames

    @staticmethod
    def _tint(image, tint):
        tinted = image.copy()
        tinted.fill((*tint[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)   # alpha x255 = unchanged
        return tinted

    @staticmethod
    def _hueShift(image, degrees):
        global _warnedNoNumpy
        try:
            import numpy as np
        except ImportError:
            if not _warnedNoNumpy:
                print("hue_shift needs numpy (pip install numpy) -- skipping it, use `tint` instead")
                _warnedNoNumpy = True
            return image
        shifted = image.copy()
        pixels = pygame.surfarray.pixels3d(shifted)   # live RGB view; alpha is left untouched
        rgb = pixels.astype(np.float32)
        pixels[:] = np.clip(rgb @ np.array(_hueMatrix(degrees), dtype=np.float32).T, 0, 255).astype(np.uint8)
        del pixels   # release the surface lock
        return shifted

    @staticmethod
    def _fitToSize(image, max_size):
        max_w, max_h = max_size
        imageWidth, imageHeight = image.get_size()
        scale = min(max_w / imageWidth, max_h / imageHeight, 1.0)   # never upscale past native size
        if scale >= 1.0:
            return image
        new_size = (max(1, int(imageWidth * scale)), max(1, int(imageHeight * scale)))
        return pygame.transform.smoothscale(image, new_size)

    @classmethod
    def get(cls, folder_path, prefix, count=8, ext="png", size=None, max_size=None,
            flip=False, tint=None, hue_shift=0, scale=1.0):
        """Cached load: the same (folder_path, prefix, size, look) only ever hits disk once, no matter how many times the skill is cast."""
        tint = tuple(tint) if tint is not None else None
        key = (folder_path, prefix, count, ext,
               tuple(size) if size is not None else None,
               tuple(max_size) if max_size is not None else None,
               bool(flip), tint, hue_shift, scale)
        cachedFrames = cls._cache.get(key)
        if cachedFrames is None:
            cachedFrames = cls(folder_path, prefix, count, ext, size, max_size, flip, tint, hue_shift, scale)
            cls._cache[key] = cachedFrames
        return cachedFrames


# ---------- Effect anchoring ----------
def _skillEffectAnchor(attacker, target, offset, anchor):
    """Where something sits relative to the sprite it is anchored to."""
    sprite = attacker if anchor == "self" else target
    x, y = sprite["stats"].rect.center
    towardAttacker = -1 if attacker.get("side") == "left" else 1
    if isinstance(offset, (tuple, list)):
        offsetX, offsetY = offset
    else:
        offsetX, offsetY = offset, 0
    return (x + offsetX * towardAttacker, y + offsetY)


# ---------- SkillEffect (playback, motion, impact timing) ----------
class SkillEffect:
    """One playthrough of a skill's animation."""

    def __init__(self, action, config):
        self.action = action
        self.attacker = action["sprite"]
        self.target = action["target"]
        self.category = config.get("category", DIRECT)
        self.anchor = config.get("anchor", "self" if self.category in _SELF_ANCHORED else "target")
        # REPLACE_IDLE/ENVELOP play right on top of the attacker.
        defaultOffset = 0 if self.category in (REPLACE_IDLE, ENVELOP) else SKILL_ANIMATION_FORWARD_OFFSET
        legacyOffset = config.get("offset", defaultOffset)
        self.skillOffset = config.get("skillOffset", legacyOffset)   # where the effect frames play
        self.charOffset = config.get("charOffset", legacyOffset)     # where a CHARGE-ing character stops
        self.offset = self.skillOffset                               # kept for anything still reading .offset

        size = config.get("size")
        max_size = config.get("max_size")
        if size is None and max_size is None and self.category in (REPLACE_IDLE, ENVELOP):
            # No explicit size given.
            attackerSize = self.attacker["stats"].image.get_size()
            if self.category == ENVELOP:
                scale = config.get("envelop_scale", 1.6)
                size = (round(attackerSize[0] * scale), round(attackerSize[1] * scale))
            else:
                size = attackerSize

        # flip: True / False / "auto" (= mirror only for a right-side attacker)
        flipOption = config.get("flip", False)
        if flipOption == "auto":
            self.flipped = self.attacker.get("side") == "right"
        else:
            self.flipped = bool(flipOption)

        self.framesObj = SkillFrames.get(
            config["folder_path"], config.get("prefix", "skill"),
            config.get("count", 8), config.get("ext", "png"),
            size, max_size,
            flip=self.flipped,
            tint=config.get("tint"),
            hue_shift=config.get("hue_shift", 0),
            scale=config.get("scale", 1.0),
        )

        # ---------- natural drift & shake ----------
        self.drift = config.get("drift", 0)
        self.drift_speed = config.get("drift_speed", 0.004)
        self.shake = config.get("shake", 0)
        # Randomized per instance so simultaneous casts (e.g.
        self._driftPhaseX = random.uniform(0, math.tau)
        self._driftPhaseY = random.uniform(0, math.tau)
        self._driftFreqY = self.drift_speed * random.uniform(0.7, 1.3)
        self._shakeOffset = (0.0, 0.0)

        # ---------- trail & spin ----------
        self.trail = max(0, int(config.get("trail", 0)))
        self.trail_gap = config.get("trail_gap", 30)
        self.trail_fade = config.get("trail_fade", 0.6)
        self.trail_shrink = config.get("trail_shrink", 1.0)
        self.spin_speed = config.get("spin_speed", 0)
        self._trailTimer = 0
        self._trailHistory = []

        frameCount = max(1, len(self.framesObj.frames))
        self.frame_time = config.get("frame_time", 80)
        self.impact_frame = max(0, min(config.get("impact_frame", frameCount - 1), frameCount - 1))
        self.hold_time = config.get("hold_time", 0)
        # Whether frames keep cycling once the main animation is done.
        self.loop = config.get("loop", self.hold_time > 0)

        playDuration = frameCount * self.frame_time
        self.playDuration = playDuration
        impactIntoPlay = self.impact_frame * self.frame_time

        self.homeCenter = self.attacker["stats"].rect.center

        if self.category == CHARGE:
            approachTime = config.get("approach_time", 200)
            retreatTime = config.get("retreat_time", 200)
            # hold_time here means "linger at the target.
            self.segments = [("approach", approachTime), ("play", playDuration + self.hold_time), ("retreat", retreatTime)]
            self.impactAt = approachTime + impactIntoPlay
            self.chargeTo = _skillEffectAnchor(self.attacker, self.target, self.charOffset, "target")
            # the effect frames get their own offset, independent of the character's
            self.effectCenter = _skillEffectAnchor(self.attacker, self.target, self.skillOffset, self.anchor)
        elif self.category == PROJECTILE:
            self.travel_time = config.get("travel_time", 300)
            self.segments = [("travel", max(self.travel_time, playDuration))]
            self.impactAt = config.get("impact_time", self.travel_time)
        else:   # DIRECT or BUFF
            self.segments = [("play", playDuration)]
            self.impactAt = impactIntoPlay
            self.effectCenter = _skillEffectAnchor(self.attacker, self.target, self.skillOffset, self.anchor)

        # CHARGE already folded hold_time into its "play" segment above.
        self.duration = sum(segmentDuration for _, segmentDuration in self.segments)
        if self.category != CHARGE:
            self.duration += self.hold_time
        self.elapsed = 0
        self.impactFired = False
        self.impactJustFired = False

        # ---------- cast pose (DIRECT only) ----------
        # Config: "cast" (True by default for DIRECT; False turns it off), "cast_distance" (px of forward thrust),
        # "cast_flash" (False = no flash), "cast_color" (flash colour).
        self.cast = (self.category == DIRECT
                     and bool(config.get("cast", True))
                     and not action.get("_splash")
                     and self.target is not None
                     and self.target is not self.attacker)
        if self.cast:
            targetX, targetY = self.target["stats"].rect.center
            homeX, homeY = self.homeCenter
            distanceToTarget = math.hypot(targetX - homeX, targetY - homeY)
            # only lunge at an opponent; a cast aimed at an ally just flashes in place
            hostile = self.target.get("side") != self.attacker.get("side") and distanceToTarget > 1
            self.castDir = ((targetX - homeX) / distanceToTarget, (targetY - homeY) / distanceToTarget) if hostile else (0.0, 0.0)
            self.castThrust = config.get("cast_distance", CAST_THRUST_DIST)
            self.castWindup = CAST_WINDUP_DIST * (self.castThrust / CAST_THRUST_DIST) if CAST_THRUST_DIST else 0
            self.castFlashOn = bool(config.get("cast_flash", True))
            self.castColor = tuple(config.get("cast_color", CAST_FLASH_COLOR))
            span = CAST_WINDUP_MS + CAST_THRUST_MS + CAST_RETURN_MS
            timeScale = min(1.0, self.duration / span) if self.duration > 0 else 1.0   # never outlast the animation
            self.castTimes = (CAST_WINDUP_MS * timeScale, CAST_THRUST_MS * timeScale, CAST_RETURN_MS * timeScale)

        # ---------- dash look (CHARGE only) ----------
        # Config: "dash" (True by default for CHARGE; False turns the whole effect off),
        # "dash_lines" (False = no speed lines), "dash_blur" (False = no motion blur).
        self.dash = (self.category == CHARGE
                     and bool(config.get("dash", True))
                     and not action.get("_splash"))
        self.dashLinesOn = bool(config.get("dash_lines", True))
        self.dashBlurOn = bool(config.get("dash_blur", True))
        self._dashLines = []
        self._dashMove = (0.0, 0.0)      # unit vector of the sprite's current motion
        self._dashSpeed = 0.0            # px per ms

        # ---------- tick schedule ----------
        self.ticks = max(1, int(config.get("ticks", 1)))
        if self.ticks > 1:
            span = max(0.0, self.duration - self.impactAt)
            interval = span / self.ticks
        else:
            interval = 0
        self._tickTimes = [self.impactAt + i * interval for i in range(self.ticks)]
        self._ticksFired = 0
        self.ticksFiredNow = []
        self.tickJustFired = False  # True whenever ticksFiredNow is non-empty

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def _segmentElapsed(self):
        """(phase, ms into that phase) -- only CHARGE has more than one named phase; everything else is just one long "play"/"travel"."""
        if self.category != CHARGE:
            return ("play", self.elapsed)
        approachTime, playTime, _retreatTime = (segmentDuration for _, segmentDuration in self.segments)
        if self.elapsed < approachTime:
            return ("approach", self.elapsed)
        if self.elapsed < approachTime + playTime:
            return ("play", self.elapsed - approachTime)
        return ("retreat", self.elapsed - approachTime - playTime)

    def update(self, dt):
        """Call once per frame with the same dt as everything else."""
        self.elapsed = min(self.elapsed + dt, self.duration)

        if self.shake:
            self._shakeOffset = (random.uniform(-self.shake, self.shake),
                                  random.uniform(-self.shake, self.shake))

        # Collect every tick whose time has now passed.
        self.ticksFiredNow = []
        while self._ticksFired < self.ticks and self.elapsed >= self._tickTimes[self._ticksFired]:
            self.ticksFiredNow.append(self._ticksFired)
            self._ticksFired += 1
        self.tickJustFired = bool(self.ticksFiredNow)

        # impactFired/impactJustFired kept as a compatibility alias for the very first tick.
        self.impactJustFired = 0 in self.ticksFiredNow
        if self.impactJustFired:
            self.impactFired = True

        chargeFrom = self.attacker["stats"].rect.center
        if self.category == CHARGE:
            phase, segmentProgress = self._segmentElapsed()
            approachTime, _playTime, retreatTime = (segmentDuration for _, segmentDuration in self.segments)
            if phase == "approach":
                self._lerpAttacker(self.homeCenter, self.chargeTo, segmentProgress / approachTime if approachTime else 1)
            elif phase == "play":
                self.attacker["stats"].rect.center = self.chargeTo
            else:
                self._lerpAttacker(self.chargeTo, self.homeCenter, segmentProgress / retreatTime if retreatTime else 1)
            if self.finished:
                self.attacker["stats"].rect.center = self.homeCenter   # exact snap back, no float drift

        if self.dash:
            self._trackDash(chargeFrom, dt)
        if self.cast:
            self._updateCast()

        if self.trail:
            self._trailTimer += dt
            while self._trailTimer >= self.trail_gap:
                self._trailTimer -= self.trail_gap
                frame = self.frame
                if frame is not None:
                    self._trailHistory.append((frame, self.position, self.angle))
                    if len(self._trailHistory) > self.trail:
                        self._trailHistory.pop(0)

    def _castOffset(self):
        """Signed px along the target direction: dips back, snaps forward past home, eases home."""
        windup, thrust, retreatTime = self.castTimes
        castElapsed = self.elapsed
        if castElapsed < windup:
            windupProgress = castElapsed / windup if windup else 1.0
            return -self.castWindup * (1 - (1 - windupProgress) ** 2)
        castElapsed -= windup
        if castElapsed < thrust:
            windupProgress = castElapsed / thrust if thrust else 1.0
            return -self.castWindup + (self.castThrust + self.castWindup) * windupProgress
        castElapsed -= thrust
        if castElapsed < retreatTime:
            windupProgress = castElapsed / retreatTime if retreatTime else 1.0
            return self.castThrust * (1 - windupProgress * windupProgress * (3 - 2 * windupProgress))
        return 0.0

    def _updateCast(self):
        rect = self.attacker["stats"].rect
        if self.finished:
            rect.center = self.homeCenter                      # exact snap back, no float drift
            return
        castOffset = self._castOffset()
        rect.center = (round(self.homeCenter[0] + self.castDir[0] * castOffset),
                       round(self.homeCenter[1] + self.castDir[1] * castOffset))

    def castFlashStrength(self):
        """0..1: ramps up through the thrust, peaks as it lands, then fades over the return."""
        windup, thrust, retreatTime = self.castTimes
        flashElapsed = self.elapsed - windup
        if flashElapsed <= 0:
            return 0.0
        if flashElapsed < thrust:
            return flashElapsed / thrust if thrust else 1.0
        return max(0.0, 1 - (flashElapsed - thrust) / (retreatTime * 1.1)) if retreatTime else 0.0

    def _trackDash(self, oldCenter, dt):
        """Works out how the attacker just moved, and spawns speed lines behind it while it's moving."""
        rect = self.attacker["stats"].rect
        dx, dy = rect.centerx - oldCenter[0], rect.centery - oldCenter[1]
        moved = math.hypot(dx, dy)
        if moved >= 1 and dt > 0:
            self._dashMove = (dx / moved, dy / moved)
            self._dashSpeed = moved / dt
        else:
            self._dashSpeed = 0.0

        if self.dashLinesOn and self._dashSpeed > 0.15 and not self.finished:
            moveX, moveY = self._dashMove
            perpX, perpY = -moveY, moveX                                   # perpendicular to the motion
            trailHeight = rect.height * 0.9
            for _ in range(DASH_LINES_PER_FRAME):
                sideOffset = random.uniform(-0.5, 0.5) * trailHeight
                back = random.uniform(0.1, 0.5) * rect.width   # start just behind the sprite's middle
                lineStartX = rect.centerx + perpX * sideOffset - moveX * back
                lineStartY = rect.centery + perpY * sideOffset - moveY * back
                length = random.uniform(*DASH_LINE_LENGTH)
                self._dashLines.append((lineStartX, lineStartY, lineStartX - moveX * length, lineStartY - moveY * length,
                                        random.randint(*DASH_LINE_WIDTH), self.elapsed))
        self._dashLines = [dashLine for dashLine in self._dashLines if self.elapsed - dashLine[5] < DASH_LINE_LIFE_MS]

    def _lerpAttacker(self, start, endPoint, moveProgress):
        moveProgress = max(0.0, min(1.0, moveProgress))
        x = start[0] + (endPoint[0] - start[0]) * moveProgress
        y = start[1] + (endPoint[1] - start[1]) * moveProgress
        self.attacker["stats"].rect.center = (round(x), round(y))

    @property
    def frame(self):
        """The current frame's surface, or None if there's nothing to draw right now (e.g."""
        frames = self.framesObj.frames
        if not frames:
            return None
        if self.category == CHARGE:
            phase, segmentProgress = self._segmentElapsed()
            if phase != "play":
                return None
            if self.hold_time > 0 and segmentProgress >= self.playDuration:
                # Same idea as the hold-loop below.
                if self.loop:
                    index = int((segmentProgress - self.playDuration) // self.frame_time) % len(frames)
                else:
                    index = len(frames) - 1
            else:
                index = int(segmentProgress // self.frame_time)
                index = max(0, min(index, len(frames) - 1))
        else:
            # Once the main animation has finished playing.
            mainDuration = self.duration - self.hold_time
            if self.hold_time > 0 and self.elapsed >= mainDuration:
                if self.loop:
                    index = int((self.elapsed - mainDuration) // self.frame_time) % len(frames)
                else:
                    index = len(frames) - 1
            else:
                index = min(int(self.elapsed // self.frame_time), len(frames) - 1)
        return frames[index]

    @property
    def position(self):
        """Where to draw .frame."""
        if self.category == CHARGE:
            base = self.effectCenter
        elif self.category == PROJECTILE:
            travelProgress = min(1.0, self.elapsed / self.travel_time) if self.travel_time else 1
            start = self.homeCenter
            targetCenter = self.target["stats"].rect.center
            base = (start[0] + (targetCenter[0] - start[0]) * travelProgress, start[1] + (targetCenter[1] - start[1]) * travelProgress)
        else:
            base = self.effectCenter

        dx, dy = self._driftOffset()
        shakeX, shakeY = self._shakeOffset
        return (base[0] + dx + shakeX, base[1] + dy + shakeY)

    @property
    def angle(self):
        """Current spin angle in degrees (0 if spin_speed is off)."""
        if not self.spin_speed:
            return 0
        angle = (self.elapsed * self.spin_speed) % 360
        return -angle if self.flipped else angle

    @property
    def cameraFocus(self):
        """Where a dramatic camera should center while this effect plays."""
        if self.category == CHARGE:
            return self.attacker["stats"].rect.center
        return self.position

    def _driftOffset(self):
        """Slow, smooth wander."""
        if not self.drift:
            return (0.0, 0.0)
        elapsedMs = self.elapsed
        dx = self.drift * math.sin(elapsedMs * self.drift_speed + self._driftPhaseX)
        dy = self.drift * 0.6 * math.sin(elapsedMs * self._driftFreqY + self._driftPhaseY)
        return (dx, dy)


# ---------- Skill effect loading (primary and AOE splash) ----------
def _resolveSkillConfig(action, config_by_char):
    """Looks up `action`'s animation config -- by its sprite's name, then its skillName, falling back to its skillDef.icon."""
    perChar = config_by_char.get(action["sprite"].get("name"))
    if not perChar:
        return None
    skillName = action.get("skillName")
    skillDef = action.get("skillDef")
    if skillName is not None and skillName in perChar:
        return perChar[skillName]
    if skillDef is not None and getattr(skillDef, "icon", None) in perChar:
        return perChar[skillDef.icon]
    return None

def loadSkillEffect(action, config_by_char):
    """Returns a SkillEffect for `action`'s primary target, or None if this skill has no configured animation."""
    config = _resolveSkillConfig(action, config_by_char)
    if config is None:
        return None
    return SkillEffect(action, config)

SPLASH_EFFECT_DELAY = 0

# WHEN the splash copies begin.
SPLASH_START_WITH_PRIMARY = True

def splashStartsWithPrimary(action, config_by_char):
    config = _resolveSkillConfig(action, config_by_char)
    if config is None:
        return False
    return bool(config.get("splashSync", SPLASH_START_WITH_PRIMARY))

def splashDelayFor(action, config_by_char):
    """Per-target stagger for `action`'s splash animations: the skill's own "splashDelay" if it sets one, otherwise SPLASH_EFFECT_DELAY."""
    config = _resolveSkillConfig(action, config_by_char)
    if config is None:
        return 0
    return max(0, config.get("splashDelay", SPLASH_EFFECT_DELAY))

def loadSplashEffect(action, target, config_by_char):
    """The AOE counterpart to loadSkillEffect -- builds a SkillEffect for one of `action`'s SPLASH targets instead of its primary target."""
    config = _resolveSkillConfig(action, config_by_char)
    if config is None or not config.get("splashEffect", True):
        return None
    splashAction = {**action, "target": target, "_splash": True}
    return SkillEffect(splashAction, config)


# ---------- Skill effect rendering (trails and drawing) ----------
def _renderTrailGhost(surface, angle, scale, alpha):
    """One faded/shrunk/rotated afterimage."""
    ghost = surface
    if angle:
        ghost = pygame.transform.rotate(ghost, angle)
    if scale != 1.0:
        ghostWidth, ghostHeight = ghost.get_size()
        size = (max(1, round(ghostWidth * scale)), max(1, round(ghostHeight * scale)))
        ghost = pygame.transform.smoothscale(ghost, size)
    if ghost is surface:
        ghost = surface.copy()
    ghost.set_alpha(alpha)
    return ghost


def _drawDashLines(window, skillAnim, alpha):
    """Thin white speed lines left along the dash path, fading out."""
    lines = getattr(skillAnim, "_dashLines", None)
    if not lines:
        return
    allX = [coordinate for dashLine in lines for coordinate in (dashLine[0], dashLine[2])]
    allY = [coordinate for dashLine in lines for coordinate in (dashLine[1], dashLine[3])]
    pad = DASH_LINE_WIDTH[1] + 2
    left, top = int(min(allX)) - pad, int(min(allY)) - pad
    layer = pygame.Surface((int(max(allX)) - left + pad * 2, int(max(allY)) - top + pad * 2), pygame.SRCALPHA)
    for startX, startY, endX, endY, width, born in lines:
        age = (skillAnim.elapsed - born) / DASH_LINE_LIFE_MS
        lineAlpha = round(DASH_LINE_ALPHA * (1 - age) * alpha / 255)
        if lineAlpha > 0:
            pygame.draw.line(layer, (*DASH_LINE_COLOR, lineAlpha), (startX - left, startY - top), (endX - left, endY - top), width)
    window.blit(layer, (left, top))

def _drawDashBlur(window, skillAnim, alpha):
    """A short directional smear of the sprite: faint copies stepped back along its motion."""
    speed = getattr(skillAnim, "_dashSpeed", 0.0)
    if not getattr(skillAnim, "dashBlurOn", False) or speed <= 0:
        return
    length = DASH_BLUR_MAX_LEN * min(1.0, speed / DASH_BLUR_FULL_SPEED)
    if length < 2:
        return
    stats = skillAnim.attacker["stats"]
    moveX, moveY = skillAnim._dashMove
    for i in range(DASH_BLUR_COPIES, 0, -1):
        copyFraction = i / DASH_BLUR_COPIES
        blurAlpha = round(DASH_BLUR_ALPHA * (1 - (copyFraction - 1 / DASH_BLUR_COPIES) * 0.8) * alpha / 255)
        if blurAlpha <= 0:
            continue
        copy = stats.image.copy()
        copy.set_alpha(blurAlpha)
        window.blit(copy, stats.rect.move(round(-moveX * length * copyFraction), round(-moveY * length * copyFraction)))

_castSilhouetteCache = {}

def _drawCastFlash(window, skillAnim, alpha):
    """A white-hot silhouette over the attacker at the moment of the thrust."""
    if not getattr(skillAnim, "cast", False) or not skillAnim.castFlashOn:
        return
    strength = skillAnim.castFlashStrength()
    flashAlpha = round(CAST_FLASH_ALPHA * strength * alpha / 255)
    if flashAlpha <= 0:
        return
    stats = skillAnim.attacker["stats"]
    key = (id(stats.image), skillAnim.castColor)
    entry = _castSilhouetteCache.get(key)
    if entry is None or entry[0] is not stats.image:
        if len(_castSilhouetteCache) > 32:
            _castSilhouetteCache.clear()
        silhouetteImage = pygame.mask.from_surface(stats.image).to_surface(
            setcolor=(*skillAnim.castColor, 255), unsetcolor=(0, 0, 0, 0))
        entry = (stats.image, silhouetteImage)
        _castSilhouetteCache[key] = entry
    silhouetteImage = entry[1].copy()
    silhouetteImage.set_alpha(flashAlpha)
    window.blit(silhouetteImage, stats.rect)

def drawSkillEffect(window, skillAnim, alpha=255):
    """Draws the current frame of a playing SkillEffect, if any."""
    _drawCastFlash(window, skillAnim, alpha)
    if getattr(skillAnim, "dash", False):
        _drawDashBlur(window, skillAnim, alpha)
        _drawDashLines(window, skillAnim, alpha)
    history = skillAnim._trailHistory
    if history:
        stepsBack = len(history)
        for surf, pos, angle in history:
            ghostAlpha = round(255 * (skillAnim.trail_fade ** stepsBack) * alpha / 255)
            stepsBack -= 1
            if ghostAlpha <= 0:
                continue
            scale = skillAnim.trail_shrink ** (stepsBack + 1)
            ghost = _renderTrailGhost(surf, angle, scale, ghostAlpha)
            window.blit(ghost, ghost.get_rect(center=(round(pos[0]), round(pos[1]))))

    frame = skillAnim.frame
    if frame is None:
        return
    if skillAnim.spin_speed:
        frame = pygame.transform.rotate(frame, skillAnim.angle)
    if alpha < 255:
        frame = frame.copy()
        frame.set_alpha(max(0, alpha))
    x, y = skillAnim.position
    window.blit(frame, frame.get_rect(center=(round(x), round(y))))


# ---------- Coin flip animation ----------

COIN_FRAME_COUNT = 8
COIN_SIZE = 48
COIN_GAP = 6                    # gap between a player's two coins

# The 8 frames are one full rotation: 1.png = heads facing you, 5.png = tails.
COIN_HEADS_FRAME = 0
COIN_TAILS_FRAME = 4
COIN_SPINS = 1

COIN_PLAYER_WIN_TINT = (90, 255, 90)
COIN_ENEMY_WIN_TINT = (255, 90, 90)

COIN_SHOW_TIME = 700            # ms the coins sit still before flipping
COIN_FRAME_TIME = 70            # ms per animation frame
COIN_HOLD_TIME = 700            # ms the landed coins stay on screen

# ---------- Coin image helpers ----------
def makeGreyscale(surface):
    """Grey copy of a surface, keeping its transparency."""
    if hasattr(pygame.transform, "grayscale"):
        return pygame.transform.grayscale(surface)
    grey = surface.copy()
    for x in range(grey.get_width()):
        for y in range(grey.get_height()):
            red, green, blue, alpha = grey.get_at((x, y))
            greyValue = int(0.299 * red + 0.587 * green + 0.114 * blue)
            grey.set_at((x, y), (greyValue, greyValue, greyValue, alpha))
    return grey

# Frame 8 goes straight from the edge-on frame 7 to a full face.
COIN_INBETWEEN_SOURCE = 7       # frame to squash
COIN_INBETWEEN_WIDTH = 0.6
COIN_CYCLE = [0, 1, 2, 3, 4, 5, 6, 8, 7]

def makeInbetweenFrame(frame):
    frameWidth, frameHeight = frame.get_size()
    narrow = pygame.transform.smoothscale(frame, (max(2, int(frameWidth * COIN_INBETWEEN_WIDTH)), frameHeight))
    out = pygame.Surface((frameWidth, frameHeight), pygame.SRCALPHA)
    out.blit(narrow, narrow.get_rect(center=(frameWidth // 2, frameHeight // 2)))
    return out

# ---------- Coin frames ----------
class CoinFrames:
    """The 8 coin frames + the generated in-between frame, in colour, plus a grey copy of each."""
    def __init__(self, colorFrames):
        self.color = list(colorFrames) + [makeInbetweenFrame(colorFrames[COIN_INBETWEEN_SOURCE])]
        self.grey = [makeGreyscale(colorFrame) for colorFrame in self.color]
        self.tinted = {}

    def get(self, index, grey=False, tint=None):
        """Frame as colour or grey. `tint` (r, g, b) recolours the grey version."""
        if tint is None:
            return (self.grey if grey else self.color)[index]
        key = (index, tint)
        if key not in self.tinted:
            img = self.grey[index].copy()
            img.fill((40, 40, 40, 0), special_flags=pygame.BLEND_RGB_ADD)        # brighten a little
            img.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)         # keeps transparency
            self.tinted[key] = img
        return self.tinted[key]

def loadCoinFrames():
    """Call once AFTER pygame.display.set_mode (convert_alpha needs a display)."""
    frames = []
    for i in range(1, COIN_FRAME_COUNT + 1):
        coinFramePath = os.path.join(f"assets/img/coin/{i}.png")
        img = pygame.image.load(coinFramePath).convert_alpha()
        frames.append(pygame.transform.smoothscale(img, (COIN_SIZE, COIN_SIZE)))
    return CoinFrames(frames)

def coinFrameSequence(isHeads):
    """Frame indices for one coin: full spin(s), then on to the landing frame."""
    land = COIN_HEADS_FRAME if isHeads else COIN_TAILS_FRAME
    return COIN_CYCLE * COIN_SPINS + COIN_CYCLE[:COIN_CYCLE.index(land) + 1]

def getCoinRects(sprite):
    """Where the 2 coins go for a sprite (above its head, side by side)."""
    rect = sprite["stats"].rect
    totalWidth = COIN_SIZE * 2 + COIN_GAP
    left = rect.centerx - totalWidth // 2
    top = rect.top - COIN_SIZE - 6
    return [pygame.Rect(left + i * (COIN_SIZE + COIN_GAP), top, COIN_SIZE, COIN_SIZE) for i in range(2)]

# ---------- Coin flip animation ----------
class CoinFlipAnim:
    """Plays for one clash: coins appear above each clashing sprite, wait, spin, land and hold."""

    def __init__(self, actions, animate, tiebreak=None):
        self.actions = actions
        self.animate = animate
        self.tiebreak = tiebreak
        self.elapsed = 0
        self.showTime = COIN_SHOW_TIME if any(animate) else 0

        self.sequences = []
        longest = 0
        for action, doAnimate in zip(actions, animate):
            if doAnimate:
                seqs = [coinFrameSequence(face) for face in action["flips"]]
                longest = max([longest] + [len(sequence) for sequence in seqs])
            else:
                seqs = None
            self.sequences.append(seqs)

        flipEnd = self.showTime + longest * COIN_FRAME_TIME
        if tiebreak is None:
            self.duration = flipEnd + COIN_HOLD_TIME
        else:
            self.tbSeq = coinFrameSequence(tiebreak)
            self.tbShowStart = flipEnd + COIN_HOLD_TIME      # equal results linger first
            self.tbFlipStart = self.tbShowStart + COIN_SHOW_TIME
            self.tbEnd = self.tbFlipStart + len(self.tbSeq) * COIN_FRAME_TIME
            self.duration = self.tbEnd + COIN_HOLD_TIME
            self.winner = clashWinner(actions[0], actions[1], tiebreak)

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def frameFor(self, actionIdx, coinIdx):
        """(frame index, grey?) for one coin."""
        face = self.actions[actionIdx]["flips"][coinIdx]
        seqs = self.sequences[actionIdx]
        if seqs is None:
            return (COIN_HEADS_FRAME if face else COIN_TAILS_FRAME), not face
        return self._playFrame(seqs[coinIdx], self.elapsed - self.showTime, face)

    def tiebreakFrame(self):
        """(frame index, grey?) for the decider coin, or None if it isn't on screen yet."""
        if self.tiebreak is None or self.elapsed < self.tbShowStart:
            return None
        return self._playFrame(self.tbSeq, self.elapsed - self.tbFlipStart, self.tiebreak)

    @staticmethod
    def _playFrame(frameSequence, flipProgress, isHeads):
        if flipProgress < 0:
            return frameSequence[0], True                      # waiting to flip: grey
        step = int(flipProgress / COIN_FRAME_TIME)
        if step >= len(frameSequence) - 1:
            return frameSequence[-1], not isHeads              # landed: grey if tails
        return frameSequence[step], True                       # spinning: grey

    def tiebreakCoinLanded(self):
        """True as soon as the decider coin itself has landed."""
        return self.tiebreak is not None and \
            self.elapsed - self.tbFlipStart >= (len(self.tbSeq) - 1) * COIN_FRAME_TIME

    def tiebreakLanded(self):
        return self.tiebreak is not None and self.elapsed >= self.tbEnd

# ---------- Coin flip drawing ----------
def getTiebreakCoinRect(actions):
    """The decider coin sits halfway between the two clashing sprites, on the same row as their coins."""
    rects = [action["sprite"]["stats"].rect for action in actions]
    centerX = sum(rect.centerx for rect in rects) // len(rects)
    top = sum(rect.top for rect in rects) // len(rects) - COIN_SIZE - 6
    return pygame.Rect(centerX - COIN_SIZE // 2, top, COIN_SIZE, COIN_SIZE)

def drawCoinFlip(window, anim, frames):
    landed = anim.tiebreakLanded()
    for idx, action in enumerate(anim.actions):
        isWinner = landed and action is anim.winner
        color = (60, 220, 60) if isWinner else (255, 215, 0)
        drawCharacterGlow(window, action["sprite"], color)
        for coinIdx, rect in enumerate(getCoinRects(action["sprite"])):
            window.blit(frames.get(*anim.frameFor(idx, coinIdx)), rect)

    tbFrame = anim.tiebreakFrame()
    if tbFrame is not None:
        rect = getTiebreakCoinRect(anim.actions)
        title = FONT.render("Tiebreaker!", True, (255, 255, 255))
        window.blit(title, title.get_rect(midbottom=(rect.centerx, rect.top - 2)))
        if anim.tiebreakCoinLanded():
            tint = COIN_PLAYER_WIN_TINT if anim.tiebreak else COIN_ENEMY_WIN_TINT   # green / red by winner
            window.blit(frames.get(tbFrame[0], True, tint), rect)
        else:
            window.blit(frames.get(*tbFrame), rect)
        if landed:
            text = "Player goes first" if anim.tiebreak else "Enemy goes first"
            label = FONT.render(text, True, (60, 220, 60) if anim.tiebreak else (230, 70, 70))
            window.blit(label, label.get_rect(midtop=(rect.centerx, rect.bottom + 2)))


# ---------- Damage popups ----------

DAMAGE_POPUP_DURATION = 900          # ms
DAMAGE_POPUP_YELLOW = (255, 225, 40)
DAMAGE_POPUP_RED = (230, 30, 20)
DAMAGE_POPUP_OUTLINE_COLOR = (45, 0, 0)
DAMAGE_POPUP_OUTLINE = 2
DAMAGE_POPUP_GRADIENT_STEPS = 12
DAMAGE_POPUP_SHAKE = 7               # px, peak shake amplitude at impact
DAMAGE_POPUP_SHAKE_END = 0.6
DAMAGE_POPUP_POP_SCALE = 1.6         # how far the initial pop overshoots
DAMAGE_POPUP_FADE_START = 0.6

_damageTextCache = {}

def _damageTextSurface(text, step):
    """Outlined yellow->red gradient text."""
    key = (text, step)
    surf = _damageTextCache.get(key)
    if surf is not None:
        return surf
    if len(_damageTextCache) >= 256:
        _damageTextCache.clear()

    base = DAMAGE_POPUP_FONT.render(text, True, (255, 255, 255))
    textWidth, textHeight = base.get_size()

    # vertical gradient, multiplied onto the white text (alpha untouched)
    shift = step / max(1, DAMAGE_POPUP_GRADIENT_STEPS - 1)
    gradient = pygame.Surface((textWidth, textHeight))
    for y in range(textHeight):
        colorBlend = min(1.0, (y / textHeight) * 0.7 + shift * 0.7)
        color = tuple(round(fromChannel + (toChannel - fromChannel) * colorBlend) for fromChannel, toChannel in zip(DAMAGE_POPUP_YELLOW, DAMAGE_POPUP_RED))
        pygame.draw.line(gradient, color, (0, y), (textWidth, y))
    base.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    outlineSize = DAMAGE_POPUP_OUTLINE
    surf = pygame.Surface((textWidth + 2 * outlineSize, textHeight + 2 * outlineSize), pygame.SRCALPHA)
    outline = DAMAGE_POPUP_FONT.render(text, True, DAMAGE_POPUP_OUTLINE_COLOR)
    for dx in (-outlineSize, 0, outlineSize):
        for dy in (-outlineSize, 0, outlineSize):
            if dx or dy:
                surf.blit(outline, (outlineSize + dx, outlineSize + dy))
    surf.blit(base, (outlineSize, outlineSize))
    _damageTextCache[key] = surf
    return surf

# ---------- Heal popups ----------
HEAL_POPUP_LIGHT = (150, 255, 150)
HEAL_POPUP_DARK = (30, 170, 60)

_healTextCache = {}

def _healTextSurface(text, step):
    """Outlined light-green->deep-green gradient text -- the heal counterpart to _damageTextSurface above, same construction."""
    key = (text, step)
    surf = _healTextCache.get(key)
    if surf is not None:
        return surf
    if len(_healTextCache) >= 256:
        _healTextCache.clear()

    base = DAMAGE_POPUP_FONT.render(text, True, (255, 255, 255))
    textWidth, textHeight = base.get_size()

    shift = step / max(1, DAMAGE_POPUP_GRADIENT_STEPS - 1)
    gradient = pygame.Surface((textWidth, textHeight))
    for y in range(textHeight):
        colorBlend = min(1.0, (y / textHeight) * 0.7 + shift * 0.7)
        color = tuple(round(fromChannel + (toChannel - fromChannel) * colorBlend) for fromChannel, toChannel in zip(HEAL_POPUP_LIGHT, HEAL_POPUP_DARK))
        pygame.draw.line(gradient, color, (0, y), (textWidth, y))
    base.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    outlineSize = DAMAGE_POPUP_OUTLINE
    surf = pygame.Surface((textWidth + 2 * outlineSize, textHeight + 2 * outlineSize), pygame.SRCALPHA)
    outline = DAMAGE_POPUP_FONT.render(text, True, DAMAGE_POPUP_OUTLINE_COLOR)
    for dx in (-outlineSize, 0, outlineSize):
        for dy in (-outlineSize, 0, outlineSize):
            if dx or dy:
                surf.blit(outline, (outlineSize + dx, outlineSize + dy))
    surf.blit(base, (outlineSize, outlineSize))
    _healTextCache[key] = surf
    return surf

# ---------- Sanity popups ----------
SANITY_POPUP_PALETTES = {
    "sanityUp":   ((150, 210, 255), (50, 110, 255)),
    "sanityDown": ((235, 170, 255), (140, 50, 210)),
}

_sanityTextCache = {}

def _sanityTextSurface(text, step, kind):
    key = (text, step, kind)
    surf = _sanityTextCache.get(key)
    if surf is not None:
        return surf
    if len(_sanityTextCache) >= 256:
        _sanityTextCache.clear()

    light, dark = SANITY_POPUP_PALETTES[kind]
    base = DAMAGE_POPUP_FONT.render(text, True, (255, 255, 255))
    textWidth, textHeight = base.get_size()

    shift = step / max(1, DAMAGE_POPUP_GRADIENT_STEPS - 1)
    gradient = pygame.Surface((textWidth, textHeight))
    for y in range(textHeight):
        colorBlend = min(1.0, (y / textHeight) * 0.7 + shift * 0.7)
        color = tuple(round(fromChannel + (toChannel - fromChannel) * colorBlend) for fromChannel, toChannel in zip(light, dark))
        pygame.draw.line(gradient, color, (0, y), (textWidth, y))
    base.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    outlineSize = DAMAGE_POPUP_OUTLINE
    surf = pygame.Surface((textWidth + 2 * outlineSize, textHeight + 2 * outlineSize), pygame.SRCALPHA)
    outline = DAMAGE_POPUP_FONT.render(text, True, DAMAGE_POPUP_OUTLINE_COLOR)
    for dx in (-outlineSize, 0, outlineSize):
        for dy in (-outlineSize, 0, outlineSize):
            if dx or dy:
                surf.blit(outline, (outlineSize + dx, outlineSize + dy))
    surf.blit(base, (outlineSize, outlineSize))
    _sanityTextCache[key] = surf
    return surf

# ---------- Popup update and drawing ----------
def _popupScale(popupProgress):
    """Scale over the popup's life (t = 0..1): quick pop up to an overshoot, settle back to 1.0, then a slow continuous expansion."""
    if popupProgress < 0.15:
        growProgress = popupProgress / 0.15
        return 0.4 + (DAMAGE_POPUP_POP_SCALE - 0.4) * (1 - (1 - growProgress) ** 2)   # ease-out
    if popupProgress < 0.35:
        growProgress = (popupProgress - 0.15) / 0.2
        growProgress = growProgress * growProgress * (3 - 2 * growProgress)                                            # smoothstep
        return DAMAGE_POPUP_POP_SCALE + (1.0 - DAMAGE_POPUP_POP_SCALE) * growProgress
    return 1.0 + 0.2 * ((popupProgress - 0.35) / 0.65)

def updateDamagePopups(popups, dt):
    for popup in popups[:]:
        popup["elapsed"] += dt
        if popup.get("float", True):
            popup["y"] -= 0.05 * dt
        if popup["elapsed"] >= DAMAGE_POPUP_DURATION:
            popups.remove(popup)

def drawDamagePopups(window, popups):
    for popup in popups:
        popupProgress = min(1.0, popup["elapsed"] / DAMAGE_POPUP_DURATION)

        step = min(DAMAGE_POPUP_GRADIENT_STEPS - 1, int(popupProgress * DAMAGE_POPUP_GRADIENT_STEPS))
        kind = popup.get("kind")
        if kind in SANITY_POPUP_PALETTES:
            base = _sanityTextSurface(popup["text"], step, kind)
        else:
            textSurfaceFn = _healTextSurface if kind == "heal" else _damageTextSurface
            base = textSurfaceFn(popup["text"], step)

        scale = _popupScale(popupProgress) * popup.get("scale", 1.0)
        size = (max(1, round(base.get_width() * scale)), max(1, round(base.get_height() * scale)))
        surf = pygame.transform.smoothscale(base, size)

        if popupProgress > DAMAGE_POPUP_FADE_START:
            fade = (popupProgress - DAMAGE_POPUP_FADE_START) / (1 - DAMAGE_POPUP_FADE_START)
            surf.set_alpha(max(0, round(255 * (1 - fade))))

        # violent at impact, dying out by DAMAGE_POPUP_SHAKE_END
        shakeAmplitude = DAMAGE_POPUP_SHAKE * max(0.0, 1 - popupProgress / DAMAGE_POPUP_SHAKE_END) ** 2
        shakeX = random.uniform(-shakeAmplitude, shakeAmplitude)
        shakeY = random.uniform(-shakeAmplitude, shakeAmplitude)

        anchor = popup.get("anchor")
        if anchor:
            # pinned to a bar: "x" is the text's near edge, "y" its vertical center
            pos = (round(popup["x"] + shakeX), round(popup["y"] + shakeY))
            rect = surf.get_rect(midright=pos) if anchor == "right" else surf.get_rect(midleft=pos)
            window.blit(surf, rect)
        else:
            # scale from the middle of the text so it swells outward, not down/right
            centerY = popup["y"] + base.get_height() / 2
            window.blit(surf, surf.get_rect(center=(round(popup["x"] + shakeX), round(centerY + shakeY))))


# ---------- Status-effect arrows (buff / debuff) ----------

STATUS_ARROW_DURATION = 1100

# A buff/debuff is now a VOLLEY of arrows spread across the sprite's body.
STATUS_ARROW_COLUMNS = 3            # arrows across the sprite's width...
STATUS_ARROW_PER_COLUMN = 1
STATUS_ARROW_LIFE = 0.55
STATUS_ARROW_MAX_DELAY = 0.30
STATUS_ARROW_TRAVEL_FRAC = 0.55
STATUS_ARROW_WIDTH_SPAN = 0.5
STATUS_ARROW_SIZE_RANGE = (1.0, 1.15)   # random size multiplier per arrow
STATUS_ARROW_FADE_IN = 0.15
STATUS_ARROW_FADE_START = 0.6
STATUS_ARROW_BUFF_COLOR = (70, 230, 100)
STATUS_ARROW_DEBUFF_COLOR = (230, 70, 70)
STATUS_ARROW_OUTLINE_COLOR = (25, 25, 25)
STATUS_ARROW_HEAD_WIDTH = 13     # px, tip-to-tip width of the arrowhead
STATUS_ARROW_HEAD_HEIGHT = 12
STATUS_ARROW_SHAFT_WIDTH = 4
STATUS_ARROW_SHAFT_HEIGHT = 15

# ---------- Cleanse sparkles ----------
STATUS_CLEANSE_COLOR = (150, 235, 255)
STATUS_CLEANSE_CORE_COLOR = (255, 255, 255)
STATUS_CLEANSE_SPARKLE_COUNT = 9
STATUS_CLEANSE_SIZE_RANGE = (4, 8)     # px, half-width of a sparkle
STATUS_CLEANSE_TRAVEL_FRAC = 0.75
STATUS_CLEANSE_SWAY_FRAC = 0.04

_cleanseSparkCache = {}

def _cleanseSparkSurface(size):
    surf = _cleanseSparkCache.get(size)
    if surf is None:
        side = size * 2 + 1
        center = size
        thickness = max(1.0, size * 0.28)
        points = [(center, 0), (center + thickness, center - thickness), (side - 1, center), (center + thickness, center + thickness),
                  (center, side - 1), (center - thickness, center + thickness), (0, center), (center - thickness, center - thickness)]
        surf = pygame.Surface((side, side), pygame.SRCALPHA)
        pygame.draw.polygon(surf, STATUS_CLEANSE_COLOR, points)
        pygame.draw.circle(surf, STATUS_CLEANSE_CORE_COLOR, (center, center), max(1, size // 3))
        _cleanseSparkCache[size] = surf
    return surf

def _cleanseLayout(popup):
    """Per-sparkle (xFraction, delayFraction, size, swayPhase), built once per popup."""
    sparks = popup.get("sparks")
    if sparks is None:
        rng = random.Random(id(popup))
        sparkleCount = STATUS_CLEANSE_SPARKLE_COUNT
        sparks = []
        for i in range(sparkleCount):
            sparks.append((
                rng.uniform(-0.35, 0.35),
                (i / max(1, sparkleCount - 1)) * STATUS_ARROW_MAX_DELAY,
                rng.randint(*STATUS_CLEANSE_SIZE_RANGE),
                rng.uniform(0, math.tau),
            ))
        popup["sparks"] = sparks
    return sparks

def _drawCleanseSparkles(window, popup, popupProgress):
    rect = popup["sprite"]["stats"].rect
    travel = rect.height * STATUS_CLEANSE_TRAVEL_FRAC
    for xFrac, delay, size, phase in _cleanseLayout(popup):
        local = (popupProgress - delay) / STATUS_ARROW_LIFE
        if local < 0 or local > 1:
            continue
        surf = _cleanseSparkSurface(size)
        x = rect.centerx + xFrac * rect.width + math.sin(local * math.tau + phase) * rect.width * STATUS_CLEANSE_SWAY_FRAC
        y = rect.bottom - rect.height * 0.1 - travel * local
        if local < STATUS_ARROW_FADE_IN:
            alpha = local / STATUS_ARROW_FADE_IN
        elif local > STATUS_ARROW_FADE_START:
            alpha = 1 - (local - STATUS_ARROW_FADE_START) / (1 - STATUS_ARROW_FADE_START)
        else:
            alpha = 1.0
        if alpha < 1.0:
            surf = surf.copy()
            surf.set_alpha(max(0, round(255 * alpha)))
        window.blit(surf, surf.get_rect(center=(round(x), round(y))))

def updateStatusArrowPopups(popups, dt):
    for popup in popups[:]:
        popup["elapsed"] += dt
        if popup["elapsed"] >= STATUS_ARROW_DURATION:
            popups.remove(popup)

def _statusArrowSurface(pointing_up, color):
    """A single up/down arrow glyph -- triangular head plus a short rectangular shaft."""
    headWidth = STATUS_ARROW_HEAD_WIDTH
    headH = STATUS_ARROW_HEAD_HEIGHT
    shaftW = STATUS_ARROW_SHAFT_WIDTH
    shaftH = STATUS_ARROW_SHAFT_HEIGHT
    height = headH + shaftH
    surf = pygame.Surface((headWidth, height), pygame.SRCALPHA)

    if pointing_up:
        head = [(headWidth / 2, 0), (0, headH), (headWidth, headH)]
        shaft = pygame.Rect((headWidth - shaftW) / 2, headH, shaftW, shaftH)
    else:
        head = [(headWidth / 2, height), (0, height - headH), (headWidth, height - headH)]
        shaft = pygame.Rect((headWidth - shaftW) / 2, 0, shaftW, shaftH)

    pygame.draw.rect(surf, color, shaft)
    pygame.draw.polygon(surf, color, head)
    pygame.draw.polygon(surf, STATUS_ARROW_OUTLINE_COLOR, head, 1)
    pygame.draw.rect(surf, STATUS_ARROW_OUTLINE_COLOR, shaft, 1)
    return surf

_statusArrowCache = {}

def _scaledStatusArrow(pointing_up, color, sizeScale):
    """_statusArrowSurface at a size multiplier, cached (a volley draws several arrows every frame, so rebuilding each one is wasteful)."""
    step = round(sizeScale * 20)
    key = (pointing_up, color, step)
    surf = _statusArrowCache.get(key)
    if surf is None:
        base = _statusArrowSurface(pointing_up, color)
        arrowWidth, arrowHeight = base.get_size()
        scaleFactor = step / 20
        surf = pygame.transform.smoothscale(base, (max(1, round(arrowWidth * scaleFactor)), max(1, round(arrowHeight * scaleFactor))))
        _statusArrowCache[key] = surf
    return surf

def _statusArrowLayout(popup):
    """The volley's fixed per-arrow layout, built once per popup: a list of (xFraction, delayFraction, sizeScale)."""
    arrows = popup.get("arrows")
    if arrows is None:
        rng = random.Random(id(popup))
        arrows = []
        for col in range(STATUS_ARROW_COLUMNS):
            # column center, spread evenly over STATUS_ARROW_WIDTH_SPAN of the sprite's width
            base = ((col + 0.5) / STATUS_ARROW_COLUMNS - 0.5) * STATUS_ARROW_WIDTH_SPAN
            for row in range(STATUS_ARROW_PER_COLUMN):
                x = base + rng.uniform(-0.02, 0.02)
                arrowCount = STATUS_ARROW_COLUMNS * STATUS_ARROW_PER_COLUMN
                idx = col * STATUS_ARROW_PER_COLUMN + row
                delay = (idx / max(1, arrowCount - 1)) * STATUS_ARROW_MAX_DELAY
                arrows.append((x, delay, rng.uniform(*STATUS_ARROW_SIZE_RANGE)))
        popup["arrows"] = arrows
    return arrows

def drawStatusArrowPopups(window, popups):
    for popup in popups:
        popupProgress = min(1.0, popup["elapsed"] / STATUS_ARROW_DURATION)
        if popup["kind"] == "cleanse":
            _drawCleanseSparkles(window, popup, popupProgress)
            continue
        isBuff = popup["kind"] == "buff"
        color = STATUS_ARROW_BUFF_COLOR if isBuff else STATUS_ARROW_DEBUFF_COLOR
        rect = popup["sprite"]["stats"].rect
        travel = rect.height * STATUS_ARROW_TRAVEL_FRAC

        for xFrac, delay, sizeScale in _statusArrowLayout(popup):
            local = (popupProgress - delay) / STATUS_ARROW_LIFE
            if local < 0 or local > 1:
                continue

            surf = _scaledStatusArrow(isBuff, color, sizeScale)

            # A buff's arrows start low on the body and climb; a debuff's start high and sink.
            if isBuff:
                y = rect.bottom - rect.height * 0.15 - travel * local
            else:
                y = rect.top + rect.height * 0.2 + travel * local
            x = rect.centerx + xFrac * rect.width

            if local < STATUS_ARROW_FADE_IN:
                alpha = local / STATUS_ARROW_FADE_IN
            elif local > STATUS_ARROW_FADE_START:
                alpha = 1 - (local - STATUS_ARROW_FADE_START) / (1 - STATUS_ARROW_FADE_START)
            else:
                alpha = 1.0
            if alpha < 1.0:
                surf = surf.copy()
                surf.set_alpha(max(0, round(255 * alpha)))

            window.blit(surf, surf.get_rect(center=(round(x), round(y))))


# ---------- Combo readout ----------

COMBO_PULSE_DURATION = 220            # ms, per-hit punch decay
COMBO_PULSE_PUNCH_SCALE = 1.45        # how big a single hit's punch overshoots
COMBO_FINISH_HOLD = 450
COMBO_FINISH_FADE = 500
COMBO_FINISH_POP_SCALE = 1.7          # overshoot on the very last hit
COMBO_GAP = 10

COMBO_TRIANGLE_MIN_WIDTH = 70
COMBO_RAMP_THICKNESS = 22             # px, visual thickness of the wedge itself
COMBO_RAMP_TEXT_GAP = 4
COMBO_RAMP_SIDE_PAD = 10
COMBO_TRIANGLE_COLOR = (255, 200, 60, 235)
COMBO_TRIANGLE_OUTLINE = (45, 30, 0)
COMBO_TRIANGLE_OUTLINE_WIDTH = 3

COMBO_SIDE_GAP = 12

def updateComboDisplays(combos, dt):
    for combo in combos[:]:
        combo["pulse"] += dt
        if combo["finished"]:
            combo["finishedElapsed"] += dt
            if combo["finishedElapsed"] >= COMBO_FINISH_HOLD + COMBO_FINISH_FADE:
                combos.remove(combo)

_comboTotalTextCache = {}

def _comboTotalTextSurface(text, step):
    """Same yellow->red gradient/outline treatment as _damageTextSurface."""
    key = (text, step)
    surf = _comboTotalTextCache.get(key)
    if surf is not None:
        return surf
    if len(_comboTotalTextCache) >= 256:
        _comboTotalTextCache.clear()

    base = COMBO_TOTAL_FONT.render(text, True, (255, 255, 255))
    textWidth, textHeight = base.get_size()

    shift = step / max(1, DAMAGE_POPUP_GRADIENT_STEPS - 1)
    gradient = pygame.Surface((textWidth, textHeight))
    for y in range(textHeight):
        colorBlend = min(1.0, (y / textHeight) * 0.7 + shift * 0.7)
        color = tuple(round(fromChannel + (toChannel - fromChannel) * colorBlend) for fromChannel, toChannel in zip(DAMAGE_POPUP_YELLOW, DAMAGE_POPUP_RED))
        pygame.draw.line(gradient, color, (0, y), (textWidth, y))
    base.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    outlineSize = DAMAGE_POPUP_OUTLINE
    surf = pygame.Surface((textWidth + 2 * outlineSize, textHeight + 2 * outlineSize), pygame.SRCALPHA)
    outline = COMBO_TOTAL_FONT.render(text, True, DAMAGE_POPUP_OUTLINE_COLOR)
    for dx in (-outlineSize, 0, outlineSize):
        for dy in (-outlineSize, 0, outlineSize):
            if dx or dy:
                surf.blit(outline, (outlineSize + dx, outlineSize + dy))
    surf.blit(base, (outlineSize, outlineSize))
    _comboTotalTextCache[key] = surf
    return surf

def _comboPulseScale(pulseMs):
    """Decays from a punchy overshoot back down to 1.0 over COMBO_PULSE_DURATION."""
    pulseProgress = min(1.0, pulseMs / COMBO_PULSE_DURATION)
    return 1.0 + (COMBO_PULSE_PUNCH_SCALE - 1.0) * (1 - pulseProgress) ** 2

def _comboBadgeSize(hitsSurf, totalSurf):
    """Just the _comboBadge would build for this pair of text surfaces, without actually drawing anything."""
    contentWidth = hitsSurf.get_width() + COMBO_GAP + totalSurf.get_width()
    width = max(COMBO_TRIANGLE_MIN_WIDTH, contentWidth + 2 * COMBO_RAMP_SIDE_PAD)
    topMargin = totalSurf.get_height() + COMBO_RAMP_TEXT_GAP
    height = topMargin + COMBO_RAMP_THICKNESS
    return width, height

def comboBadgeWidth(combo):
    """The on-screen width drawComboDisplays will draw this combo's badge at, before any pulse/finish-pop scaling."""
    hitsSurf = _outlinedText(COMBO_HITS_FONT, f"x{combo['hits']}", (255, 255, 255))
    totalSurf = _comboTotalTextSurface(str(round(combo["total"])), 0)  # step only affects color, not size
    width, _ = _comboBadgeSize(hitsSurf, totalSurf)
    return width

def _comboBadge(hitsSurf, totalSurf):
    """One combined badge: a long, low wedge with both texts riding on top of its rising hypotenuse rather than embedded inside the fill."""
    width, height = _comboBadgeSize(hitsSurf, totalSurf)
    topMargin = height - COMBO_RAMP_THICKNESS

    surf = pygame.Surface((width, height), pygame.SRCALPHA)

    points = [(0, height), (width, height), (width, topMargin)]
    pygame.draw.polygon(surf, COMBO_TRIANGLE_COLOR, points)
    pygame.draw.polygon(surf, COMBO_TRIANGLE_OUTLINE, points, COMBO_TRIANGLE_OUTLINE_WIDTH)

    totalCenterX = width - COMBO_RAMP_SIDE_PAD - totalSurf.get_width() / 2
    hitsCenterX = totalCenterX - totalSurf.get_width() / 2 - COMBO_GAP - hitsSurf.get_width() / 2

    for textSurf, centerX in ((hitsSurf, hitsCenterX), (totalSurf, totalCenterX)):
        lineY = height - COMBO_RAMP_THICKNESS * (centerX / width)
        rect = textSurf.get_rect(midbottom=(round(centerX), round(lineY - COMBO_RAMP_TEXT_GAP)))
        surf.blit(textSurf, rect)

    return surf

def drawComboDisplays(window, combos):
    """No background panel."""
    for combo in combos:
        target = combo["target"]
        rect = target["stats"].rect

        step = min(DAMAGE_POPUP_GRADIENT_STEPS - 1,
                   int((combo["hits"] / max(1, combo["ticks"])) * DAMAGE_POPUP_GRADIENT_STEPS))

        hitsSurf = _outlinedText(COMBO_HITS_FONT, f"x{combo['hits']}", (255, 255, 255))
        totalSurf = _comboTotalTextSurface(str(round(combo["total"])), step)
        badgeSurf = _comboBadge(hitsSurf, totalSurf)

        scale = _comboPulseScale(combo["pulse"])
        alpha = 255
        floatOffset = 0

        if combo["finished"]:
            finishedMs = combo["finishedElapsed"]
            if finishedMs < COMBO_FINISH_HOLD:
                finishProgress = finishedMs / COMBO_FINISH_HOLD
                scale = max(scale, 1.0 + (COMBO_FINISH_POP_SCALE - 1.0) * (1 - finishProgress) ** 2)
            else:
                fadeT = (finishedMs - COMBO_FINISH_HOLD) / COMBO_FINISH_FADE
                alpha = max(0, round(255 * (1 - fadeT)))
                floatOffset = 30 * fadeT   # drifts further outward as it fades out

        if scale != 1.0:
            size = (max(1, round(badgeSurf.get_width() * scale)), max(1, round(badgeSurf.get_height() * scale)))
            badgeSurf = pygame.transform.smoothscale(badgeSurf, size)

        if alpha < 255:
            badgeSurf = badgeSurf.copy()
            badgeSurf.set_alpha(alpha)

        # Always to the right of the target, outside its sprite, vertically centered on it.
        groupLeft = (rect.right + COMBO_SIDE_GAP + floatOffset) - 50
        badgeRect = badgeSurf.get_rect(midleft=(round(groupLeft), round(rect.centery)))

        window.blit(badgeSurf, badgeRect)

# ---------- Outlined text helper ----------
_outlineTextCache = {}

def _outlinedText(font, text, color, outlineColor=DAMAGE_POPUP_OUTLINE_COLOR, outline=DAMAGE_POPUP_OUTLINE):
    """Small helper for a plain outlined text surface, cached like _damageTextSurface."""
    key = (font, text, color, outlineColor, outline)
    surf = _outlineTextCache.get(key)
    if surf is not None:
        return surf
    if len(_outlineTextCache) >= 128:
        _outlineTextCache.clear()

    base = font.render(text, True, color)
    outlineSize = outline
    surf = pygame.Surface((base.get_width() + 2 * outlineSize, base.get_height() + 2 * outlineSize), pygame.SRCALPHA)
    outlineSurf = font.render(text, True, outlineColor)
    for dx in (-outlineSize, 0, outlineSize):
        for dy in (-outlineSize, 0, outlineSize):
            if dx or dy:
                surf.blit(outlineSurf, (outlineSize + dx, outlineSize + dy))
    surf.blit(base, (outlineSize, outlineSize))
    _outlineTextCache[key] = surf
    return surf


# ---------- Death animation ----------
# When a character is defeated their sprite crumbles away block by block and each missing piece
# lifts off as a little flier carrying that spot's colour:
#   players (side "left")   -> BUTTERFLIES: bright, graceful, slow wingbeats, drifting up
#   enemies (side "right")  -> GAMO-GAMO (moths): dusty brown/cream, fast flutter, jittery zig-zag
# Everything is drawn in code (no new art needed). Times are in ms, same dt the battle loop uses.
#
# battle_ui.py hooks:
#   updateDeathAnimations(sprites, dt)   once per frame, next to updateHitFlashes
#   drawDeadSprite(window, sprite)       instead of drawChar for a dead sprite
#   drawDeathFliers(window, sprites)     after all sprites are drawn, so fliers sit on top

DISSOLVE_MS = 1150            # how long the sprite takes to crumble away
SHADOW_FADE_FROM = 0.55       # fraction of the dissolve after which the foot shadow starts fading
BASE_SHADOW_ALPHA = 90        # must match drawCharacterShadow's default

MOTH_COLORS = [(196, 178, 140), (168, 148, 116), (212, 206, 188), (138, 120, 98), (184, 160, 120)]


def _clamp(value, low, high):
    return max(low, min(high, value))


def _vivid(color):
    """Pushes a sampled sprite colour toward a saturated, bright butterfly colour (with a little hue wobble)."""
    red, green, blue = color[:3]
    hue, saturation, brightness = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    hue = (hue + random.uniform(-0.04, 0.04)) % 1.0
    saturation = max(saturation, 0.55)
    brightness = max(brightness, 0.85)
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return (int(red * 255), int(green * 255), int(blue * 255))


def _shade(color, factor):
    return tuple(_clamp(int(channel * factor), 0, 255) for channel in color[:3])


# ---------- One flier ----------
class _Flier:
    def __init__(self, x, y, color, kind, size):
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.size = size
        self.age = 0.0
        self.phase = random.uniform(0, math.tau)
        self.seed = random.uniform(0, math.tau)
        self.angle = 0.0
        if kind == "butterfly":
            self.color = _vivid(color)
            self.life = random.uniform(1700, 2600)
            self.flapSpeed = random.uniform(0.020, 0.028)         # rad/ms  (~3-4.5 wingbeats a second)
            self.vx = random.uniform(-35, 35)
            self.vy = random.uniform(-70, -35)
        else:
            self.color = random.choice(MOTH_COLORS)
            self.life = random.uniform(1400, 2300)
            self.flapSpeed = random.uniform(0.042, 0.055)         # moths flutter much faster
            self.vx = random.uniform(-60, 60)
            self.vy = random.uniform(-60, -20)
            self.targetVx, self.targetVy = self.vx, self.vy
            self.retarget = random.uniform(80, 220)

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        self.age += dt
        self.phase += self.flapSpeed * dt
        deltaSeconds = dt / 1000.0
        if self.kind == "butterfly":
            sway = math.sin(self.age * 0.004 + self.seed) * 45          # lazy side-to-side drift
            bob = math.sin(self.age * 0.009 + self.seed) * 18           # little up/down flutter
            self.x += (self.vx + sway) * deltaSeconds
            self.y += (self.vy + bob) * deltaSeconds
            self.vy -= 8 * deltaSeconds                                            # slowly speeds up skyward
            self.angle = _clamp(-(self.vx + sway) * 0.35, -25, 25)
        else:
            # Erratic: keep choosing a new jittery heading, mostly drifting up toward "the light".
            self.retarget -= dt
            if self.retarget <= 0:
                self.retarget = random.uniform(80, 220)
                self.targetVx = random.uniform(-110, 110)
                self.targetVy = random.uniform(-120, 15) if random.random() < 0.85 else random.uniform(20, 50)
            smoothing = min(1.0, dt / 90.0)
            self.vx += (self.targetVx - self.vx) * smoothing
            self.vy += (self.targetVy - self.vy) * smoothing
            self.x += self.vx * deltaSeconds
            self.y += self.vy * deltaSeconds
            self.angle = _clamp(-self.vx * 0.3, -35, 35)

    def draw(self, window):
        fadeStart = self.life * 0.65
        alpha = 255
        if self.age > fadeStart:
            alpha = int(255 * max(0.0, 1 - (self.age - fadeStart) / (self.life - fadeStart)))
        if alpha <= 0:
            return
        bodyWidth = self.size
        side = int(bodyWidth * 3) | 1
        surf = pygame.Surface((side, side), pygame.SRCALPHA)
        cx = cy = side // 2
        flap = 0.22 + 0.78 * abs(math.cos(self.phase))              # 1 = wings open flat, small = wings edge-on
        if self.kind == "butterfly":
            self._drawButterfly(surf, cx, cy, bodyWidth, flap)
        else:
            self._drawMoth(surf, cx, cy, bodyWidth, flap)
        if abs(self.angle) > 2:
            surf = pygame.transform.rotate(surf, self.angle)
        if alpha < 255:
            surf.set_alpha(alpha)
        window.blit(surf, surf.get_rect(center=(round(self.x), round(self.y))))

    # --- butterfly: rounded two-part wings with a pale spot, dark outline, thin body + antennae ---
    def _drawButterfly(self, surf, cx, cy, wingSpan, flapFactor):
        outline = _shade(self.color, 0.45)
        lower = _shade(self.color, 0.85)
        spot = (255, 255, 255)
        flappedWidth = max(2, int(wingSpan * flapFactor))
        for sign in (-1, 1):
            left = cx if sign > 0 else cx - flappedWidth
            upper = pygame.Rect(left, int(cy - wingSpan), flappedWidth, int(wingSpan * 0.95))
            low = pygame.Rect(cx if sign > 0 else cx - int(flappedWidth * 0.75), int(cy - wingSpan * 0.05), max(2, int(flappedWidth * 0.75)), int(wingSpan * 0.7))
            pygame.draw.ellipse(surf, lower, low)
            pygame.draw.ellipse(surf, outline, low, 1)
            pygame.draw.ellipse(surf, self.color, upper)
            pygame.draw.ellipse(surf, outline, upper, 1)
            if flapFactor > 0.45:
                pygame.draw.circle(surf, spot, (int(cx + sign * flappedWidth * 0.55), int(cy - wingSpan * 0.5)), max(1, int(wingSpan * 0.16)))
        body = pygame.Rect(0, 0, max(2, int(wingSpan * 0.22)), int(wingSpan * 1.1))
        body.midtop = (cx, int(cy - wingSpan * 0.65))
        pygame.draw.ellipse(surf, (35, 25, 40), body)
        top = (cx, int(cy - wingSpan * 0.62))
        for sign in (-1, 1):
            pygame.draw.line(surf, (35, 25, 40), top, (int(cx + sign * wingSpan * 0.35), int(cy - wingSpan * 1.05)), 1)

    # --- gamo-gamo (moth): swept-back angular wings, fuzzy dusty colour, eye-spot, plump body, feathery antennae ---
    def _drawMoth(self, surf, cx, cy, wingSpan, flapFactor):
        dark = _shade(self.color, 0.6)
        light = _shade(self.color, 1.12)
        for sign in (-1, 1):
            flappedWidth = wingSpan * 1.15 * flapFactor
            upper = [(cx, cy - wingSpan * 0.35), (cx + sign * flappedWidth, cy - wingSpan * 0.6),
                     (cx + sign * flappedWidth * 0.95, cy + wingSpan * 0.2), (cx, cy + wingSpan * 0.1)]
            pygame.draw.polygon(surf, self.color, [(int(x), int(y)) for x, y in upper])
            pygame.draw.polygon(surf, dark, [(int(x), int(y)) for x, y in upper], 1)
            # darker wing-tip band and an eye-spot
            band = [(cx + sign * flappedWidth * 0.6, cy - wingSpan * 0.52), (cx + sign * flappedWidth, cy - wingSpan * 0.6),
                    (cx + sign * flappedWidth * 0.95, cy + wingSpan * 0.2), (cx + sign * flappedWidth * 0.6, cy + wingSpan * 0.14)]
            pygame.draw.polygon(surf, dark, [(int(x), int(y)) for x, y in band])
            if flapFactor > 0.4:
                pygame.draw.circle(surf, light, (int(cx + sign * flappedWidth * 0.38), int(cy - wingSpan * 0.22)), max(1, int(wingSpan * 0.17)))
                pygame.draw.circle(surf, dark, (int(cx + sign * flappedWidth * 0.38), int(cy - wingSpan * 0.22)), max(1, int(wingSpan * 0.08)))
        body = pygame.Rect(0, 0, max(3, int(wingSpan * 0.34)), int(wingSpan * 1.15))
        body.midtop = (cx, int(cy - wingSpan * 0.55))
        pygame.draw.ellipse(surf, light, body)
        pygame.draw.ellipse(surf, dark, body, 1)
        top = (cx, int(cy - wingSpan * 0.5))
        for sign in (-1, 1):
            tip = (int(cx + sign * wingSpan * 0.45), int(cy - wingSpan * 1.0))
            pygame.draw.line(surf, dark, top, tip, 1)
            for barbPosition in (0.4, 0.7):        # little feathery barbs
                barbX = int(top[0] + (tip[0] - top[0]) * barbPosition)
                barbY = int(top[1] + (tip[1] - top[1]) * barbPosition)
                pygame.draw.line(surf, dark, (barbX, barbY), (barbX + sign * 2, barbY - 1), 1)


# ---------- The whole death of one sprite ----------
class DeathAnim:
    def __init__(self, sprite):
        stats = sprite["stats"]
        self.kind = "butterfly" if sprite.get("side") == "left" else "moth"
        self.src = stats.image.copy()
        self.image = stats.image.copy()
        self.origin = stats.rect.topleft
        self.elapsed = 0.0
        self.fliers = []
        self.shadowSprite = sprite

        imageWidth, imageHeight = self.src.get_size()
        self.block = _clamp(round(max(imageWidth, imageHeight) / 40), 4, 10)
        blockSize = self.block

        # Every opaque block, ordered so the sprite erodes from the top down (with plenty of randomness).
        blocks = []
        for blockY in range(0, imageHeight, blockSize):
            for blockX in range(0, imageWidth, blockSize):
                if self._opaque(blockX, blockY, blockSize, imageWidth, imageHeight):
                    blocks.append((0.65 * blockY / max(1, imageHeight) + 0.35 * random.random(), blockX, blockY))
        blocks.sort()
        self.blocks = blocks
        self.nextBlock = 0

        wanted = _clamp(imageHeight // 12, 10, 22)
        self.spawnEvery = max(1, len(blocks) // wanted)
        self.fliersSize = _clamp(imageHeight * 0.085, 9, 22)

    def _opaque(self, blockX, blockY, blockSize, imageWidth, imageHeight):
        for dx, dy in ((blockSize // 2, blockSize // 2), (1, 1), (blockSize - 1, 1), (1, blockSize - 1), (blockSize - 1, blockSize - 1)):
            x, y = min(imageWidth - 1, blockX + dx), min(imageHeight - 1, blockY + dy)
            if self.src.get_at((x, y)).a > 20:
                return True
        return False

    @property
    def progress(self):
        dissolveProgress = _clamp(self.elapsed / DISSOLVE_MS, 0.0, 1.0)
        return dissolveProgress * dissolveProgress * (3 - 2 * dissolveProgress)           # smoothstep: slow start, quick middle, soft end

    @property
    def spriteGone(self):
        return self.nextBlock >= len(self.blocks)

    @property
    def finished(self):
        return self.spriteGone and not self.fliers

    def update(self, dt):
        self.elapsed += dt
        total = len(self.blocks)
        target = int(self.progress * total) if self.elapsed < DISSOLVE_MS else total
        blockSize = self.block
        while self.nextBlock < target:
            _, blockX, blockY = self.blocks[self.nextBlock]
            if self.nextBlock % self.spawnEvery == 0:
                cx = min(self.src.get_width() - 1, blockX + blockSize // 2)
                cy = min(self.src.get_height() - 1, blockY + blockSize // 2)
                color = self.src.get_at((cx, cy))
                if color.a < 20:
                    color = pygame.Color(200, 200, 200, 255)
                self.fliers.append(_Flier(self.origin[0] + cx, self.origin[1] + cy,
                                          (color.r, color.g, color.b), self.kind,
                                          self.fliersSize * random.uniform(0.8, 1.25)))
            self.image.fill((0, 0, 0, 0), pygame.Rect(blockX, blockY, blockSize, blockSize))
            self.nextBlock += 1
        for flier in self.fliers:
            flier.update(dt)
        self.fliers = [flier for flier in self.fliers if flier.alive]

    def drawBody(self, window):
        if self.spriteGone:
            return
        dissolveProgress = self.progress
        if dissolveProgress > SHADOW_FADE_FROM:
            fade = 1 - (dissolveProgress - SHADOW_FADE_FROM) / (1 - SHADOW_FADE_FROM)
        else:
            fade = 1.0
        alpha = int(BASE_SHADOW_ALPHA * fade) // 6 * 6     # stepped so the shadow cache stays small
        if alpha > 0:
            drawCharacterShadow(window, self.shadowSprite, alpha=alpha)
        window.blit(self.image, self.origin)

    def drawFliers(self, window):
        for flier in self.fliers:
            flier.draw(window)


# ---------- Hooks for the battle loop ----------
def updateDeathAnimations(sprites, dt):
    """Call once per frame. Starts the animation the first frame a sprite is dead, wherever that death was flagged."""
    for sprite in sprites:
        if not sprite.get("dead"):
            sprite.pop("deathAnim", None)      # revived / fresh battle: nothing to show
            continue
        anim = sprite.get("deathAnim")
        if anim is None:
            anim = sprite["deathAnim"] = DeathAnim(sprite)
            playDeathSound(anim.kind)         # butterfly chimes for a player, gamugamo rustle for an enemy
        if not anim.finished:
            anim.update(dt)


def drawDeadSprite(window, sprite):
    """Replaces drawChar for a dead sprite: crumbling body only (bars and status icons vanish at death)."""
    anim = sprite.get("deathAnim")
    if anim is not None:
        anim.drawBody(window)


def drawDeathFliers(window, sprites):
    """Butterflies / gamo-gamo, drawn over every sprite."""
    for sprite in sprites:
        anim = sprite.get("deathAnim")
        if anim is not None:
            anim.drawFliers(window)


# ---------- Boss fight effects ----------
# Screen-space post effects for boss stages (battle_ui calls bossFx.apply(window, dt) right after the camera
# is presented and before the HUD, so cards / buttons / log stay crisp):
#   - heat-wave ripple: every horizontal strip of the screen sways sideways a couple of pixels
#   - pulsing blood-red vignette that beats like a heartbeat
#   - rising embers
#   - random GLITCH bursts (every 2.5-5 s, ~0.2 s): RGB split, torn strips, vignette flashes full
class BossFX:
    STRIP = 8
    GLITCH_EVERY = (2500, 5000)
    GLITCH_LENGTH = (140, 260)
    RGB_SPLIT = 7
    EMBER_COUNT = 28

    def __init__(self, size):
        self.w, self.h = size
        self.t = 0.0
        self.glitchIn = random.uniform(*self.GLITCH_EVERY)
        self.glitchLeft = 0.0
        self.vignette = self._buildVignette()
        self.embers = [self._newEmber(True) for _ in range(self.EMBER_COUNT)]

    def _buildVignette(self):
        surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        steps, ring = 60, 3
        for i in range(steps):
            alpha = int(150 * (1 - i / steps) ** 2)
            rect = pygame.Rect(i * ring, i * ring, self.w - 2 * i * ring, self.h - 2 * i * ring)
            if rect.width <= 0 or rect.height <= 0:
                break
            pygame.draw.rect(surf, (150, 10, 20, alpha), rect, ring)
        return surf

    def _newEmber(self, anywhere=False):
        return {
            "x": random.uniform(0, self.w),
            "y": random.uniform(0, self.h) if anywhere else self.h + random.uniform(0, 40),
            "speed": random.uniform(25, 70),
            "size": random.choice((1, 1, 2, 2, 3)),
            "phase": random.uniform(0, math.tau),
            "color": random.choice(((255, 120, 40), (255, 170, 60), (220, 60, 30))),
        }

    def apply(self, window, dt):
        self.t += dt
        if self.glitchLeft > 0:
            self.glitchLeft -= dt
        else:
            self.glitchIn -= dt
            if self.glitchIn <= 0:
                self.glitchLeft = random.uniform(*self.GLITCH_LENGTH)
                self.glitchIn = random.uniform(*self.GLITCH_EVERY)
        glitching = self.glitchLeft > 0

        # --- heat-wave ripple (+ torn strips while glitching) ---
        screenCopy = window.copy()
        waveAmplitude = 2.2 + 0.8 * math.sin(self.t * 0.002)
        for y in range(0, self.h, self.STRIP):
            if glitching and random.random() < 0.16:
                offset = random.choice((-1, 1)) * random.randint(14, 42)
            else:
                offset = round(waveAmplitude * math.sin(self.t * 0.004 + y * 0.03))
            if offset:
                window.blit(screenCopy, (offset, y), pygame.Rect(0, y, self.w, self.STRIP))   # gaps keep the original pixels

        # --- RGB split (glitch only: it costs a few full-screen blits) ---
        if glitching:
            base = window.copy()
            window.fill((0, 0, 0))
            for mask, dx in (((255, 0, 0), -self.RGB_SPLIT), ((0, 255, 0), 0), ((0, 0, 255), self.RGB_SPLIT)):
                channel = base.copy()
                channel.fill(mask, special_flags=pygame.BLEND_RGB_MULT)
                window.blit(channel, (dx, 0), special_flags=pygame.BLEND_RGB_ADD)

        # --- heartbeat vignette ---
        beat = abs(math.sin(self.t * 0.0035)) ** 6
        self.vignette.set_alpha(255 if glitching else int(255 * (0.45 + 0.55 * beat)))
        window.blit(self.vignette, (0, 0))

        # --- embers ---
        deltaSeconds = dt / 1000.0
        for ember in self.embers:
            ember["y"] -= ember["speed"] * deltaSeconds
            ember["x"] += math.sin(self.t * 0.003 + ember["phase"]) * 18 * deltaSeconds
            if ember["y"] < -10:
                ember.update(self._newEmber())
            pygame.draw.circle(window, ember["color"], (int(ember["x"]), int(ember["y"])), ember["size"])