import math
import pygame
import random
import sys
from entities import CHARACTER
from voice import playHurtVoice
from classes import stun, EffectDef, EFFECT_REVERTS, EFFECT_VISUAL_KIND, EFFECT_TICKS, EFFECT_COUNTDOWN_NEXT_ROUND, SANITY_TICK_EFFECTS, EFFECT_PERCENT_OF_DAMAGE, effectStrength

# ---------- Fonts ----------
pygame.font.init()
FONT = pygame.font.Font('assets/font/monogram.ttf', 20)
BIG_FONT = pygame.font.Font('assets/font/monogram.ttf', 60)
DAMAGE_POPUP_FONT = pygame.font.Font('assets/font/monogram.ttf', 60)
COMBO_HITS_FONT = pygame.font.Font('assets/font/monogram.ttf', 32)
COMBO_TOTAL_FONT = pygame.font.Font('assets/font/monogram.ttf', 72)
STATUS_ICON_FONT = pygame.font.Font('assets/font/monogram.ttf', 14)

# ---------- Drawing ----------

def drawBg(window, background_img):
    window.blit(background_img, (0, 0))

HP_TEXT_GAP = 3   # px between a bar and the text beside it

_barTextCache = {}

def barText(text, color=(255, 255, 255), font=None):
    """Horizontal label with a 1px drop shadow so it stays legible over the battlefield."""
    font = font or FONT
    key = (text, color, id(font))
    surf = _barTextCache.get(key)
    if surf is None:
        if len(_barTextCache) >= 256:
            _barTextCache.clear()
        front = font.render(text, True, color)
        shadow = font.render(text, True, (0, 0, 0))
        surf = pygame.Surface((front.get_width() + 1, front.get_height() + 1), pygame.SRCALPHA)
        surf.blit(shadow, (1, 1))
        surf.blit(front, (0, 0))
        _barTextCache[key] = surf
    return surf

def hpLabel(currentHp):
    return barText(str(max(0, round(currentHp))))

def sanityLabel(sanity):
    return barText(str(round(max(0, min(sanity, 1)) * 100)))

# ---------- Stat bar smoothing (HP / sanity) ----------

STAT_BAR_LERP_RATE = 4.0
STAT_BAR_MAX_DT = 40

def lerpValue(current, target, dt, rate=STAT_BAR_LERP_RATE):
    """Frame-rate independent smoothing of a single number toward `target`, same exponential-decay shape as lerpCameraZoom/lerpPoint."""
    dt = min(dt, STAT_BAR_MAX_DT)
    blendFactor = 1 - math.exp(-rate * dt / 1000)
    newValue = current + (target - current) * blendFactor
    if abs(target - newValue) < 0.01:
        return target
    return newValue

def updateStatBars(sprites, dt):
    """Call once per frame, before drawing."""
    for sprite in sprites:
        stats = sprite["stats"]
        sprite["displayHp"] = lerpValue(sprite.get("displayHp", stats.hp), stats.hp, dt)
        targetSanity = sprite.get("sanity", 0.5)
        sprite["displaySanity"] = lerpValue(sprite.get("displaySanity", targetSanity), targetSanity, dt)

# ---------- Health and sanity bars ----------
HP_BAR_COLOR = (0, 200, 0)
HP_BAR_DRAIN_COLOR = (210, 50, 50)
HP_BAR_DRAIN_EPSILON = 0.5

def drawHealthBar(window, x, y, width, height, currentHp, maxHp, draining=False):
    ratio = max(0, min(currentHp / maxHp, 1))
    filled_height = height * ratio
    fill_y = y + (height - filled_height)
    color = HP_BAR_DRAIN_COLOR if draining else HP_BAR_COLOR
    pygame.draw.rect(window, (60, 60, 60), (x, y, width, height))
    pygame.draw.rect(window, color, (x, fill_y, width, filled_height))
    pygame.draw.rect(window, (0, 0, 0), (x, y, width, height), 2)

SANITY_LOW_COLOR = (210, 50, 50)     # below 0.5
SANITY_HIGH_COLOR = (60, 130, 255)   # 0.5 and above
SANITY_MID_TICK_COLOR = (255, 255, 255)
SANITY_BAR_GAP = 4

def drawSanityBar(window, x, y, width, height, sanity):
    """Vertical gauge next to the health bar, 0..1."""
    ratio = max(0, min(sanity, 1))
    filled_height = height * ratio
    fill_y = y + (height - filled_height)
    color = SANITY_HIGH_COLOR if ratio >= 0.5 else SANITY_LOW_COLOR
    pygame.draw.rect(window, (60, 60, 60), (x, y, width, height))
    pygame.draw.rect(window, color, (x, fill_y, width, filled_height))
    midY = y + height * 0.5
    pygame.draw.line(window, SANITY_MID_TICK_COLOR, (x, midY), (x + width, midY), 1)
    pygame.draw.rect(window, (0, 0, 0), (x, y, width, height), 2)


# ---------- Image caches (faded / cutout / shadow) ----------
_CACHE_LIMIT = 256
_fadedCache = {}
_cutoutCache = {}
_shadowCache = {}

def _cachedPerImage(cache, image, build):
    cachedResult = cache.get(id(image))
    if cachedResult is None or cachedResult[0] is not image:     # hit[0] check guards against id() reuse
        if len(cache) >= _CACHE_LIMIT:
            cache.clear()
        cachedResult = (image, build(image))
        cache[id(image)] = cachedResult
    return cachedResult[1]

def _buildCutout(image):
    """A same-size stencil of `image`: fully transparent where the sprite is opaque, opaque white everywhere else."""
    mask = pygame.mask.from_surface(image, 10)
    mask.invert()
    return mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))

def _buildFaded(image):
    faded = image.copy()
    faded.set_alpha(120)
    return faded

def prewarmImageCaches(idleAnimations):
    """Pre-builds the faded copy and glow stencil for every idle-animation frame."""
    for anim in idleAnimations.values():
        for frame in anim.framesObj.frames:
            _cachedPerImage(_fadedCache, frame, _buildFaded)
            _cachedPerImage(_cutoutCache, frame, _buildCutout)

# ---------- Character glow (the highlight) ----------

GLOW_COLUMN_HEIGHT_FACTOR = 0.55
GLOW_COLUMN_PEAK_ALPHA = 150
GLOW_COLUMN_FALLOFF = 1.6
GLOW_BASE_ALPHAS = (70, 70, 80)
GLOW_PULSE = 0.10                  # gentle breathing, 0 for a steady glow
GLOW_PULSE_SPEED = 0.005           # radians per ms

_glowCache = {}

# The finished glow.
_stencilGlowCache = {}
_STENCIL_GLOW_CACHE_LIMIT = 384

def _buildGlow(width, ovalHeight, height, color):
    """`width` x `ovalHeight` is the shadow oval itself; `height` is how far the gradient rises above its middle."""
    totalHeight = height + ovalHeight
    baseY = height + ovalHeight // 2
    rgb = tuple(color[:3])

    # vertical gradient: rows fade from PEAK at the shadow up to 0 at the top
    column = pygame.Surface((width, totalHeight), pygame.SRCALPHA)
    for y in range(baseY):
        alpha = int(GLOW_COLUMN_PEAK_ALPHA * ((y / baseY) ** GLOW_COLUMN_FALLOFF))
        if alpha > 0:
            pygame.draw.line(column, (*rgb, alpha), (0, y), (width, y))

    # soften the left/right edges so it reads as a glow, not a rectangle
    edgeMask = pygame.Surface((width, totalHeight), pygame.SRCALPHA)
    for x in range(width):
        edgeDistance = abs((x + 0.5) / width * 2 - 1)   # 0 at the centre, 1 at the edges
        glowAlpha = int(255 * max(0.0, 1 - edgeDistance * edgeDistance))
        pygame.draw.line(edgeMask, (255, 255, 255, glowAlpha), (x, 0), (x, totalHeight))
    column.blit(edgeMask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    surf = pygame.Surface((width, totalHeight), pygame.SRCALPHA)
    surf.blit(column, (0, 0))

    # the shadow oval itself, lit up: nested ovals, brightest in the middle
    for i, alpha in enumerate(GLOW_BASE_ALPHAS):
        shrink = 1 - i * 0.25
        glowWidth = max(2, int(width * shrink))
        glowHeight = max(2, int(ovalHeight * shrink))
        layer = pygame.Surface((width, totalHeight), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (*rgb, alpha),
                            pygame.Rect((width - glowWidth) // 2, height + (ovalHeight - glowHeight) // 2, glowWidth, glowHeight))
        surf.blit(layer, (0, 0))
    return surf

def drawCharacterGlow(window, sprite, color, strength=1.0, rect=None, image=None):
    """The one highlight for a character: their foot shadow glowing in `color`, with a gradient fading upward out of it."""
    if sprite.get("dead"):
        return      # a defeated sprite is crumbling into butterflies / moths: no highlight on it
    stats = sprite["stats"]
    rect = stats.rect if rect is None else rect
    image = stats.image if image is None else image

    # exactly drawCharacterShadow's oval
    width = max(8, int(rect.width * 0.45))
    ovalHeight = max(4, int(width * 0.25))
    height = max(8, int(rect.height * GLOW_COLUMN_HEIGHT_FACTOR))

    key = (width, ovalHeight, height, tuple(color[:3]))
    glow = _glowCache.get(key)
    if glow is None:
        if len(_glowCache) >= 64:
            _glowCache.clear()
        glow = _buildGlow(width, ovalHeight, height, color)
        _glowCache[key] = glow

    shadowCenter = (rect.centerx + 5, rect.bottom - ovalHeight * 0.45)
    glowRect = glow.get_rect(midbottom=(int(shadowCenter[0]), int(shadowCenter[1] + ovalHeight / 2)))

    # the glow with the model's silhouette punched out -- built once per, then reused
    offset = (rect.left - glowRect.left, rect.top - glowRect.top)
    stencilKey = (id(image), key, offset)
    cachedGlow = _stencilGlowCache.get(stencilKey)
    if cachedGlow is None or cachedGlow[0] is not image:   # hit[0] check guards against id() reuse
        if len(_stencilGlowCache) >= _STENCIL_GLOW_CACHE_LIMIT:
            _stencilGlowCache.clear()
        out = glow.copy()
        cutout = _cachedPerImage(_cutoutCache, image, _buildCutout)
        out.blit(cutout, offset, special_flags=pygame.BLEND_RGBA_MULT)
        cachedGlow = (image, out)
        _stencilGlowCache[stencilKey] = cachedGlow
    out = cachedGlow[1]

    pulse = 1 - GLOW_PULSE + GLOW_PULSE * math.sin(pygame.time.get_ticks() * GLOW_PULSE_SPEED)
    out.set_alpha(max(0, min(255, int(255 * strength * pulse))))
    window.blit(out, glowRect)

# ---------- Sprite outline and shadow ----------
def drawSpriteOutline(window, sprite, color, width=2, image=None, rect=None):
    """Kept so any old call site still works -- outlines are gone, this now just draws the glow (`width` and `image` are ignored)."""
    drawCharacterGlow(window, sprite, color, rect=rect)

def drawCharacterShadow(window, sprite, alpha=90):
    """Soft oval shadow beneath the character's feet, drawn before the sprite itself so it reads as sitting on the ground under them."""
    stats = sprite["stats"]
    rect = stats.rect
    shadowWidth = rect.width * 0.45
    shadowHeight = shadowWidth * 0.25

    key = (int(shadowWidth), int(shadowHeight), alpha)
    shadowSurf = _shadowCache.get(key)
    if shadowSurf is None:
        shadowSurf = pygame.Surface(key[:2], pygame.SRCALPHA)
        pygame.draw.ellipse(shadowSurf, (0, 0, 0, alpha), shadowSurf.get_rect())
        _shadowCache[key] = shadowSurf

    shadowRect = shadowSurf.get_rect(center=(rect.centerx + 5, rect.bottom - shadowHeight * 0.45))
    window.blit(shadowSurf, shadowRect)

# ---------- Hit flash (tick damage feedback) ----------

HIT_FLASH_DURATION = 220   # ms the glow + shake take to fade out
HIT_FLASH_SHAKE = 6
HIT_FLASH_STEPS = 8

def triggerHitFlash(sprite):
    """Marks `sprite` as freshly hit (and plays its 'hurt' voice, see voice.py)."""
    sprite["hitFlash"] = {"elapsed": 0}
    playHurtVoice(sprite)

def updateHitFlashes(sprites, dt):
    """Call once per frame, before drawing."""
    for sprite in sprites:
        flash = sprite.get("hitFlash")
        if flash is None:
            continue
        flash["elapsed"] += dt
        if flash["elapsed"] >= HIT_FLASH_DURATION:
            sprite["hitFlash"] = None

_hitFlashCache = {}

def _redTintedImage(image, step):
    """`image` boosted toward red, `step` (0..HIT_FLASH_STEPS) of the way there."""
    key = (id(image), step)
    cached = _hitFlashCache.get(key)
    if cached is not None:
        return cached
    if len(_hitFlashCache) >= 256:
        _hitFlashCache.clear()

    tintAmount = step / HIT_FLASH_STEPS
    tinted = image.copy()
    tinted.fill((round(255 * tintAmount), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
    tinted.fill((0, round(120 * tintAmount), round(120 * tintAmount)), special_flags=pygame.BLEND_RGB_SUB)
    _hitFlashCache[key] = tinted
    return tinted

# ---------- Heal flash ----------

HEAL_FLASH_DURATION = 220   # ms the glow takes to fade out
HEAL_FLASH_STEPS = 8        # distinct tint strengths to cache

def triggerHealFlash(sprite):
    """Marks `sprite` as freshly healed -- drawChar() reads sprite['healFlash'] to tint it green for HEAL_FLASH_DURATION ms."""
    sprite["healFlash"] = {"elapsed": 0}

def updateHealFlashes(sprites, dt):
    """Call once per frame, before drawing (alongside updateHitFlashes)."""
    for sprite in sprites:
        flash = sprite.get("healFlash")
        if flash is None:
            continue
        flash["elapsed"] += dt
        if flash["elapsed"] >= HEAL_FLASH_DURATION:
            sprite["healFlash"] = None

_healFlashCache = {}

def _greenTintedImage(image, step):
    """`image` boosted toward green, `step` of the way there."""
    key = (id(image), step)
    cached = _healFlashCache.get(key)
    if cached is not None:
        return cached
    if len(_healFlashCache) >= 256:
        _healFlashCache.clear()

    tintAmount = step / HEAL_FLASH_STEPS
    tinted = image.copy()
    tinted.fill((0, round(255 * tintAmount), 0), special_flags=pygame.BLEND_RGB_ADD)
    tinted.fill((round(120 * tintAmount), 0, round(120 * tintAmount)), special_flags=pygame.BLEND_RGB_SUB)
    _healFlashCache[key] = tinted
    return tinted

# ---------- DoT flash (poison-style tick feedback) ----------

DOT_FLASH_DURATION = 650
DOT_BRUISE_COLOR = (95, 40, 110)   # dark purple-ish bruise
DOT_BRUISE_COUNT = 4                # blotches per sprite
DOT_BRUISE_MAX_RADIUS = 10          # px, largest blotch
DOT_BRUISE_MAX_ALPHA = 180

def triggerDotFlash(sprite):
    """Marks `sprite` as freshly afflicted by a DoT-category effect (e.g."""
    sprite["dotFlash"] = {"elapsed": 0}

def updateDotFlashes(sprites, dt):
    """Call once per frame, alongside updateHitFlashes/updateHealFlashes."""
    for sprite in sprites:
        flash = sprite.get("dotFlash")
        if flash is not None:
            flash["elapsed"] += dt
            if flash["elapsed"] >= DOT_FLASH_DURATION:
                sprite["dotFlash"] = None
        bleed = sprite.get("bleedFlash")
        if bleed is not None:
            bleed["elapsed"] += dt
            if bleed["elapsed"] >= BLEED_FLASH_DURATION:
                sprite["bleedFlash"] = None

def _bruiseSpots(rect, seed):
    """Fixed positions/sizes for one sprite's bruises."""
    rng = random.Random(seed)
    spots = []
    for _ in range(DOT_BRUISE_COUNT):
        x = rect.centerx + rng.uniform(-rect.width * 0.3, rect.width * 0.3)
        y = rect.top + rng.uniform(rect.height * 0.25, rect.height * 0.8)
        spotRadius = rng.uniform(DOT_BRUISE_MAX_RADIUS * 0.5, DOT_BRUISE_MAX_RADIUS)
        spots.append((x, y, spotRadius))
    return spots

def drawDotBruises(window, sprite, rect, remaining):
    """Overlays a handful of dark blotches on `sprite`'s own rect, faded by `remaining`."""
    alpha = round(DOT_BRUISE_MAX_ALPHA * remaining)
    if alpha <= 0:
        return
    for x, y, spotRadius in _bruiseSpots(rect, id(sprite)):
        surf = pygame.Surface((round(spotRadius * 2), round(spotRadius * 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (*DOT_BRUISE_COLOR, alpha), surf.get_rect())
        window.blit(surf, surf.get_rect(center=(round(x), round(y))))

# ---------- Bleed flash (blood-drip tick feedback) ----------

BLEED_FLASH_DURATION = 800
BLEED_COLOR = (185, 12, 28)
BLEED_SLASH_END = 0.45
BLEED_DROP_COUNT = 7
BLEED_DROP_MAX_RADIUS = 5         # px, largest drop
BLEED_DROP_FALL = 40              # px a drop runs down over its life

def triggerBleedFlash(sprite):
    """Marks `sprite` as freshly bleeding."""
    sprite["bleedFlash"] = {"elapsed": 0}

def _bleedDrops(rect, seed):
    """Fixed drop positions/sizes/start delays for one sprite so the drips land in the same places each flash."""
    rng = random.Random(seed + 7)
    drops = []
    for _ in range(BLEED_DROP_COUNT):
        x = rect.centerx + rng.uniform(-rect.width * 0.3, rect.width * 0.3)
        y = rect.top + rng.uniform(rect.height * 0.25, rect.height * 0.65)
        dropRadius = rng.uniform(BLEED_DROP_MAX_RADIUS * 0.55, BLEED_DROP_MAX_RADIUS)
        delay = rng.uniform(0.1, 0.45)
        drops.append((x, y, dropRadius, delay))
    return drops

def drawBleedEffect(window, sprite, rect, elapsed):
    """Overlays the bleed effect on `sprite`'s rect: two diagonal slash marks that fade out early."""
    flashProgress = min(1.0, elapsed / BLEED_FLASH_DURATION)

    if flashProgress < BLEED_SLASH_END:
        alpha = round(230 * (1 - flashProgress / BLEED_SLASH_END))
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        rectWidth, rectHeight = rect.size
        for offset in (0.0, 0.14):
            start = (rectWidth * (0.22 + offset), rectHeight * 0.22)
            dropEnd = (rectWidth * (0.62 + offset), rectHeight * 0.70)
            pygame.draw.line(layer, (*BLEED_COLOR, alpha), start, dropEnd, 4)
            pygame.draw.line(layer, (255, 120, 120, alpha // 2), start, dropEnd, 1)
        window.blit(layer, rect.topleft)

    for x, y, dropRadius, delay in _bleedDrops(rect, id(sprite)):
        local = (flashProgress - delay) / (1 - delay)
        if local <= 0:
            continue
        alpha = round(220 * (1 - local))
        if alpha <= 0:
            continue
        drawRadius = max(2, round(dropRadius))
        drop = pygame.Surface((drawRadius * 2 + 2, drawRadius * 3 + 2), pygame.SRCALPHA)
        color = (*BLEED_COLOR, alpha)
        pygame.draw.circle(drop, color, (drawRadius + 1, drawRadius * 2 + 1), drawRadius)
        pygame.draw.polygon(drop, color, [(drawRadius + 1, 0), (1, drawRadius * 2), (drawRadius * 2 + 1, drawRadius * 2)])
        window.blit(drop, (round(x - drawRadius), round(y + local * BLEED_DROP_FALL - drawRadius * 2)))

# ---------- Stun stars ----------

STUN_STAR_COUNT = 3
STUN_STAR_ORBIT_X = 13          # px, how far out the stars swing sideways
STUN_STAR_ORBIT_Y = 4           # px, how far they bob vertically
STUN_STAR_SIZE = 7              # px, half-width of each star
STUN_STAR_COLOR = (255, 230, 60)
STUN_STAR_OUTLINE = (120, 90, 0)
STUN_STAR_PERIOD = 1400         # ms per full orbit

def _starPoints(cx, cy, size):
    """A simple 5-point star polygon centered at (cx, cy)."""
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        pointRadius = size if i % 2 == 0 else size * 0.45
        points.append((cx + pointRadius * math.cos(angle), cy - pointRadius * math.sin(angle)))
    return points

def drawStunStars(window, rect):
    """Draws STUN_STAR_COUNT stars evenly spaced around a slow orbit just above `rect`."""
    now = pygame.time.get_ticks()
    centerX = rect.centerx
    centerY = rect.top - 6
    for i in range(STUN_STAR_COUNT):
        phase = (now / STUN_STAR_PERIOD + i / STUN_STAR_COUNT) * 2 * math.pi
        x = centerX + STUN_STAR_ORBIT_X * math.cos(phase)
        y = centerY - STUN_STAR_ORBIT_Y - STUN_STAR_ORBIT_Y * math.sin(phase)
        points = _starPoints(x, y, STUN_STAR_SIZE)
        pygame.draw.polygon(window, STUN_STAR_COLOR, points)
        pygame.draw.polygon(window, STUN_STAR_OUTLINE, points, 1)

# ---------- Status effect icons ----------

STATUS_ICON_SIZE = 18            # px, square
STATUS_ICON_GAP = 3              # px between stacked icons
STATUS_ICON_SIDE_GAP = 6
STATUS_ICON_BG_COLOR = (20, 20, 20)
STATUS_ICON_BORDER_COLOR = (0, 0, 0)
STATUS_ICON_DURATION_COLOR = (255, 255, 255)
STATUS_ICON_POTENCY_BUFF_COLOR = (120, 255, 140)
STATUS_ICON_POTENCY_DEBUFF_COLOR = (255, 120, 120)
STATUS_ICON_LABEL_GAP = 3

# The only effect functions that ever actually get tracked with a live.
STATUS_ICON_NAMES = [fn.__name__ for fn in EFFECT_REVERTS]

def loadStatusIcons():
    """Call once, after pygame.display.set_mode -- same convention as loadSkillIcons."""
    icons = {}
    for name in STATUS_ICON_NAMES:
        try:
            img = pygame.image.load(f"assets/img/status/{name}.png").convert_alpha()
        except (FileNotFoundError, pygame.error):
            print(f"[status icon missing] assets/img/status/{name}.png -- drawing a placeholder")
            continue
        icons[name] = fitIcon(img, STATUS_ICON_SIZE)
    return icons

def _statusPotencyLabel(entry):
    """Short potency label for one status-effect icon's badge, e.g."""
    if entry.apply.__name__ == "stun":
        return None
    if entry.apply.__name__ == "bleed":
        if entry.amount is not None:
            return f"-{entry.amount}/rd"          # the constant HP lost every round
        return f"-{entry.modifier:g}/rd"
    if entry.apply.__name__ == "sanityUpTick":
        return f"+{entry.modifier * 100:g}%/rd"   # sanity gained per round
    if entry.apply.__name__ == "sanityDownTick":
        return f"-{entry.modifier * 100:g}%/rd"   # sanity lost per round
    if entry.apply.__name__ == "poison":
        return f"-{entry.modifier * 100:g}%/rd"   # % of max HP lost per round
    percentChange = round((entry.modifier - 1) * 100)
    sign = "+" if percentChange > 0 else ""
    return f"{sign}{percentChange}%"

def drawStatusEffectIcons(window, sprite, icons):
    """Draws `sprite`'s current statusEffects as a small vertical stack of icons -- see the module note above."""
    effects = sprite.get("statusEffects")
    if not effects or icons is None:
        return

    side = sprite["side"]
    size = STATUS_ICON_SIZE
    stackHeight = len(effects) * size + (len(effects) - 1) * STATUS_ICON_GAP

    barX, barY, barWidth, barHeight, sanityBarX, sanityBarWidth, _sanityBarHeight, _sanityBarY = _barGeometry(sprite)
    topY = barY

    if side == "left":
        boxX = sanityBarX - STATUS_ICON_SIDE_GAP - size
    else:
        boxX = sanityBarX + sanityBarWidth + STATUS_ICON_SIDE_GAP

    for i, entry in enumerate(effects):
        boxY = topY + i * (size + STATUS_ICON_GAP)
        boxRect = pygame.Rect(round(boxX), round(boxY), size, size)

        pygame.draw.rect(window, STATUS_ICON_BG_COLOR, boxRect)
        icon = icons.get(entry.apply.__name__)
        if icon is not None:
            window.blit(icon, boxRect.topleft)
        else:
            pygame.draw.circle(window, (200, 30, 40), boxRect.center, size // 3)   # placeholder (no PNG found)
        pygame.draw.rect(window, STATUS_ICON_BORDER_COLOR, boxRect, 1)

        durLabel = barText(str(max(0, round(entry.duration))), STATUS_ICON_DURATION_COLOR, STATUS_ICON_FONT)
        window.blit(durLabel, durLabel.get_rect(bottomright=(boxRect.right, boxRect.bottom)))

        potencyText = _statusPotencyLabel(entry)
        if potencyText is not None:
            isBuff = (entry.modifier >= 1 and entry.apply.__name__ not in ("bleed", "poison")) or entry.apply.__name__ == "sanityUpTick"
            color = STATUS_ICON_POTENCY_BUFF_COLOR if isBuff else STATUS_ICON_POTENCY_DEBUFF_COLOR
            potLabel = barText(potencyText, color, STATUS_ICON_FONT)
            if side == "left":
                potRect = potLabel.get_rect(midright=(boxRect.left - STATUS_ICON_LABEL_GAP, boxRect.centery))
            else:
                potRect = potLabel.get_rect(midleft=(boxRect.right + STATUS_ICON_LABEL_GAP, boxRect.centery))
            window.blit(potLabel, potRect)

# ---------- Character drawing ----------
def _barGeometry(sprite):
    """Shared health/sanity bar geometry."""
    stats = sprite["stats"]
    barHeight = stats.rect.height * 0.85
    barWidth = 14
    barY = stats.rect.top + (stats.rect.height - barHeight) / 2

    sanityBarWidth = barWidth * 0.5
    sanityBarHeight = barHeight * 0.5
    sanityBarY = barY + (barHeight + sanityBarHeight) / 2.75

    # Original bar spacing: the sanity bar sits right against the health bar.
    if sprite["side"] == "left":
        barX = stats.rect.left - barWidth + 40
        sanityBarX = barX - sanityBarWidth - SANITY_BAR_GAP
    else:
        barX = stats.rect.right - 40
        sanityBarX = barX + barWidth + SANITY_BAR_GAP

    return barX, barY, barWidth, barHeight, sanityBarX, sanityBarWidth, sanityBarHeight, sanityBarY

ACTED_GLOW_STRENGTH = 0.85

def drawChar(window, sprite, active=False, hide_image=False, statusIcons=None):
    """Draws a sprite at full opacity."""
    stats = sprite["stats"]

    drawCharacterShadow(window, sprite)

    image = stats.image
    rect = stats.rect

    flash = sprite.get("hitFlash")
    healFlash = sprite.get("healFlash")
    if flash is not None:
        remaining = max(0.0, 1 - flash["elapsed"] / HIT_FLASH_DURATION)
        step = round(remaining * HIT_FLASH_STEPS)
        if step > 0:
            image = _redTintedImage(image, step)
            shakeAmt = HIT_FLASH_SHAKE * remaining
            rect = rect.move(round(random.uniform(-shakeAmt, shakeAmt)),
                              round(random.uniform(-shakeAmt, shakeAmt)))
    elif healFlash is not None:
        # A hit flash always wins if somehow both are active at once (rare -- e.g.
        remaining = max(0.0, 1 - healFlash["elapsed"] / HEAL_FLASH_DURATION)
        step = round(remaining * HEAL_FLASH_STEPS)
        if step > 0:
            image = _greenTintedImage(image, step)

    if not hide_image:
        window.blit(image, rect)
        if sprite["acted"] and not sprite["selected"] and not active:
            drawCharacterGlow(window, sprite, _arrowColorForSide(sprite["side"]),
                              strength=ACTED_GLOW_STRENGTH, rect=rect, image=image)

        dotFlash = sprite.get("dotFlash")
        if dotFlash is not None:
            remaining = max(0.0, 1 - dotFlash["elapsed"] / DOT_FLASH_DURATION)
            drawDotBruises(window, sprite, rect, remaining)

        bleedFlash = sprite.get("bleedFlash")
        if bleedFlash is not None:
            drawBleedEffect(window, sprite, rect, bleedFlash["elapsed"])

    if sprite["selected"]:
        drawCharacterGlow(window, sprite, (255, 215, 0), rect=rect, image=image)

    if stats.stunned:
        drawStunStars(window, rect)

    barX, barY, barWidth, barHeight, sanityBarX, sanityBarWidth, sanityBarHeight, sanityBarY = _barGeometry(sprite)

    # Bars draw the eased "display" values, not stats.hp/sprite["sanity"] directly.
    displayHp = sprite.get("displayHp", stats.hp)
    displaySanity = sprite.get("displaySanity", sprite.get("sanity", 0.5))
    draining = displayHp > stats.hp + HP_BAR_DRAIN_EPSILON

    isBoss = sprite.get("ultChance") is not None
    if not isBoss:      # a boss's HP lives in the top-of-screen boss bar (drawBossHpBar), clear of the turn-order tabs
        drawHealthBar(window, barX, barY, barWidth, barHeight, displayHp, stats.maxHp, draining=draining)
    if not isBoss:      # a boss's sanity sits under its HP in the top-of-screen boss bar
        drawSanityBar(window, sanityBarX, sanityBarY, sanityBarWidth, sanityBarHeight, displaySanity)

    # Current HP sits centered right on top of the health bar.
    hp = hpLabel(displayHp)
    sanityText = sanityLabel(displaySanity)
    if not isBoss:
        window.blit(hp, hp.get_rect(midbottom=(int(barX + barWidth / 2), int(barY) - HP_TEXT_GAP)))

    sanityMidY = int(sanityBarY + sanityBarHeight / 2)
    if isBoss:
        pass
    elif sprite["side"] == "left":
        window.blit(sanityText, sanityText.get_rect(midright=(int(sanityBarX) - HP_TEXT_GAP, sanityMidY)))
    else:
        window.blit(sanityText, sanityText.get_rect(midleft=(int(sanityBarX + sanityBarWidth) + HP_TEXT_GAP, sanityMidY)))

    drawStatusEffectIcons(window, sprite, statusIcons)

# ---------- "ULT LOCKED" tag (bosses) ----------
ULT_LOCKED_COLOR = (225, 90, 90)

# ---------- Boss HP bar (screen-space HUD) ----------
# A wide bar under the turn-order tabs instead of a tall bar beside the (big) boss sprite, which could climb up
# behind the sorting resolver. It is drawn AFTER the queue, in screen space, and sits below QUEUE_TOP + a tab's height.
BOSS_BAR_WIDTH = 520
BOSS_BAR_HEIGHT = 18
BOSS_BAR_GAP_BELOW_QUEUE = 34       # room under the tabs (the active tab hangs QUEUE_DROP lower) before the name row
BOSS_SANITY_BAR_HEIGHT = 6          # the boss's sanity gauge, right under its HP bar
BOSS_SANITY_BAR_WIDTH = 260         # narrower than the HP bar; centred beneath it
BOSS_BAR_ROW_GAP = 8                # between stacked boss bars (only if a stage ever has two bosses)
_bossBarFont = [None]

def bossBarTop():
    """Y of the boss bar's name row: always clear of the turn-order tabs."""
    return QUEUE_TOP + QUEUE_TILE_H + QUEUE_DROP + BOSS_BAR_GAP_BELOW_QUEUE

def drawBossHpBar(window, sprites):
    """Draws a horizontal HP bar (name, HP numbers, ULT LOCKED tag) for every living boss, below the turn-order tabs."""
    if _bossBarFont[0] is None:
        _bossBarFont[0] = pygame.font.Font('assets/font/monogram.ttf', 26)
    font = _bossBarFont[0]
    y = bossBarTop()
    for sprite in sprites:
        if sprite.get("ultChance") is None or sprite["side"] != "right" or sprite["dead"]:
            continue
        stats = sprite["stats"]
        x = (window.get_width() - BOSS_BAR_WIDTH) // 2
        displayHp = sprite.get("displayHp", stats.hp)
        draining = displayHp > stats.hp + HP_BAR_DRAIN_EPSILON

        # name (left) and current / max HP (right), outlined so they read over any battlefield
        name = _outlinedText(font, str(stats.owner), (255, 255, 255), outline=2, shadow=2)
        window.blit(name, name.get_rect(bottomleft=(x, y + 20)))
        nums = _outlinedText(font, f"{max(0, round(displayHp))} / {round(stats.maxHp)}", (255, 255, 255),
                             outline=2, shadow=2)
        window.blit(nums, nums.get_rect(bottomright=(x + BOSS_BAR_WIDTH, y + 20)))
        if sprite.get("ultLock", 0) > 0:
            tag = _outlinedText(font, "ULT LOCKED", ULT_LOCKED_COLOR, outline=2, shadow=2)
            window.blit(tag, tag.get_rect(midbottom=(x + BOSS_BAR_WIDTH // 2, y + 20)))

        barY = y + 24
        ratio = max(0.0, min(displayHp / max(1, stats.maxHp), 1.0))
        pygame.draw.rect(window, (60, 60, 60), (x, barY, BOSS_BAR_WIDTH, BOSS_BAR_HEIGHT))
        pygame.draw.rect(window, HP_BAR_DRAIN_COLOR if draining else HP_BAR_COLOR,
                         (x, barY, round(BOSS_BAR_WIDTH * ratio), BOSS_BAR_HEIGHT))
        pygame.draw.rect(window, (0, 0, 0), (x, barY, BOSS_BAR_WIDTH, BOSS_BAR_HEIGHT), 2)

        # sanity, directly below the health bar (same look as the other sanity gauges, laid on its side)
        sanity = max(0.0, min(sprite.get("displaySanity", sprite.get("sanity", 0.5)), 1.0))
        sanY = barY + BOSS_BAR_HEIGHT + 4
        sanW = BOSS_SANITY_BAR_WIDTH
        sanX = x + (BOSS_BAR_WIDTH - sanW) // 2
        pygame.draw.rect(window, (60, 60, 60), (sanX, sanY, sanW, BOSS_SANITY_BAR_HEIGHT))
        pygame.draw.rect(window, SANITY_HIGH_COLOR if sanity >= 0.5 else SANITY_LOW_COLOR,
                         (sanX, sanY, round(sanW * sanity), BOSS_SANITY_BAR_HEIGHT))
        midX = sanX + sanW // 2
        pygame.draw.line(window, SANITY_MID_TICK_COLOR, (midX, sanY), (midX, sanY + BOSS_SANITY_BAR_HEIGHT - 1), 1)
        pygame.draw.rect(window, (0, 0, 0), (sanX, sanY, sanW, BOSS_SANITY_BAR_HEIGHT), 2)
        sanText = _outlinedText(font, f"{round(sanity * 100)}", (255, 255, 255), outline=2, shadow=2)
        window.blit(sanText, sanText.get_rect(midleft=(sanX + sanW + 6, sanY + BOSS_SANITY_BAR_HEIGHT // 2)))
        y = sanY + BOSS_SANITY_BAR_HEIGHT + BOSS_BAR_ROW_GAP

# ---------- Target highlights and action queue display ----------
TARGET_HIGHLIGHT_ENEMY_COLOR = (200, 30, 30)
TARGET_HIGHLIGHT_ALLY_COLOR = (40, 200, 90)

def drawTargetHighlights(window, sprites, selectedSprite, skillDef=None):
    """Outlines every valid target while a target-select phase is open."""
    friendly = isFriendlyTargetSkill(skillDef)
    for sprite in sprites:
        sameSide = sprite["side"] == selectedSprite["side"]
        if friendly and sameSide:
            if sprite is selectedSprite and not canTargetSelf(skillDef):
                continue
            drawCharacterGlow(window, sprite, TARGET_HIGHLIGHT_ALLY_COLOR)
        elif not friendly and not sameSide:
            drawCharacterGlow(window, sprite, TARGET_HIGHLIGHT_ENEMY_COLOR)

# ---------- Action queue / turn order display ----------

QUEUE_TILE_W = 64
QUEUE_FACE_H = 58                # the face window
QUEUE_STRIP_H = 24               # skill icon + speed row under the face
QUEUE_TILE_H = 3 + QUEUE_FACE_H + QUEUE_STRIP_H
QUEUE_TILE_GAP = 8
QUEUE_TOP = 0
QUEUE_DROP = 7                   # how much lower the active tab hangs
QUEUE_GLIDE_RATE = 16.0          # higher = tiles snap to their slot faster
QUEUE_ACTIVE_COLOR = (255, 215, 0)
QUEUE_TILE_FILL = (34, 34, 40)
QUEUE_RADIUS = 10

_queueAnim = {}                  # id(action) -> {"x", "lift", "appear"}
_queuePortraits = {}             # character name -> icon surface
_queueLastTick = [None]

QUEUE_ICON_DIR = "assets/img/char_icon"

def _queueIconPath(name):
    return f"{QUEUE_ICON_DIR}/{name.lower().replace(' ', '')}_icon.png"

def _queuePlaceholder(size):
    """Stand-in for a character with no icon file yet: a dim tile with a '?'."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surf, (58, 58, 68), surf.get_rect(), border_radius=7)
    mark = renderFittedText("?", (150, 150, 165), size[0] - 20, startSize=40, minSize=20)
    surf.blit(mark, mark.get_rect(center=surf.get_rect().center))
    return surf

def _queuePortrait(sprite):
    """The character's head icon from assets/img/char_icon/<name>_icon.png, scaled to the face window (cached per character)."""
    name = sprite["name"]
    surf = _queuePortraits.get(name)
    if surf is None:
        size = (QUEUE_TILE_W - 6, QUEUE_FACE_H)
        path = _queueIconPath(name)
        try:
            img = pygame.image.load(path).convert_alpha()
            bounds = img.get_bounding_rect()
            if bounds.width and bounds.height:
                img = img.subsurface(bounds)
            ratio = min(size[0] / img.get_width(), size[1] / img.get_height())
            scaled = pygame.transform.smoothscale(
                img, (max(1, round(img.get_width() * ratio)), max(1, round(img.get_height() * ratio))))
            surf = pygame.Surface(size, pygame.SRCALPHA)
            surf.blit(scaled, scaled.get_rect(center=surf.get_rect().center))
        except (FileNotFoundError, pygame.error):
            print(f"[turn order] icon missing for {name} -> looked for {path}; using placeholder")
            surf = _queuePlaceholder(size)
        _queuePortraits[name] = surf
    return surf

def _drawQueueTile(action, index, active, drop, icons):
    """Turn-order entry, styled like the skill cards: NO box or border around it."""
    sprite, skillDef = action["sprite"], action["skillDef"]
    tile = pygame.Surface((QUEUE_TILE_W, QUEUE_TILE_H + QUEUE_DROP), pygame.SRCALPHA)
    sideColor = ARROW_PLAYER_COLOR if sprite["side"] == "left" else ARROW_ENEMY_COLOR
    textColor = CARD_HOVER_COLOR if active else CARD_TEXT_COLOR
    ruleColor = CARD_HOVER_COLOR if active else sideColor
    outlineSize = 1
    top = 2 + drop    # the active entry slides down a little

    if active:
        glow = _iconGlow(40)
        tile.blit(glow, glow.get_rect(center=(QUEUE_TILE_W // 2, top + QUEUE_FACE_H // 2)))

    # portrait, ink-outlined, no plate behind it
    face = _queuePortrait(sprite)
    faceRect = face.get_rect(midtop=(QUEUE_TILE_W // 2, top))
    _blitInked(tile, face, faceRect.topleft, outlineSize)

    # turn-order number: big outlined digit like the ROUND number.
    _drawInkedText(tile, str(action.get("orderNum", index + 1)), textColor, 20, 22, 14, 2,
                   topleft=(2, top))

    # fading rule under the portrait (side colour, gold when active)
    ruleY = top + QUEUE_FACE_H + 2
    _drawFadeRule(tile, ruleColor, 4, QUEUE_TILE_W - 4, ruleY, 2, outlineSize)

    # speed (left) + skill icon (right)
    midY = ruleY + 2 + QUEUE_STRIP_H // 2 - 2
    x = 6
    spdIcon = _iconAtSize("stat_speed", 12) if "stat_speed" in _ICON_SOURCES else None
    if spdIcon is not None:
        _blitInked(tile, spdIcon, spdIcon.get_rect(midleft=(x, midY)).topleft, outlineSize)
        x += spdIcon.get_width() + 3
    _drawInkedText(tile, str(skillDef.speed) if skillDef is not None else "-", textColor,
                   22, 16, 10, outlineSize, midleft=(x, midY))
    skillIcon = _iconAtSize(skillDef.icon, 16, icons) if skillDef is not None else None
    if skillIcon is not None:
        _blitInked(tile, skillIcon, skillIcon.get_rect(midright=(QUEUE_TILE_W - 5, midY)).topleft, outlineSize)
    return tile

def drawActionQueue(window, actionQueue, x=None, y=QUEUE_TOP, activeIndex=None, icons=None):
    """Turn-order tabs, centered along the very top of the window (x overrides the centre)."""
    now = pygame.time.get_ticks()
    dt = 16 if _queueLastTick[0] is None else min(50, now - _queueLastTick[0])
    _queueLastTick[0] = now
    ease = 1 - math.exp(-QUEUE_GLIDE_RATE * dt / 1000)

    count = len(actionQueue)
    rowW = count * QUEUE_TILE_W + (count - 1) * QUEUE_TILE_GAP
    centerX = window.get_width() // 2 if x is None else x
    startX = centerX - rowW / 2

    live = set()
    for i, action in enumerate(actionQueue):
        key = id(action)
        live.add(key)
        targetX = startX + i * (QUEUE_TILE_W + QUEUE_TILE_GAP)
        anim = _queueAnim.get(key)
        if anim is None:
            anim = _queueAnim[key] = {"x": targetX, "lift": 0.0, "appear": 0.0}
        active = (i == activeIndex)
        anim["x"] += (targetX - anim["x"]) * ease
        anim["lift"] += ((1.0 if active else 0.0) - anim["lift"]) * ease
        anim["appear"] += (1.0 - anim["appear"]) * ease

        tile = _drawQueueTile(action, i, active, round(anim["lift"] * QUEUE_DROP), icons)
        if anim["appear"] < 0.98:
            tile.set_alpha(round(255 * anim["appear"]))
        window.blit(tile, (round(anim["x"]), y))

    for key in [staleKey for staleKey in _queueAnim if staleKey not in live]:
        del _queueAnim[key]


# ---------- Vignette ----------

VIGNETTE_CLEAR_RADIUS = 30
VIGNETTE_DARK_RADIUS = 100    # fully darkened by this many px out
VIGNETTE_COLOR = (0, 0, 0)
VIGNETTE_MAX_ALPHA = 190

def makeVignette(screenSize, focusPositions, innerRadius=VIGNETTE_CLEAR_RADIUS,
                  outerRadius=VIGNETTE_DARK_RADIUS, color=VIGNETTE_COLOR,
                  maxAlpha=VIGNETTE_MAX_ALPHA):
    """Full-screen SRCALPHA overlay: fully dark everywhere, except a clear gradient hole centered on each point in focusPositions."""
    hole = _vignetteHole(innerRadius, outerRadius, color, maxAlpha)
    surf = pygame.Surface(screenSize, pygame.SRCALPHA)
    surf.fill((*color, maxAlpha))
    for x, y in focusPositions:
        # MIN-blend the small pre-drawn hole in.
        surf.blit(hole, (int(x) - outerRadius, int(y) - outerRadius), special_flags=pygame.BLEND_RGBA_MIN)
    return surf.convert_alpha()

_holeCache = {}
def _vignetteHole(innerRadius, outerRadius, color, maxAlpha):
    """Small radial-gradient tile (clear in the middle, maxAlpha at/after outerRadius)."""
    key = (innerRadius, outerRadius, color, maxAlpha)
    hole = _holeCache.get(key)
    if hole is None:
        size = outerRadius * 2 + 1
        hole = pygame.Surface((size, size), pygame.SRCALPHA)
        hole.fill((*color, maxAlpha))
        for ringRadius in range(outerRadius, 0, -1):
            if ringRadius <= innerRadius:
                alpha = 0
            else:
                alpha = int(maxAlpha * (ringRadius - innerRadius) / (outerRadius - innerRadius))
            pygame.draw.circle(hole, (*color, alpha), (outerRadius, outerRadius), ringRadius)
        _holeCache[key] = hole
    return hole

_vignetteCache = {}
def cachedVignette(screenSize, focusPositions):
    """makeVignette, memoized on."""
    key = (tuple(screenSize), tuple((int(x), int(y)) for x, y in focusPositions))
    surf = _vignetteCache.get(key)
    if surf is None:
        if len(_vignetteCache) >= 12:
            _vignetteCache.clear()
        surf = makeVignette(screenSize, key[1])
        _vignetteCache[key] = surf
    return surf

def makeSelectionVignette(screenSize, focusPos, **kwargs):
    """Vignette with a single hole, for the currently selected character."""
    return makeVignette(screenSize, [focusPos], **kwargs)


# The camera pan nudges the whole scene a few pixels off its native position each frame.
EDGE_VIGNETTE_BORDER = 48
EDGE_VIGNETTE_MAX_ALPHA = 150 # darkness right at the edge

def makeEdgeVignette(screenSize, borderWidth=EDGE_VIGNETTE_BORDER,
                      maxAlpha=EDGE_VIGNETTE_MAX_ALPHA, color=VIGNETTE_COLOR):
    """Full-screen SRCALPHA overlay."""
    screenWidth, screenHeight = screenSize
    surf = pygame.Surface(screenSize, pygame.SRCALPHA)
    for i in range(borderWidth, -1, -1):
        inset = borderWidth - i
        alpha = int(maxAlpha * i / borderWidth) if borderWidth else 0
        rect = pygame.Rect(inset, inset, screenWidth - 2 * inset, screenHeight - 2 * inset)
        pygame.draw.rect(surf, (*color, alpha), rect)
    return surf.convert_alpha()

def drawEdgeVignette(window, vignette, borderWidth=EDGE_VIGNETTE_BORDER):
    """Blit only the four border strips of an edge vignette."""
    vignetteWidth, vignetteHeight = vignette.get_size()
    borderPixels = borderWidth + 1
    window.blit(vignette, (0, 0), pygame.Rect(0, 0, vignetteWidth, borderPixels))
    window.blit(vignette, (0, vignetteHeight - borderPixels), pygame.Rect(0, vignetteHeight - borderPixels, vignetteWidth, borderPixels))
    window.blit(vignette, (0, borderPixels), pygame.Rect(0, borderPixels, borderPixels, vignetteHeight - 2 * borderPixels))
    window.blit(vignette, (vignetteWidth - borderPixels, borderPixels), pygame.Rect(vignetteWidth - borderPixels, borderPixels, borderPixels, vignetteHeight - 2 * borderPixels))


# ---------- Wipe transition (e.g. character select -> battle) ----------
# An ink-dark curtain with a thin gold seam sweeps across and reveals the battlefield behind it, while a stage
# title card (chapter in white, stage in gold -- red for a boss) fades in and out on top. Same ink / gold /
# fading-rule look as the cards, round banner and HUD.

WIPE_COLOR = (10, 8, 16)         # the same ink as CARD_INK
WIPE_SEAM_COLOR = (255, 215, 0)  # the same gold as CARD_HOVER_COLOR
WIPE_BAND_WIDTH = 420
WIPE_MAX_ALPHA = 235             # opacity of the curtain at its center
WIPE_SEAM_GLOW = 26              # px of soft gold glow either side of the seam
WIPE_DURATION = 1100             # ms

def makeWipeBand(height, width=WIPE_BAND_WIDTH, color=WIPE_COLOR, maxAlpha=WIPE_MAX_ALPHA,
                 seamColor=WIPE_SEAM_COLOR, glow=WIPE_SEAM_GLOW):
    """A vertical ink curtain, full screen height: soft at both edges, darkest in the middle, with a gold seam down its center line."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    center = width / 2
    for x in range(width):
        dist = abs(x + 0.5 - center)
        alpha = maxAlpha * (1 - dist / center) ** 0.8
        seamBlend = 0.0
        if dist < glow:
            seamBlend = (1 - dist / glow) ** 2 * 0.65
        if dist < 1.5:                                   # the 2-3px solid seam itself
            seamBlend, alpha = 1.0, 255
        elif dist < glow:
            alpha = max(alpha, 150 * (1 - dist / glow) ** 2)
        bandColor = tuple(int(color[i] + (seamColor[i] - color[i]) * seamBlend) for i in range(3))
        pygame.draw.line(surf, (*bandColor, max(0, min(255, int(alpha)))), (x, 0), (x, height))
    return surf

def makeStageBanner(chapterName, stageTitle, isBoss=False):
    """Returns draw(window, t) for wipeTransition's `banner`: the stage title card, t = 0..1 across the wipe."""
    chapterText = str(chapterName).upper()
    stageText = str(stageTitle).upper()

    def draw(window, elapsedMs):
        windowWidth, windowHeight = window.get_size()
        accent = (255, 90, 90) if isBoss else ROUND_GOLD
        fadeIn = max(0.0, min(1.0, (elapsedMs - 0.12) / 0.26))
        fadeOut = max(0.0, min(1.0, (elapsedMs - 0.78) / 0.20))
        bannerAlpha = _easeOutCubic(fadeIn) * (1 - fadeOut)
        if bannerAlpha <= 0:
            return
        scale = 1.0 + 0.18 * (1 - _easeOutCubic(fadeIn))
        rise = 16 * fadeOut
        alpha = int(255 * bannerAlpha)
        cy = windowHeight * 0.42 - rise

        chapter = _scaled(_outlinedText(ROUND_TITLE_FONT, chapterText, (255, 255, 255), outline=4, shadow=4), scale)
        stage = _scaled(_outlinedText(ROUND_NUMBER_FONT, stageText, accent, outline=3, shadow=3), scale)
        lineGap = 14
        total = chapter.get_height() + lineGap + stage.get_height()
        top = cy - total / 2

        chapter = chapter.copy()
        chapter.set_alpha(alpha)
        window.blit(chapter, chapter.get_rect(midtop=(windowWidth // 2, int(top))))

        # fading gold rule that grows out from the middle
        half = int(max(chapter.get_width(), 360) * 0.5 * _easeOutCubic(fadeIn))
        ruleY = int(top + chapter.get_height() + lineGap // 2 - 4)
        if half >= 2:
            rule = pygame.Surface((half * 2, 6), pygame.SRCALPHA)
            _drawFadeRule(rule, accent, 0, half * 2, 0, 2, 1)
            rule.set_alpha(alpha)
            window.blit(rule, (windowWidth // 2 - half, ruleY))

        stage = stage.copy()
        stage.set_alpha(alpha)
        window.blit(stage, stage.get_rect(midtop=(windowWidth // 2, int(top + chapter.get_height() + lineGap))))

    return draw

def wipeTransition(window, fromSurface, toSurface, screenSize, duration=WIPE_DURATION, bandWidth=WIPE_BAND_WIDTH,
                   vignette=None, clock=None, overlay=None, camera=None, onUpdate=None, banner=None):
    """Plays a full-screen wipe transition from `fromSurface` to `toSurface`.
    banner: optional callable(window, t) drawn over the wipe each frame (see makeStageBanner)."""
    width, height = screenSize
    if camera is not None:
        margin = camera.margin
        canvas = camera.bigSurface
    else:
        margin = 0
        canvas = window
    canvasHeight = canvas.get_height()
    band = makeWipeBand(canvasHeight, bandWidth)
    travelDistance = width + bandWidth

    def show(progress):
        if camera is not None:
            camera.present(window)
        elif vignette is not None:
            window.blit(vignette, (0, 0))
        if banner is not None:
            banner(window, progress)
        if overlay is not None:
            overlay(window, clock)
        pygame.display.update()

    if clock is None:
        clock = pygame.time.Clock()
    elapsed = 0
    while elapsed < duration:
        dt = min(clock.tick(60), 50)
        elapsed += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if camera is not None:
            camera.update(dt)
        if onUpdate is not None:
            onUpdate(dt)

        t = min(elapsed / duration, 1.0)
        eased = t * t * (3 - 2 * t)          # slow in, slow out: the curtain glides instead of marching
        bandX = -bandWidth + eased * travelDistance
        revealX = max(0, min(width, bandX + bandWidth / 2))

        canvas.blit(fromSurface, (0, 0))
        if revealX > 0:
            # once fully revealed also take the right padding ring.
            revealWidth = revealX + margin + (margin if revealX >= width else 0)
            canvas.blit(toSurface, (0, 0), pygame.Rect(0, 0, revealWidth, canvasHeight))
        canvas.blit(band, (bandX + margin, 0))
        show(t)

    # land exactly on the target frame, no band residue
    canvas.blit(toSurface, (0, 0))
    show(1.0)


# ---------- Camera zoom ----------

CAMERA_ZOOM_IDLE = 1.0            # no zoom -- plain 1:1 blit
CAMERA_ZOOM_SKILL_SELECT = 1.4
CAMERA_ZOOM_CLASH = 1.15
CAMERA_ZOOM_SKILL_PLAY = 1.35
CAMERA_ZOOM_SKILL_PLAY_FLOOR = CAMERA_ZOOM_CLASH
CAMERA_ZOOM_STATUS_EFFECT = 1.5
CAMERA_ZOOM_FIT_MARGIN = 24
CAMERA_ZOOM_LERP_RATE = 8.0       # higher = snaps to the target zoom faster

CAMERA_MAX_DT = 40   # ms

def lerpCameraZoom(current, target, dt):
    """Frame-rate independent smoothing toward `target`. `dt` is ms since last frame."""
    dt = min(dt, CAMERA_MAX_DT)
    blendFactor = 1 - math.exp(-CAMERA_ZOOM_LERP_RATE * dt / 1000)
    newZoom = current + (target - current) * blendFactor
    # Exponential easing only ever *approaches* the target.
    if abs(target - newZoom) < 0.0002:
        return target
    return newZoom

def lerpPoint(current, target, dt, rate=None):
    """Frame-rate independent smoothing of a 2D point toward `target`, same exponential-decay shape as lerpCameraZoom."""
    if rate is None:
        rate = CAMERA_FOCUS_LERP_RATE
    dt = min(dt, CAMERA_MAX_DT)
    blendFactor = 1 - math.exp(-rate * dt / 1000)
    cx, cy = current
    targetX, targetY = target
    return (cx + (targetX - cx) * blendFactor, cy + (targetY - cy) * blendFactor)


CAMERA_FOCUS_LERP_RATE = CAMERA_ZOOM_LERP_RATE

# How far the camera leans toward the mouse cursor.
CAMERA_MOUSE_FOLLOW_STRENGTH = 0.05
CAMERA_MOUSE_FOLLOW_MAX = 18

# The pan above nudges the whole scene a few pixels off its native position each frame.
CAMERA_PAN_MARGIN = CAMERA_MOUSE_FOLLOW_MAX + 20

# Parallax: the battlefield image is the far layer.
BG_PARALLAX = 0.45

def mouseFollowOffset(mousePos, screenSize, strength=CAMERA_MOUSE_FOLLOW_STRENGTH,
                       maxOffset=CAMERA_MOUSE_FOLLOW_MAX):
    """(dx, dy) to nudge the camera focus based on how far the cursor sits from the center of the window."""
    screenWidth, screenHeight = screenSize
    mouseX, mouseY = mousePos
    offsetX = (screenWidth / 2 - mouseX) * strength
    offsetY = (mouseY - screenHeight / 2) * strength
    dist = math.hypot(offsetX, offsetY)
    if dist > maxOffset:
        scale = maxOffset / dist
        offsetX *= scale
        offsetY *= scale
    return offsetX, offsetY


def screenToScene(pos, zoom, focus, pan=(0, 0)):
    """Inverse of applyCameraZoom's transform: convert a real mouse/window position back into the offscreen scene's coordinate space."""
    panX, panY = pan
    posX, posY = pos[0] - panX, pos[1] - panY
    if zoom == CAMERA_ZOOM_IDLE:
        return (posX, posY)
    focusX, focusY = focus
    return (focusX + (posX - focusX) / zoom, focusY + (posY - focusY) / zoom)


def sceneRectToScreen(rect, zoom, focus, pan=(0, 0)):
    """Where a scene-space rect lands on the real window: the same transform as applyCameraZoom / screenToScene."""
    fx, fy = focus
    panX, panY = pan
    left = fx + panX + (rect.left - fx) * zoom
    top = fy + panY + (rect.top - fy) * zoom
    return pygame.Rect(round(left), round(top),
                       max(1, round(rect.width * zoom)), max(1, round(rect.height * zoom)))

def visibleSourceRect(surfaceSize, windowSize, zoom, focus, pan=(0, 0), margin=0):
    """The integer rect of the padded scene surface that actually lands on the window for this zoom / focus / pan."""
    bigW, bigH = surfaceSize
    winW, winH = windowSize
    panX, panY = pan
    focusX, focusY = focus
    originX = focusX - focusX * zoom - margin * zoom + panX
    originY = focusY - focusY * zoom - margin * zoom + panY
    # +/-1px of slack: the crop is scaled to a whole-pixel size.
    left = max(0, math.floor(-originX / zoom) - 1)
    top = max(0, math.floor(-originY / zoom) - 1)
    right = min(bigW, math.ceil((winW - originX) / zoom) + 1)
    bottom = min(bigH, math.ceil((winH - originY) / zoom) + 1)
    if right <= left or bottom <= top:
        return None
    return pygame.Rect(left, top, right - left, bottom - top)

def applyCameraZoom(window, sceneSurface, zoom, focus, pan=(0, 0), margin=0):
    """Blit sceneSurface onto the real window scaled by `zoom`."""
    panX, panY = pan
    focusX, focusY = focus
    if zoom == CAMERA_ZOOM_IDLE:
        window.blit(sceneSurface, (panX - margin, panY - margin))
        return

    bigW, bigH = sceneSurface.get_size()
    winW, winH = window.get_size()

    # Only scale the part of the scene that actually lands on the window.
    srcRect = visibleSourceRect((bigW, bigH), (winW, winH), zoom, focus, pan, margin)
    if srcRect is None:
        return
    destSize = (max(1, round(srcRect.width * zoom)), max(1, round(srcRect.height * zoom)))
    scaled = pygame.transform.smoothscale(sceneSurface.subsurface(srcRect), destSize)
    # The crop is whole pixels, so the real scale is destSize / srcSize, a hair off `zoom`.
    ratioX = destSize[0] / srcRect.width
    ratioY = destSize[1] / srcRect.height
    destX = (focusX + panX) - (focusX + margin - srcRect.left) * ratioX
    destY = (focusY + panY) - (focusY + margin - srcRect.top) * ratioY
    window.blit(scaled, (round(destX), round(destY)))


# ---------- Shared camera rig ----------

class CameraRig:
    def __init__(self, screenSize, margin=CAMERA_PAN_MARGIN):
        self.screenSize = tuple(screenSize)
        self.margin = margin
        width, height = self.screenSize
        # bigSurface extends `margin` px past every edge.
        self.bigSurface = pygame.Surface((width + 2 * margin, height + 2 * margin)).convert()
        self.sceneSurface = self.bigSurface.subsurface((margin, margin, width, height))
        self.edgeVignette = makeEdgeVignette(self.screenSize)
        self.followOffset = (0, 0)
        # one clock for every screen.
        self.clock = pygame.time.Clock()

    @property
    def bigSize(self):
        return self.bigSurface.get_size()

    @property
    def pan(self):
        """The mouse-follow lean as WHOLE pixels."""
        return (round(self.followOffset[0]), round(self.followOffset[1]))

    def update(self, dt):
        """Ease the mouse-follow lean toward the cursor. Call once per frame."""
        target = mouseFollowOffset(pygame.mouse.get_pos(), self.screenSize)
        self.followOffset = lerpPoint(self.followOffset, target, dt)

    def backgroundOffset(self):
        """Where the background's top-left goes on bigSurface."""
        panX, panY = self.pan
        return (round(panX * (BG_PARALLAX - 1)), round(panY * (BG_PARALLAX - 1)))

    def drawBackground(self, background_img, target=None):
        """Draw the (margin-padded) battlefield with the parallax shift."""
        (target if target is not None else self.bigSurface).blit(background_img, self.backgroundOffset())

    def toScene(self, pos, zoom=CAMERA_ZOOM_IDLE, focus=(0, 0)):
        """Real window position -> scene coordinates (undoes pan and zoom)."""
        return screenToScene(pos, zoom, focus, self.pan)

    def visibleRect(self, zoom=CAMERA_ZOOM_IDLE, focus=(0, 0)):
        """Part of bigSurface that will be on screen this frame (or None)."""
        return visibleSourceRect(self.bigSurface.get_size(), self.screenSize, zoom, focus,
                                 self.pan, self.margin)

    def present(self, window, zoom=CAMERA_ZOOM_IDLE, focus=(0, 0)):
        """Draw bigSurface onto the window with the current pan/zoom, then the edge vignette on top."""
        applyCameraZoom(window, self.bigSurface, zoom, focus, self.pan, self.margin)
        drawEdgeVignette(window, self.edgeVignette)


# ---------- Skill cards ----------

CARD_WIDTH = 92
CARD_HEIGHT = 130
CARD_GAP = 10              # space between the two adjacent cards
CARD_OFFSET_X = -10
CARD_HEADROOM = 18
CARD_PADDING = 6
CARD_BORDER_RADIUS = 10
CARD_ROW_HEIGHT = 14       # each stat row (SPD / DMG / SAN / EFF)
CARD_HEADER_GAP = 5
CARD_ROWS_GAP = 4          # divider line down to the first stat row
CARD_SANITY_HEIGHT = 16

ICON_NAMES = ["skill1", "skill2", "block", "dodge", "heal", "buff", "debuff", "ult", "change"]
CARD_ICON_SIZE = 24

# Stat-row icons: each row's text label is replaced by the icon below.
STAT_ICON_FILES = {
    "SPD":  "stat_speed",
    "DMG":  "stat_damage",
    "HEAL": "stat_heal",
    "RED":  "stat_reduce",
    "EFF":  "stat_effect",
    "SAN":  "stat_sanity",
}
STAT_ICON_SIZE = 13
CHANGE_ICON_SIZE = 18
CHANGE_ICON_MARGIN = 6

def fitIcon(img, size):
    """Crop away the transparent margin, then scale to fit a size x size box (keeps proportions)."""
    img = img.subsurface(img.get_bounding_rect()).copy()
    scale = size / max(img.get_size())
    scaledWidth, scaledHeight = max(1, round(img.get_width() * scale)), max(1, round(img.get_height() * scale))
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    scaled = pygame.transform.smoothscale(img, (scaledWidth, scaledHeight))
    out.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
    return out

_ICON_SOURCES = {}
_scaledIconCache = {}

def loadSkillIcons():
    """Call once AFTER pygame.display.set_mode."""
    icons = {}
    for name in ICON_NAMES:
        img = pygame.image.load(f"assets/img/icon/{name}.png").convert_alpha()
        _ICON_SOURCES[name] = img.subsurface(img.get_bounding_rect()).copy()   # crop once, not per frame
        icons[name] = fitIcon(img, CHANGE_ICON_SIZE if name == "change" else CARD_ICON_SIZE)

    # Optional stat-row icons.
    for fileName in set(STAT_ICON_FILES.values()):
        try:
            img = pygame.image.load(f"assets/img/icon/{fileName}.png").convert_alpha()
        except (FileNotFoundError, pygame.error):
            print(f"[stat icon missing] assets/img/icon/{fileName}.png -- using the text label")
            continue
        _ICON_SOURCES[fileName] = img.subsurface(img.get_bounding_rect()).copy()
    return icons

def _drawStatLabel(surface, label, x, y, S):
    """Draws a stat row's label at."""
    fileName = STAT_ICON_FILES.get(label)
    size = S(STAT_ICON_SIZE)
    icon = _iconAtSize(fileName, size) if fileName in _ICON_SOURCES else None
    if icon is not None:
        _blitInked(surface, icon, (x, y), S(1))
        return icon.get_width()
    rect = _drawInkedText(surface, label, CARD_STAT_LABEL_COLOR, 9999, S(12), S(12), S(1), topleft=(x, y))
    return rect.width

def _iconAtSize(name, size, icons=None):
    """The icon scaled straight from its full-res (pre-cropped) source to fit a size x size box."""
    key = (name, size)
    surf = _scaledIconCache.get(key)
    if surf is None:
        source = _ICON_SOURCES.get(name)
        if source is None:
            return icons.get(name) if icons else None
        scale = size / max(source.get_size())
        scaledWidth = max(1, round(source.get_width() * scale))
        scaledHeight = max(1, round(source.get_height() * scale))
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        scaled = pygame.transform.smoothscale(source, (scaledWidth, scaledHeight))
        surf.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
        if len(_scaledIconCache) > 128:
            _scaledIconCache.clear()
        _scaledIconCache[key] = surf
    return surf

def _roundHalfUp(value):
    return int(value + 0.5)

def _rangeText(low, high, suffix=""):
    """'low-high' (or just 'low' when the two are equal), e.g. '11-19' or '25-75%'."""
    if low == high:
        return f"{low}{suffix}"
    return f"{low}-{high}{suffix}"

def skillOutputRange(skillDef, sanity=0.5, attackMult=1.0):
    """ of what a damage or heal skill can actually roll for its PRIMARY target."""
    flipMults = FLIP_DAMAGE_MULTIPLIERS.values()
    base = skillDef.damage * attackMult * sanityDamageMultiplier(sanity)
    return _roundHalfUp(base * min(flipMults)), _roundHalfUp(base * max(flipMults))

def guardReductionRange(skillDef):
    """(min, max) fraction of an incoming hit a guard stance removes."""
    table = (DODGE_FLIP_MITIGATION_MULTIPLIERS if getattr(skillDef, "icon", None) == "dodge"
             else BLOCK_FLIP_MITIGATION_MULTIPLIERS)
    values = table.values()
    return min(values), max(values)

def _cardRows(skillDef, sprite=None):
    """The stat rows a card shows."""
    sanity = sprite.get("sanity", 0.5) if sprite is not None else 0.5
    attackMult = sprite["stats"].attackMult if sprite is not None and "stats" in sprite else 1.0
    rows = [("SPD", str(skillDef.speed) if skillDef else "-")]

    if skillDef is not None and isGuardSkill(skillDef):
        minReduction, maxReduction = guardReductionRange(skillDef)
        rows.append(("RED", _rangeText(_roundHalfUp(minReduction * 100), _roundHalfUp(maxReduction * 100), "%")))
    elif skillDef is not None and skillDef.damage and isHealSkill(skillDef):
        rows.append(("HEAL", _rangeText(*skillOutputRange(skillDef, sanity))))
    elif skillDef is not None and skillDef.damage and skillDef.kind == "damage":
        rows.append(("DMG", _rangeText(*skillOutputRange(skillDef, sanity, attackMult))))
    else:
        rows.append(("DMG", "-"))

    if skillDef is not None and skillDef.effects:
        effLabel = prettyEffectName(skillDef.effects[0].effect)
        if len(skillDef.effects) > 1:
            effLabel += " +" + str(len(skillDef.effects) - 1)
        rows.append(("EFF", effLabel))
    return rows

def getButtonRect(sprite):
    """Two card rects, side by side, to the right of the sprite, vertically centered on it as a pair."""
    stats = sprite["stats"]
    baseX = stats.rect.right + CARD_OFFSET_X
    baseY = stats.rect.centery - CARD_HEIGHT // 2

    return [
        pygame.Rect(baseX + i * (CARD_WIDTH + CARD_GAP), baseY, CARD_WIDTH, CARD_HEIGHT)
        for i in range(len(sprite["buttonSkills"]))
    ]

# No card box any more.
CARD_TEXT_COLOR = (255, 255, 255)
CARD_HOVER_COLOR = (255, 215, 0)
CARD_LOCKED_COLOR = (225, 100, 100)
# A sanity-locked card is drawn as a faded, grey ghost; only the "LOW SANITY" label stays bright.
CARD_LOCKED_FADE_ALPHA = 80                  # 0 = invisible, 255 = untouched
CARD_LOCKED_TEXT_COLOR = (170, 170, 182)
CARD_LOW_SANITY_COLOR = (255, 70, 70)
CARD_RULE_COLOR = (170, 170, 185)            # the fading rules between sections
CARD_INK = (10, 8, 16)                       # outline + shadow colour
CARD_SANITY_UP_COLOR = (110, 225, 120)       # sanity gained (+) on the card's SAN row
CARD_SANITY_DOWN_COLOR = (235, 90, 90)       # sanity spent (-)
CARD_STAT_LABEL_COLOR = (190, 190, 205)
CARD_GLOW_COLOR = (255, 210, 110)

# ---------- small text-fit helper ----------

_fontSizeCache = {}

def _fontOfSize(size):
    font = _fontSizeCache.get(size)
    if font is None:
        font = pygame.font.Font('assets/font/monogram.ttf', size)
        _fontSizeCache[size] = font
    return font

_fittedTextCache = {}

def renderFittedText(text, color, maxWidth, startSize=20, minSize=12):
    """Cached: the font-size search and the render itself are both real work."""
    key = (text, color, maxWidth, startSize, minSize)
    surf = _fittedTextCache.get(key)
    if surf is not None:
        return surf
    if len(_fittedTextCache) >= 512:
        _fittedTextCache.clear()

    size = startSize
    font = _fontOfSize(size)
    while size > minSize and font.size(text)[0] > maxWidth:
        size -= 2
        font = _fontOfSize(size)
    surf = font.render(text, True, color)
    _fittedTextCache[key] = surf
    return surf

def prettyEffectName(effect):
    """Turns an effect function (e.g."""
    if effect is None:
        return "-"
    name = effect.__name__
    words = []
    current = ""
    for character in name:
        if character.isupper() and current:
            words.append(current)
            current = character
        else:
            current += character
    words.append(current)
    return " ".join(word.capitalize() for word in words)

# ---------- hover highlight ----------

_cardGlowCache = {}
CARD_GLOW_ALPHA = 55

def _buildCardGlow(width, height, radius):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(surf, (*CARD_GLOW_COLOR, CARD_GLOW_ALPHA), surf.get_rect(), border_radius=radius)
    return surf

def drawCardGlow(window, rect, radius=CARD_BORDER_RADIUS):
    key = (rect.width, rect.height, radius)
    glow = _cardGlowCache.get(key)
    if glow is None:
        if len(_cardGlowCache) > 64:
            _cardGlowCache.clear()
        glow = _buildCardGlow(*key)
        _cardGlowCache[key] = glow
    window.blit(glow, rect.topleft)

_labelTextCache = {}

def _cachedLabelText(size, text, color):
    """Same idea as renderFittedText's cache, for the small fixed row labels."""
    key = (size, text, color)
    surf = _labelTextCache.get(key)
    if surf is None:
        surf = _fontOfSize(size).render(text, True, color)
        _labelTextCache[key] = surf
    return surf

# ---------- card flip ----------

CARD_FLIP_DURATION = 320
CARD_FLIP_STAGGER = 70

CHANGE_ICON_TURN = -180

def _changeIconAngle(sprite, now):
    """How far the shared change icon is turned right now."""
    spin = sprite.get("changeSpin")
    if spin is None:
        return 0.0
    spinProgress = max(0.0, min(1.0, (now - spin["start"]) / spin["duration"]))
    eased = 0.5 - 0.5 * math.cos(math.pi * spinProgress)
    return spin["from"] + (spin["to"] - spin["from"]) * eased

_inkSilhouetteCache = {}
_inkTextCache = {}
_iconGlowCache = {}
_INK_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))

def _silhouette(image):
    entry = _inkSilhouetteCache.get(id(image))
    if entry is None or entry[0] is not image:
        silhouetteImage = image.copy()
        silhouetteImage.fill((*CARD_INK, 255), special_flags=pygame.BLEND_RGBA_MULT)
        if len(_inkSilhouetteCache) > 128:
            _inkSilhouetteCache.clear()
        entry = (image, silhouetteImage)
        _inkSilhouetteCache[id(image)] = entry
    return entry[1]

def _blitInked(surface, image, pos, outlineSize):
    """Blits an icon with a dark outline `o` px thick and a drop shadow."""
    silhouetteImage = _silhouette(image)
    x, y = pos
    surface.blit(silhouetteImage, (x + outlineSize, y + outlineSize * 2))
    for dx, dy in _INK_OFFSETS:
        surface.blit(silhouetteImage, (x + dx * outlineSize, y + dy * outlineSize))
    surface.blit(image, pos)

def _drawInkedText(surface, text, color, maxWidth, startSize, minSize, outlineSize, **anchor):
    """Fitted text with a dark outline + drop shadow, no backing."""
    key = (text, color, maxWidth, startSize, minSize, outlineSize)
    entry = _inkTextCache.get(key)
    if entry is None:
        front = renderFittedText(text, color, maxWidth, startSize, minSize)
        dark = renderFittedText(text, CARD_INK, maxWidth, startSize, minSize)
        pad = outlineSize * 2
        surf = pygame.Surface((front.get_width() + pad * 2, front.get_height() + pad * 2), pygame.SRCALPHA)
        surf.blit(dark, (pad + outlineSize, pad + outlineSize * 2))
        for dx, dy in _INK_OFFSETS:
            surf.blit(dark, (pad + dx * outlineSize, pad + dy * outlineSize))
        surf.blit(front, (pad, pad))
        if len(_inkTextCache) > 512:
            _inkTextCache.clear()
        entry = (surf, pad, front.get_size())
        _inkTextCache[key] = entry
    surf, pad, size = entry
    rect = pygame.Rect((0, 0), size)
    for name, value in anchor.items():
        setattr(rect, name, value)
    surface.blit(surf, (rect.x - pad, rect.y - pad))
    return rect

def _drawFadeRule(surface, color, startX, endX, y, thickness, outlineSize):
    """A thin horizontal rule that fades out at both ends, with a faint dark shadow just under it -- the divider between card sections."""
    width = max(2, endX - startX)
    rule = pygame.Surface((width, thickness + outlineSize + 1), pygame.SRCALPHA)
    for pixelColumn in range(width):
        fadeProgress = pixelColumn / (width - 1)
        fade = 1 - abs(2 * fadeProgress - 1) ** 2.5
        pygame.draw.line(rule, (*CARD_INK, int(190 * fade)), (pixelColumn, outlineSize), (pixelColumn, outlineSize + thickness - 1))
        pygame.draw.line(rule, (*color, int(255 * fade)), (pixelColumn, 0), (pixelColumn, thickness - 1))
    surface.blit(rule, (startX, y))

def _iconGlow(radius):
    glow = _iconGlowCache.get(radius)
    if glow is None:
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for ringRadius in range(radius, 0, -2):
            alpha = int(95 * (1 - ringRadius / radius) ** 1.4) + 4
            pygame.draw.circle(glow, (*CARD_HOVER_COLOR, alpha), (radius, radius), ringRadius)
        _iconGlowCache[radius] = glow
    return glow

def _drawSkillCardFace(surface, rect, sprite, skillName, icons, hovered=False, k=1.0):
    """One skill card's full face, drawn onto `surface` at `rect` (already in the surface's own pixels)."""
    def S(v):
        return max(1, round(v * k))

    skillDef = getSkillDef(sprite["name"], skillName)
    locked = skillDef is not None and skillLockedBySanity(sprite, skillDef)
    hovered = hovered and not locked

    textColor = CARD_LOCKED_TEXT_COLOR if locked else (CARD_HOVER_COLOR if hovered else CARD_TEXT_COLOR)
    ruleColor = CARD_RULE_COLOR if locked else (CARD_HOVER_COLOR if hovered else CARD_RULE_COLOR)

    # Locked: everything below is drawn on a scratch layer that is blitted back faded at the end.
    finalSurface = surface
    if locked:
        surface = pygame.Surface(finalSurface.get_size(), pygame.SRCALPHA)
    o = S(1)
    pad = S(CARD_PADDING)

    # header: icon centered on top (gold glow behind it on hover), name underneath
    headerY = rect.top + pad
    iconSize = S(CARD_ICON_SIZE)
    if hovered:
        glow = _iconGlow(S(32))
        surface.blit(glow, glow.get_rect(center=(rect.centerx, headerY + iconSize // 2)))
    icon = _iconAtSize(skillDef.icon, iconSize, icons) if skillDef else None
    if icon is not None:
        iconSurf = _cachedPerImage(_fadedCache, icon, _buildFaded) if locked else icon
        _blitInked(surface, iconSurf, iconSurf.get_rect(midtop=(rect.centerx, headerY)).topleft, o)

    nameY = headerY + iconSize + S(4)
    nameRect = _drawInkedText(surface, skillName, textColor, rect.width - pad * 2,
                              S(17), S(12), o, midtop=(rect.centerx, nameY))

    dividerY = nameRect.bottom + S(CARD_HEADER_GAP)
    _drawFadeRule(surface, ruleColor, rect.left + pad, rect.right - pad, dividerY, S(1), o)

    # stat rows -- see _cardRows for which ones a given skill gets
    rowY = dividerY + S(CARD_ROWS_GAP) + S(1)
    for label, value in _cardRows(skillDef, sprite):
        labelWidth = _drawStatLabel(surface, label, rect.left + pad, rowY, S)
        valueMaxWidth = rect.width - pad * 2 - labelWidth - S(6)
        _drawInkedText(surface, value, textColor, valueMaxWidth, S(14), S(10), o,
                       topright=(rect.right - pad, rowY))
        rowY += S(CARD_ROW_HEIGHT)

    # sanity-cost section along the bottom edge
    sanityTop = rect.bottom - pad - S(CARD_SANITY_HEIGHT)
    _drawFadeRule(surface, ruleColor, rect.left + pad, rect.right - pad, sanityTop - S(3), S(1), o)
    sanityLabelWidth = _drawStatLabel(surface, "SAN", rect.left + pad, sanityTop + S(1), S)
    # each part gets its own colour: spent sanity (-) red, recovered (+) green
    sanityParts = []
    if skillDef is not None and skillDef.sanityCost > 0:
        sanityParts.append((f"-{round(skillDef.sanityCost * 100)}%", CARD_SANITY_DOWN_COLOR))
    if skillDef is not None and skillDef.sanityRecover > 0:
        sanityParts.append((f"+{round(skillDef.sanityRecover * 100)}%", CARD_SANITY_UP_COLOR))
    costMaxWidth = rect.width - pad * 2 - sanityLabelWidth - S(6)
    if not sanityParts:
        _drawInkedText(surface, "-", textColor, costMaxWidth, S(14), S(9), o,
                       topright=(rect.right - pad, sanityTop + S(1)))
    else:
        gap = S(4)
        partWidth = (costMaxWidth - gap * (len(sanityParts) - 1)) // len(sanityParts)
        right = rect.right - pad
        for text, color in reversed(sanityParts):
            r = _drawInkedText(surface, text, color, partWidth, S(14), S(9), o,
                               topright=(right, sanityTop + S(1)))
            right = r.left - gap

    # "LOW SANITY" across the stats: WHY the card can't be used. The rest of the card is faded
    # back so this is the only bright thing on it (the sanity numbers above are red too).
    if locked:
        surface.set_alpha(CARD_LOCKED_FADE_ALPHA)
        finalSurface.blit(surface, (0, 0))
        _drawInkedText(finalSurface, "LOW SANITY", CARD_LOW_SANITY_COLOR, rect.width - pad * 2 - S(6),
                       S(18), S(10), o, center=(rect.centerx, (dividerY + sanityTop) // 2))

# ---------- Card render cache ----------

CARD_HI_SCALE = 2

_cardFaceCache = {}       # state key -> hi-res face
_cardScaledCache = {}

def _cachedCardFace(sprite, skillName, icons, hovered):
    """The hi-res face for this card."""
    skillDef = getSkillDef(sprite["name"], skillName)
    locked = skillDef is not None and skillLockedBySanity(sprite, skillDef)
    hovered = hovered and not locked
    rows = tuple(_cardRows(skillDef, sprite))
    key = (sprite["name"], skillName, locked, hovered, rows)
    face = _cardFaceCache.get(key)
    if face is None:
        if len(_cardFaceCache) > 48:
            _cardFaceCache.clear()
            _cardScaledCache.clear()
        head = CARD_HEADROOM * CARD_HI_SCALE
        size = (CARD_WIDTH * CARD_HI_SCALE, CARD_HEIGHT * CARD_HI_SCALE + head)
        face = pygame.Surface(size, pygame.SRCALPHA)
        cardRect = pygame.Rect(0, head, CARD_WIDTH * CARD_HI_SCALE, CARD_HEIGHT * CARD_HI_SCALE)
        _drawSkillCardFace(face, cardRect, sprite, skillName, icons, hovered, CARD_HI_SCALE)
        _cardFaceCache[key] = face
    return key, face

def _faceAtSize(key, face, size):
    """The cached hi-res face scaled down to `size` (reused while size holds still)."""
    cached = _cardScaledCache.get(key)
    if cached is not None and cached[0] == size:
        return cached[1]
    scaled = pygame.transform.smoothscale(face, size)
    _cardScaledCache[key] = (size, scaled)
    return scaled

def drawSkillButtons(window, sprite, icons, mousePos=None, zoom=1.0, focus=(0, 0), pan=(0, 0)):
    """Draws the two skill cards for `sprite` straight onto the REAL window (call it after CAMERA.present)."""
    sceneRects = getButtonRect(sprite)
    rects = [sceneRectToScreen(r, zoom, focus, pan) for r in sceneRects]
    slots = sprite["buttonSlots"]
    flips = sprite.setdefault("cardFlips", {})
    now = pygame.time.get_ticks()

    for i, (cardRect, sceneRect, skillName) in enumerate(zip(rects, sceneRects, sprite["buttonSkills"])):
        # the cached face carries CARD_HEADROOM extra rows on top.
        headPx = round(cardRect.height * CARD_HEADROOM / CARD_HEIGHT)
        rect = pygame.Rect(cardRect.x, cardRect.y - headPx, cardRect.width, cardRect.height + headPx)
        flip = flips.get(i)
        t = 0.0
        if flip is not None:
            t = (now - flip["start"]) / CARD_FLIP_DURATION
            if t >= 1.0:
                del flips[i]
                flip = None

        if flip is None:
            hovered = mousePos is not None and sceneRect.collidepoint(mousePos)
            key, face = _cachedCardFace(sprite, skillName, icons, hovered)
            window.blit(_faceAtSize(key, face, rect.size), rect.topleft)
            continue

        # first half: the old face closes to an edge; second half: the new face opens
        shown = flip["old"] if t < 0.5 else skillName
        key, face = _cachedCardFace(sprite, shown, icons, False)
        if t < 0.0:
            # still waiting out its stagger -- keep showing the old card as is
            window.blit(_faceAtSize(key, face, rect.size), rect.topleft)
            continue

        openness = abs(math.cos(math.pi * t))               # 1 -> 0 -> 1
        width = max(2, int(rect.width * openness))
        height = int(rect.height * (0.92 + 0.08 * openness))   # tiny dip in height sells the turn
        flipped = pygame.transform.smoothscale(face, (width, height))   # straight from the hi-res render
        window.blit(flipped, flipped.get_rect(center=rect.center))

    # one shared "change" icon, floating above the pair.
    if rects and any(len(s) > 1 for s in slots):
        change = _iconAtSize("change", CHANGE_ICON_SIZE * CARD_HI_SCALE, icons)
        midX = (rects[0].right + rects[1].left) // 2 if len(rects) > 1 else rects[0].centerx
        topY = min(r.top for r in rects)
        scale = zoom
        iconPx = max(1, round(CHANGE_ICON_SIZE * scale))
        centerY = topY - round(CHANGE_ICON_MARGIN * scale) - iconPx // 2
        angle = _changeIconAngle(sprite, now)
        turned = pygame.transform.rotozoom(change, -angle, scale / CARD_HI_SCALE)   # negative = clockwise
        window.blit(turned, turned.get_rect(center=(midX, centerY)))

def getClickedButton(sprite, pos):
    if sprite is None:
        return None
    for i, rect in enumerate(getButtonRect(sprite)):
        if rect.collidepoint(pos):
            return i
    return None

def _cardFlipInProgress(sprite, buttonIndex, now=None):
    """True while buttonIndex's own card flip hasn't finished settling on its new face yet."""
    if now is None:
        now = pygame.time.get_ticks()
    flip = sprite.get("cardFlips", {}).get(buttonIndex)
    return flip is not None and now < flip["start"] + CARD_FLIP_DURATION

def cycleButton(sprite, buttonIndex, flipDelay=0):
    """Switches buttonIndex to its next skill option."""
    if _cardFlipInProgress(sprite, buttonIndex):
        return
    options = sprite["buttonSlots"][buttonIndex]
    if len(options) > 1:
        # start the card flip (see drawSkillButtons) from the skill it's leaving
        sprite.setdefault("cardFlips", {})[buttonIndex] = {
            "start": pygame.time.get_ticks() + flipDelay,
            "old": sprite["buttonSkills"][buttonIndex],
        }
    sprite["buttonIndex"][buttonIndex] = (sprite["buttonIndex"][buttonIndex] + 1) % len(options)
    sprite["buttonSkills"][buttonIndex] = options[sprite["buttonIndex"][buttonIndex]]

def cycleAllButtons(sprite):
    """Switch every skill button of this sprite to its next option at once."""
    slots = sprite["buttonSlots"]
    now = pygame.time.get_ticks()
    if any(_cardFlipInProgress(sprite, i, now) for i in range(len(slots))):
        return
    if any(len(s) > 1 for s in slots):
        # the change icon turns along with the flip.
        previous = sprite.get("changeSpin")
        sprite["changeSpin"] = {
            "start": now,
            "duration": CARD_FLIP_DURATION + CARD_FLIP_STAGGER * (len(slots) - 1),
            "from": _changeIconAngle(sprite, now),
            "to": (previous["to"] if previous else 0) + CHANGE_ICON_TURN,
        }
    for i in range(len(slots)):
        cycleButton(sprite, i, flipDelay=i * CARD_FLIP_STAGGER)


# ---------- Selection / turn state ----------

def getSelectableSprite(sprites, pos):
    """The player sprite under the mouse (acted ones included, so their action can be changed)."""
    for sprite in sprites:
        if (sprite["side"] == "left" and not sprite["dead"]
                and sprite["stats"].rect.collidepoint(pos)):
            return sprite
    return None

def getSpriteAt(sprites, pos):
    """Any sprite (either side, dead or alive) under the mouse."""
    for sprite in sprites:
        if sprite["stats"].rect.collidepoint(pos):
            return sprite
    return None

def handleClick(pos, sprites, selectedSprite):
    """Select a player sprite under the click."""
    clickedSprite = getSelectableSprite(sprites, pos)

    if selectedSprite is not None:
        selectedSprite["selected"] = False
        return None

    if clickedSprite is not None:
        clickedSprite["selected"] = True
    return clickedSprite

def getHoveredSprite(sprites, selectedSprite, pendingButtonIndex, pos, skillDef=None):
    """Sprite to outline on hover: a player you could select, or whoever you'd actually hit with the pending skill."""
    if pendingButtonIndex is not None:
        if isFriendlyTargetSkill(skillDef):
            return getAllyTarget(sprites, selectedSprite, pos, skillDef)
        return getEnemyTarget(sprites, selectedSprite, pos)
    if getClickedButton(selectedSprite, pos) is not None:
        return None
    if selectedSprite is not None:
        return None
    return getSelectableSprite(sprites, pos)

def newTurn(sprites):
    for sprite in sprites:
        if not sprite["dead"]:
            # Stun is NOT applied here anymore.
            sprite["acted"] = False
        sprite["selected"] = False
        # An unspent guard doesn't carry over.
        sprite["guard"] = None
        if sprite.get("ultLock", 0) > 0:
            sprite["ultLock"] -= 1      # a boss's ult-lock wears off

def allPlayersActed(sprites):
    return all(sprite["acted"] for sprite in sprites if sprite["side"] == "left" and not sprite["dead"])

def checkDead(sprites):
    for sprite in sprites:
        # Match hpLabel's rounding, not the raw float.
        if round(sprite["stats"].hp) <= 0:
            sprite["dead"] = True

def markNewDeaths(sprites):
    """checkDead, but returns the sprites that JUST died (weren't dead before this call)."""
    before = {id(sprite) for sprite in sprites if sprite["dead"]}
    checkDead(sprites)
    return [sprite for sprite in sprites if sprite["dead"] and id(sprite) not in before]

def _spriteIsDown(sprite):
    # Same rounding checkDead/hpLabel use.
    return sprite["dead"] or round(sprite["stats"].hp) <= 0

def isActionVoid(action):
    """True if this queued action can no longer happen: its caster is down, or the sprite it's aimed at is."""
    return _spriteIsDown(action["sprite"]) or _spriteIsDown(action["target"])

def purgeVoidActions(actionQueue):
    """Drops every still-queued action that isActionVoid, in place (callers hold a reference to this list)."""
    before = len(actionQueue)
    actionQueue[:] = [action for action in actionQueue if not isActionVoid(action)]
    return before - len(actionQueue)

# ---------- Stun ----------

STUN_SKIP = "stunned"

def isStunned(sprite):
    return bool(sprite["stats"].stunned)

def checkBattleResult(sprites):
    playersAlive = any(sprite["side"] == "left" and not sprite["dead"] for sprite in sprites)
    enemiesAlive = any(sprite["side"] == "right" and not sprite["dead"] for sprite in sprites)

    if not enemiesAlive:
        return "victory"
    if not playersAlive:
        return "defeat"

# ---------- Boss sanity regen ----------
# A boss ("ultChance") can't be drained, and its ults cost sanity, so on its own its sanity only ever falls.
# Every 1 or 2 rounds (random) it now recovers a random 10-25%, up to BOSS_SANITY_REGEN_CAP.
BOSS_SANITY_REGEN_MIN = 0.10
BOSS_SANITY_REGEN_MAX = 0.25
BOSS_SANITY_REGEN_EVERY = (1, 2)    # rounds between regens, picked at random each time
BOSS_SANITY_REGEN_CAP = 0.75        # regen never pushes a boss past this (1.0 = no cap; see the balance note)

def regenBossSanity(sprites):
    """Call once per round end. Bosses recover sanity on a random 1-2 round timer."""
    for sprite in sprites:
        if sprite["dead"] or sprite.get("ultChance") is None:
            continue
        if sprite.get("_sanityRegenIn") is None:
            sprite["_sanityRegenIn"] = random.randint(*BOSS_SANITY_REGEN_EVERY)
        sprite["_sanityRegenIn"] -= 1
        if sprite["_sanityRegenIn"] > 0:
            continue
        sprite["_sanityRegenIn"] = random.randint(*BOSS_SANITY_REGEN_EVERY)
        before = sprite.get("sanity", 0.5)
        if before >= BOSS_SANITY_REGEN_CAP:
            continue
        gain = random.uniform(BOSS_SANITY_REGEN_MIN, BOSS_SANITY_REGEN_MAX)
        sprite["sanity"] = min(BOSS_SANITY_REGEN_CAP, before + gain)    # the "+N%" popup comes from trackSanityChanges

def resolveRound(sprites, roundNumber):
    checkDead(sprites)
    result = checkBattleResult(sprites)

    if result is None:
        regenBossSanity(sprites)
        decayStatusEffects(sprites)
        newTurn(sprites)
        roundNumber += 1

    return result, roundNumber

# ---------- Round HUD and battle result ----------
ROUND_MARGIN = 24
ROUND_GOLD = (255, 215, 0)
ROUND_POP_MS = 450
ROUND_TITLE_IN_MS = 300
ROUND_TITLE_HOLD_MS = 900
ROUND_TITLE_OUT_MS = 400
ROUND_TITLE_MS = ROUND_TITLE_IN_MS + ROUND_TITLE_HOLD_MS + ROUND_TITLE_OUT_MS
ROUND_TITLE_Y_FRAC = 0.30
ROUND_NUMBER_FONT = pygame.font.Font('assets/font/monogram.ttf', 64)
ROUND_TITLE_FONT = pygame.font.Font('assets/font/monogram.ttf', 110)

_roundState = {"last": None, "changedAt": 0}
_roundTextCache = {}

def _easeOutCubic(progress):
    return 1 - (1 - progress) ** 3

def _easeOutBack(progress):
    overshoot = 1.70158
    overshootPlusOne = overshoot + 1
    return 1 + overshootPlusOne * (progress - 1) ** 3 + overshoot * (progress - 1) ** 2

def _outlinedText(font, text, color, outline=3, shadow=3):
    """Text with a solid dark outline and a hard drop shadow, no background."""
    key = (id(font), text, color, outline, shadow)
    surf = _roundTextCache.get(key)
    if surf is None:
        front = font.render(text, True, color)
        dark = font.render(text, True, (10, 8, 16))
        pad = outline + shadow
        surf = pygame.Surface((front.get_width() + pad * 2, front.get_height() + pad * 2), pygame.SRCALPHA)
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx * dx + dy * dy <= outline * outline + 1:
                    surf.blit(dark, (pad + dx + shadow, pad + dy + shadow))   # shadow layer
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx * dx + dy * dy <= outline * outline + 1:
                    surf.blit(dark, (pad + dx, pad + dy))                      # outline layer
        surf.blit(front, (pad, pad))
        if len(_roundTextCache) > 200:
            _roundTextCache.clear()
        _roundTextCache[key] = surf
    return surf

def _scaled(surf, scale):
    if abs(scale - 1.0) < 0.01:
        return surf
    return pygame.transform.smoothscale(
        surf, (max(1, int(surf.get_width() * scale)), max(1, int(surf.get_height() * scale))))

def _drawRoundCorner(window, roundNumber, screenWidth, sinceChange):
    popProgress = min(1.0, sinceChange / ROUND_POP_MS)
    scale = 1.0 if popProgress >= 1 else max(0.9, 1.0 + 0.35 * (1 - _easeOutBack(popProgress)))

    title = _outlinedText(FONT, "ROUND", ROUND_GOLD, outline=2, shadow=2)
    # number flashes gold, then settles to white
    flash = max(0.0, 1 - sinceChange / (ROUND_POP_MS * 1.6))
    color = tuple(int(255 + (channel - 255) * flash) for channel in ROUND_GOLD)
    number = _scaled(_outlinedText(ROUND_NUMBER_FONT, str(roundNumber), color, outline=3, shadow=3), scale)

    right = screenWidth - ROUND_MARGIN
    window.blit(title, title.get_rect(midtop=(right - number.get_width() // 2, ROUND_MARGIN - 4)))
    window.blit(number, number.get_rect(midtop=(right - number.get_width() // 2, ROUND_MARGIN + title.get_height() - 12)))

def _drawRoundTitle(window, roundNumber, elapsed):
    if elapsed >= ROUND_TITLE_MS:
        return
    windowWidth, windowHeight = window.get_size()
    cy = windowHeight * ROUND_TITLE_Y_FRAC

    if elapsed < ROUND_TITLE_IN_MS:
        slideProgress = _easeOutCubic(elapsed / ROUND_TITLE_IN_MS)
        scale, alpha, rise = 1.7 - 0.7 * slideProgress, int(255 * slideProgress), 0
    elif elapsed < ROUND_TITLE_IN_MS + ROUND_TITLE_HOLD_MS:
        hold = (elapsed - ROUND_TITLE_IN_MS) / ROUND_TITLE_HOLD_MS
        scale, alpha, rise = 1.0 + 0.04 * hold, 255, 0          # slow creep so it isn't frozen
    else:
        slideProgress = (elapsed - ROUND_TITLE_IN_MS - ROUND_TITLE_HOLD_MS) / ROUND_TITLE_OUT_MS
        scale, alpha, rise = 1.04, int(255 * (1 - slideProgress)), slideProgress * slideProgress * 40

    # "ROUND" in gold above, the number in white big beneath -- stacked, no frame
    word = _scaled(_outlinedText(ROUND_TITLE_FONT, "ROUND", ROUND_GOLD, outline=4, shadow=4), scale)
    number = _scaled(_outlinedText(ROUND_TITLE_FONT, str(roundNumber), (255, 255, 255), outline=4, shadow=4), scale)
    letterGap = -10
    total = word.get_height() + letterGap + number.get_height()
    top = cy - total / 2 - rise

    for surf, y in ((word, top), (number, top + word.get_height() + letterGap)):
        surf = surf.copy()
        surf.set_alpha(alpha)
        window.blit(surf, surf.get_rect(midtop=(windowWidth // 2, int(y))))

def drawRoundInfo(window, roundNumber, screenWidth):
    """Call every frame."""
    now = pygame.time.get_ticks()
    if roundNumber != _roundState["last"]:
        _roundState["last"] = roundNumber
        _roundState["changedAt"] = now
    elapsed = now - _roundState["changedAt"]

    _drawRoundCorner(window, roundNumber, screenWidth, elapsed)
    _drawRoundTitle(window, roundNumber, elapsed)

# ---------- End-turn prompt & battle speed control ----------

END_TURN_TITLE = "KANA"
END_TURN_KEY = "ENTER"

BATTLE_SPEEDS = (1.0, 1.5, 2.0)
BATTLE_SPEED_LABELS = (">", ">>", ">>>")   # 1x, 1.5x, 2x

def nextBattleSpeed(speed):
    """The speed after `speed` in 1x -> 1.5x -> 2x -> 1x order."""
    i = BATTLE_SPEEDS.index(speed) if speed in BATTLE_SPEEDS else 0
    return BATTLE_SPEEDS[(i + 1) % len(BATTLE_SPEEDS)]

def drawSpeedControl(window, speed, mousePos=None, margin=24, top=None):
    """ONE arrow whose shape shows the current speed: ">" 1x, ">>" 1.5x, ">>>" 2x."""
    ink = 1
    head = _drawInkedText(window, "SPEED  [S]", CARD_STAT_LABEL_COLOR, 220, 16, 12, ink,
                          topleft=(margin, margin if top is None else top))
    i = BATTLE_SPEEDS.index(speed) if speed in BATTLE_SPEEDS else 0
    label = BATTLE_SPEED_LABELS[i]
    size = renderFittedText(label, CARD_TEXT_COLOR, 220, 30, 30).get_size()
    textRect = pygame.Rect(margin, head.bottom + 4, size[0], size[1])
    clickRect = textRect.inflate(24, 12)
    hovered = mousePos is not None and clickRect.collidepoint(mousePos)
    color = CARD_TEXT_COLOR if hovered else CARD_HOVER_COLOR
    _drawInkedText(window, label, color, 220, 30, 30, ink + 1, topleft=textRect.topleft)
    _drawFadeRule(window, color, textRect.left - 2, textRect.right + 2, textRect.bottom + 2, 2, ink)
    return [clickRect]

def drawEndTurnPrompt(window, mousePos=None, margin=24, bottomGap=44):
    windowWidth, windowHeight = window.get_size()
    rect = pygame.Rect(windowWidth - margin - 170, windowHeight - bottomGap - 84, 170, 84)
    cx = rect.centerx
    pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.006)

    glow = _iconGlow(70).copy()
    glow.set_alpha(int(110 + 120 * pulse))
    window.blit(glow, glow.get_rect(center=(cx, rect.top + 22)))

    title = _drawInkedText(window, END_TURN_TITLE, CARD_HOVER_COLOR, 160, 48, 30, 2, midtop=(cx, rect.top))
    ruleY = title.bottom + 6
    _drawFadeRule(window, CARD_HOVER_COLOR, rect.left, rect.right, ruleY, 2, 1)

    # "PRESS [ENTER]" -- the label, then a little keycap that bobs
    keyText = renderFittedText(END_TURN_KEY, CARD_TEXT_COLOR, 200, 16, 16)
    pressText = renderFittedText("PRESS", CARD_STAT_LABEL_COLOR, 200, 14, 14)
    capW, capH = keyText.get_width() + 16, 24
    rowW = pressText.get_width() + 8 + capW
    rowX, rowY = cx - rowW // 2, ruleY + 10
    _drawInkedText(window, "PRESS", CARD_STAT_LABEL_COLOR, 200, 14, 14, 1,
                   midleft=(rowX, rowY + capH // 2))
    keyCapRect = pygame.Rect(rowX + pressText.get_width() + 8, rowY, capW, capH)
    pygame.draw.rect(window, CARD_INK, keyCapRect.move(0, 3), border_radius=5)          # key's lower edge
    body = keyCapRect.move(0, round(pulse))
    pygame.draw.rect(window, (44, 44, 56), body, border_radius=5)
    pygame.draw.rect(window, CARD_HOVER_COLOR, body, 2, border_radius=5)
    _drawInkedText(window, END_TURN_KEY, CARD_HOVER_COLOR, 200, 16, 16, 1, center=body.center)
    return rect

_fpsCache = {"value": None, "label": None}

def drawFps(window, clock, margin=10):
    """FPS counter in the bottom-right corner."""
    fps = round(clock.get_fps())
    if fps != _fpsCache["value"]:
        text = f"FPS: {fps}"
        shadow = FONT.render(text, True, (0, 0, 0))
        front = FONT.render(text, True, (255, 255, 255))
        label = pygame.Surface((front.get_width() + 1, front.get_height() + 1), pygame.SRCALPHA)
        label.blit(shadow, (1, 1))
        label.blit(front, (0, 0))
        _fpsCache["value"] = fps
        _fpsCache["label"] = label
    label = _fpsCache["label"]
    window.blit(label, label.get_rect(bottomright=(window.get_width() - margin, window.get_height() - margin)))

# Result screen timeline (ms): the last blow lands, a beat passes, then the screen dims and the title slams in.
RESULT_SHOW_DELAY = 500        # beat before the result screen starts (lets the final hit / defeat animation play)
RESULT_HINT_DELAY = 900        # how long after the screen starts before "click to continue" appears
RESULT_DIM_MS = 450
RESULT_TITLE_MS = 560
RESULT_FLASH_MS = 280
RESULT_DEFEAT_RED = (255, 90, 90)

_resultOverlayCache = {}

def _resultOverlay(size):
    """Full-screen ink veil: a flat dim plus a darker horizontal band through the middle, soft at its edges."""
    overlay = _resultOverlayCache.get(size)
    if overlay is None:
        overlayWidth, overlayHeight = size
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(overlayHeight):
            distanceFromCenter = abs(y - overlayHeight * 0.46) / (overlayHeight * 0.30)
            band = max(0.0, 1 - distanceFromCenter) ** 1.5
            pygame.draw.line(overlay, (*CARD_INK, int(120 + 95 * band)), (0, y), (overlayWidth, y))
        overlay = overlay.convert_alpha()
        _resultOverlayCache.clear()
        _resultOverlayCache[size] = overlay
    return overlay

_titleInkCache = {}

def _titleInkOffset(text):
    """(dx, dy, inkHeight): how far the visible letters of `text` sit from the centre of ROUND_TITLE_FONT's render box."""
    cachedOffset = _titleInkCache.get(text)
    if cachedOffset is None:
        surf = ROUND_TITLE_FONT.render(text, True, (255, 255, 255))
        inkBounds = surf.get_bounding_rect()
        cachedOffset = (inkBounds.centerx - surf.get_width() / 2, inkBounds.centery - surf.get_height() / 2, inkBounds.height)
        _titleInkCache[text] = cachedOffset
    return cachedOffset

def drawBattleResult(window, result, screenWidth, screenHeight, elapsed=None, subtitle=None, rounds=None):
    """VICTORY / DEFEAT screen. `elapsed` = ms since the battle ended (None = fully shown). Call every frame, last."""
    if result is None:
        return
    resultElapsed = RESULT_SHOW_DELAY + 99999 if elapsed is None else elapsed
    resultElapsed -= RESULT_SHOW_DELAY
    if resultElapsed <= 0:
        return

    victory = result == "victory"
    accent = ROUND_GOLD if victory else RESULT_DEFEAT_RED
    cx = screenWidth // 2
    cy = int(screenHeight * 0.44)

    # 1. ink veil fades in
    veil = _resultOverlay((screenWidth, screenHeight))
    veil.set_alpha(int(255 * min(1.0, resultElapsed / RESULT_DIM_MS)))
    window.blit(veil, (0, 0))

    # 2. victory: a short gold flash as the title lands
    if victory and resultElapsed < RESULT_FLASH_MS:
        flash = pygame.Surface((screenWidth, screenHeight))
        flash.fill((255, 225, 120))
        flash.set_alpha(int(95 * (1 - resultElapsed / RESULT_FLASH_MS) ** 2))
        window.blit(flash, (0, 0))

    # 3. the title: slams in big and settles (defeat sinks in from above instead of popping)
    titleProgress = max(0.0, min(1.0, (resultElapsed - 100) / RESULT_TITLE_MS))
    if titleProgress > 0:
        text = "VICTORY" if victory else "DEFEAT"
        title = _outlinedText(ROUND_TITLE_FONT, text, accent, outline=5, shadow=5)
        if victory:
            scale = 1.0 + 0.9 * (1 - _easeOutBack(titleProgress))
            drop = 0
        else:
            scale = 1.0 + 0.25 * (1 - _easeOutCubic(titleProgress))
            drop = int(-60 * (1 - _easeOutCubic(titleProgress)))
        if titleProgress >= 1:
            scale = 1.0 + 0.012 * math.sin(pygame.time.get_ticks() * 0.003)     # slow breathing so it isn't frozen
        title = _scaled(title, scale).copy()
        title.set_alpha(int(255 * min(1.0, titleProgress * 2.5)))
        # Center the visible LETTERS (not the font's line box, which has empty space above/below the caps).
        inkDx, inkDy, inkH = _titleInkOffset(text)
        window.blit(title, title.get_rect(center=(cx - round(inkDx * scale), cy + drop - round(inkDy * scale))))

        # 4. gold (or red) fading rules above and below, growing out from the middle
        grow = _easeOutCubic(max(0.0, min(1.0, (resultElapsed - 300) / 500)))
        half = int(340 * grow)
        if half >= 2:
            titleGap = 14                                   # space between the VISIBLE title (letters + outline + shadow) and each rule
            outline, shadow = 5, 5                     # same values the title is drawn with above
            for y in (cy - inkH // 2 - outline - titleGap - 2, cy + inkH // 2 + outline + shadow + titleGap):
                _drawFadeRule(window, accent, cx - half, cx + half, y, 2, 1)

    # 5. stage name + rounds, fading up beneath the rule
    subtitleProgress = max(0.0, min(1.0, (resultElapsed - 500) / 300))
    if subtitleProgress > 0:
        lines = []
        if subtitle:
            lines.append((str(subtitle).upper(), CARD_TEXT_COLOR, 34))
        if rounds is not None:
            word = "ROUND" if rounds == 1 else "ROUNDS"
            lines.append((f"CLEARED IN {rounds} {word}" if victory else f"FELL IN ROUND {rounds}",
                          CARD_STAT_LABEL_COLOR, 24))
        y = cy + _titleInkOffset("VICTORY" if victory else "DEFEAT")[2] // 2 + 10 + 14 + 22 + int(10 * (1 - subtitleProgress))
        for text, color, size in lines:
            surf = _outlinedText(_fontOfSize(size), text, color, outline=2, shadow=2).copy()
            surf.set_alpha(int(255 * subtitleProgress))
            window.blit(surf, surf.get_rect(midtop=(cx, y)))
            y += surf.get_height() + 2

    # 6. "click to continue" once input is accepted: pulses between white and gold
    if resultElapsed >= RESULT_HINT_DELAY:
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.006)
        color = tuple(int(255 + (channel - 255) * pulse) for channel in CARD_HOVER_COLOR)
        hint = "CLICK TO CONTINUE" if victory else "CLICK TO TRY AGAIN"
        _drawInkedText(window, hint, color, 400, 26, 26, 2, center=(cx, int(screenHeight * 0.80)))

def fadeToInk(window, clock=None, duration=450, color=None):
    """Fades whatever is on the window to the ink colour (the exit half of the result screen). Blocks until done."""
    color = color or CARD_INK
    snapshot = window.copy()
    veil = pygame.Surface(window.get_size())
    veil.fill(color)
    if clock is None:
        clock = pygame.time.Clock()
    elapsed = 0
    while elapsed < duration:
        elapsed += min(clock.tick(60), 50)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        fadeProgress = min(elapsed / duration, 1.0)
        fadeProgress = fadeProgress * fadeProgress * (3 - 2 * fadeProgress)
        window.blit(snapshot, (0, 0))
        veil.set_alpha(int(255 * fadeProgress))
        window.blit(veil, (0, 0))
        pygame.display.update()
    window.fill(color)
    pygame.display.update()

# ---------- Battle Log ----------

BATTLE_LOG_X = 20
BATTLE_LOG_WIDTH = 360
BATTLE_LOG_MARGIN_BOTTOM = 20
BATTLE_LOG_MARGIN_TOP = 60
BATTLE_LOG_PADDING = 10
BATTLE_LOG_LINE_GAP = 2
BATTLE_LOG_COLLAPSED_LINES = 4
BATTLE_LOG_HEADER_TEXT = "Battle Log"
BATTLE_LOG_MAX_ENTRIES = 300
BATTLE_LOG_BG_TOP_ALPHA = 20
BATTLE_LOG_BG_BOTTOM_ALPHA = 210
BATTLE_LOG_TEXT_COLOR = (230, 230, 230)
BATTLE_LOG_ROUND_COLOR = (255, 215, 0)
BATTLE_LOG_DEATH_COLOR = (220, 70, 70)
BATTLE_LOG_TOGGLE_SIZE = 18
BATTLE_LOG_SCROLL_LINES = 3       # lines moved per wheel notch
BATTLE_LOG_COMPACT_DELAY = 900
BATTLE_LOG_SLIDE_LERP_RATE = 10.0

def createBattleLog():
    """One of these lives for the whole battle -- owns every logged line plus the panel's own open/closed and scroll state."""
    return {
        "entries": [],
        "expanded": False,
        "scroll": 0,
        "toggleRect": pygame.Rect(0, 0, 0, 0),
        "_wrapCache": [],
        "_wrapUpTo": 0,
        "displayWidth": None,
        "_idleMs": BATTLE_LOG_COMPACT_DELAY,
        "displayHeight": 0.0,
    }

def addBattleLogEntry(log, text, color=BATTLE_LOG_TEXT_COLOR):
    """Appends one raw line to the log and snaps the view back to the bottom."""
    log["entries"].append({"text": text, "color": color})
    if len(log["entries"]) > BATTLE_LOG_MAX_ENTRIES:
        del log["entries"][: len(log["entries"]) - BATTLE_LOG_MAX_ENTRIES]
        # Trimming the front shifts every remaining entry's index.
        log["_wrapCache"] = []
        log["_wrapUpTo"] = 0
    log["scroll"] = 0

def logRoundMarker(log, roundNumber):
    addBattleLogEntry(log, f"--- Round {roundNumber} ---", color=BATTLE_LOG_ROUND_COLOR)

def logActionLine(log, action, kind, amount=None):
    """Builds and appends the one-line summary for an action that just resolved."""
    attacker = action["sprite"]["name"]
    target = action["target"]["name"] if action.get("target") is not None else attacker
    skillName = action["skillDef"].name

    if kind == "damage":
        text = f"{attacker}'s {skillName} hit {target} for {amount:.0f} dmg!"
    elif kind == "heal":
        text = f"{attacker}'s {skillName} healed {target} for {amount:.0f} HP!"
    elif kind == "guard":
        text = f"{attacker} braced with {skillName}!"
    else:
        if target != attacker:
            text = f"{attacker}'s {skillName} affected {target}!"
        else:
            text = f"{attacker} used {skillName}!"
    addBattleLogEntry(log, text)

def _battleLogWrapEntries(entries, font, maxWidth):
    """Word-wraps just THESE entries to `maxWidth`, carrying each entry's own color onto every line it produces."""
    lines = []
    for entry in entries:
        words = entry["text"].split(" ")
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if current and font.size(trial)[0] > maxWidth:
                lines.append((current, entry["color"]))
                current = word
            else:
                current = trial
        lines.append((current, entry["color"]))
    return lines

def _battleLogSyncWrapCache(log, font, maxWidth):
    """Returns the log's fully word-wrapped line list, doing as little work as possible to get there."""
    if log.get("_wrapMaxWidth") != maxWidth:
        log["_wrapCache"] = []
        log["_wrapUpTo"] = 0
        log["_wrapMaxWidth"] = maxWidth

    entries = log["entries"]
    newEntries = entries[log["_wrapUpTo"]:]
    if newEntries:
        log["_wrapCache"].extend(_battleLogWrapEntries(newEntries, font, maxWidth))
        log["_wrapUpTo"] = len(entries)
    return log["_wrapCache"]

_battleLogCompactSize = None

def battleLogCompactSize():
    """ of the small "Battle Log ^" tab shown while skills are being picked -- just the header text plus the chevron, no text lines."""
    global _battleLogCompactSize
    if _battleLogCompactSize is None:
        headerWidth = FONT.size(BATTLE_LOG_HEADER_TEXT)[0]
        width = BATTLE_LOG_PADDING + headerWidth + BATTLE_LOG_PADDING + BATTLE_LOG_TOGGLE_SIZE + BATTLE_LOG_PADDING
        height = max(FONT.get_height(), BATTLE_LOG_TOGGLE_SIZE) + BATTLE_LOG_PADDING
        _battleLogCompactSize = (width, height)
    return _battleLogCompactSize

def battleLogPanelHeight(log, screenHeight, compact=False):
    """How tall the panel is THIS frame."""
    lineHeight = FONT.get_height() + BATTLE_LOG_LINE_GAP
    headerHeight = FONT.get_height() + BATTLE_LOG_PADDING
    if compact:
        return battleLogCompactSize()[1]
    if log["expanded"]:
        return screenHeight - BATTLE_LOG_MARGIN_TOP - BATTLE_LOG_MARGIN_BOTTOM
    return headerHeight + BATTLE_LOG_COLLAPSED_LINES * lineHeight + BATTLE_LOG_PADDING * 2

# The gradient itself is baked ONCE at a fixed reference height.
_battleLogGradientUnit = None
_battleLogGradientCache = {}
BATTLE_LOG_GRADIENT_UNIT_HEIGHT = 256
BATTLE_LOG_HEIGHT_STEP = 4

def _battleLogGradientUnitSurface(panelWidth):
    """Built ONCE at the full panel width."""
    global _battleLogGradientUnit
    if _battleLogGradientUnit is None:
        unitHeight = BATTLE_LOG_GRADIENT_UNIT_HEIGHT
        surf = pygame.Surface((BATTLE_LOG_WIDTH, unitHeight), pygame.SRCALPHA)
        for rowIndex in range(unitHeight):
            rowProgress = rowIndex / (unitHeight - 1)
            alpha = int(BATTLE_LOG_BG_TOP_ALPHA + (BATTLE_LOG_BG_BOTTOM_ALPHA - BATTLE_LOG_BG_TOP_ALPHA) * rowProgress)
            pygame.draw.line(surf, (0, 0, 0, alpha), (0, rowIndex), (BATTLE_LOG_WIDTH, rowIndex))
        _battleLogGradientUnit = surf
    width = max(1, min(panelWidth, BATTLE_LOG_WIDTH))
    return _battleLogGradientUnit.subsurface((0, 0, width, BATTLE_LOG_GRADIENT_UNIT_HEIGHT))

def _battleLogGradientSurface(panelWidth, panelHeight):
    """`panelHeight` must already be quantized to BATTLE_LOG_HEIGHT_STEP."""
    panelHeight = max(1, panelHeight)
    key = (panelWidth, panelHeight)
    surf = _battleLogGradientCache.get(key)
    if surf is None:
        unit = _battleLogGradientUnitSurface(panelWidth)
        surf = pygame.transform.scale(unit, (panelWidth, panelHeight))
        if len(_battleLogGradientCache) >= 192:
            _battleLogGradientCache.clear()
        _battleLogGradientCache[key] = surf
    return surf

def drawBattleLog(window, log, screenWidth, screenHeight, dt, compact=False):
    """Docked bottom-left panel over a black gradient."""
    lineHeight = FONT.get_height() + BATTLE_LOG_LINE_GAP

    # `compact` (passed by battle_ui while skills are being picked, i.e.
    wantsCompact = compact and not log["expanded"]
    if wantsCompact:
        log["_idleMs"] = log.get("_idleMs", 0) + min(dt, 100)
    else:
        log["_idleMs"] = 0
    isCompact = wantsCompact and log["_idleMs"] >= BATTLE_LOG_COMPACT_DELAY

    targetHeight = battleLogPanelHeight(log, screenHeight, compact=isCompact)
    log["displayHeight"] = lerpValue(log.get("displayHeight", 0.0), targetHeight, dt, rate=BATTLE_LOG_SLIDE_LERP_RATE)
    step = BATTLE_LOG_HEIGHT_STEP
    panelHeight = max(step, round(log["displayHeight"] / step) * step)

    targetWidth = battleLogCompactSize()[0] if isCompact else BATTLE_LOG_WIDTH
    if log.get("displayWidth") is None:
        log["displayWidth"] = targetWidth
    log["displayWidth"] = lerpValue(log["displayWidth"], targetWidth, dt, rate=BATTLE_LOG_SLIDE_LERP_RATE)
    panelWidth = max(step, round(log["displayWidth"] / step) * step)
    x = BATTLE_LOG_X
    bottom = screenHeight - BATTLE_LOG_MARGIN_BOTTOM
    top = bottom - panelHeight

    panelRect = pygame.Rect(x, top, panelWidth, panelHeight)
    prevClip = window.get_clip()
    window.set_clip(panelRect)

    window.blit(_battleLogGradientSurface(panelWidth, panelHeight), (x, top))

    headerSurf = barText(BATTLE_LOG_HEADER_TEXT, (255, 255, 255))
    window.blit(headerSurf, (x + BATTLE_LOG_PADDING, top + BATTLE_LOG_PADDING // 2))

    size = BATTLE_LOG_TOGGLE_SIZE
    toggleRect = pygame.Rect(x + panelWidth - size - BATTLE_LOG_PADDING,
                              top + BATTLE_LOG_PADDING // 2, size, size)
    log["toggleRect"] = toggleRect
    cx, cy = toggleRect.center
    halfW, halfH = size * 0.32, size * 0.2
    if log["expanded"]:
        points = [(cx - halfW, cy - halfH), (cx, cy + halfH), (cx + halfW, cy - halfH)]
    else:
        points = [(cx - halfW, cy + halfH), (cx, cy - halfH), (cx + halfW, cy + halfH)]
    pygame.draw.lines(window, (255, 255, 255), False, points, 3)

    # Text area sits below the header.
    if isCompact and panelHeight <= battleLogCompactSize()[1] + step:
        window.set_clip(prevClip)
        return

    textTop = top + headerSurf.get_height() + BATTLE_LOG_PADDING
    textBottom = bottom - BATTLE_LOG_PADDING // 2
    visibleHeight = max(0, textBottom - textTop)
    visibleLines = max(1, visibleHeight // lineHeight)

    wrapped = _battleLogSyncWrapCache(log, FONT, BATTLE_LOG_WIDTH - BATTLE_LOG_PADDING * 2 - size)
    maxScroll = max(0, len(wrapped) - visibleLines)
    log["scroll"] = max(0, min(log["scroll"], maxScroll))

    endIdx = len(wrapped) - log["scroll"]
    startIdx = max(0, endIdx - visibleLines)
    shown = wrapped[startIdx:endIdx]

    window.set_clip(panelRect.clip(pygame.Rect(x, textTop, panelWidth, visibleHeight)))
    cursorY = textTop
    for text, color in shown:
        window.blit(barText(text, color), (x + BATTLE_LOG_PADDING, cursorY))
        cursorY += lineHeight
    window.set_clip(prevClip)

def handleBattleLogEvent(log, event, roundLocked):
    """Battle_ui.py forwards every pygame event here before its own click handling."""
    if event.type == pygame.MOUSEWHEEL:
        log["scroll"] = max(0, log["scroll"] - event.y * BATTLE_LOG_SCROLL_LINES)
        return True
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if log["toggleRect"].collidepoint(event.pos):
            if not roundLocked:
                log["expanded"] = not log["expanded"]
                log["scroll"] = 0
            return True
    return False

# ---------- Targeting ----------

def getEnemyTarget(sprites, selectedSprite, pos):
    candidates = [
        sprite for sprite in sprites
        if sprite["side"] != selectedSprite["side"] and not sprite["dead"] and sprite["stats"].rect.collidepoint(pos)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda sprite: (sprite["stats"].rect.centerx - pos[0]) ** 2 + (sprite["stats"].rect.centery - pos[1]) ** 2
    )

def canTargetSelf(skillDef):
    """True if `skillDef` may be aimed at its own caster."""
    if skillDef is None or not isFriendlyTargetSkill(skillDef):
        return True
    return getattr(skillDef, "targetCount", 1) >= 3

def hasValidAllyTarget(sprites, caster, skillDef):
    """True if `caster` has at least one legal target for a friendly skill -- i.e."""
    return any(
        sprite["side"] == caster["side"] and not sprite["dead"]
        and (sprite is not caster or canTargetSelf(skillDef))
        for sprite in sprites
    )

def getAllyTarget(sprites, selectedSprite, pos, skillDef=None):
    """Same idea as getEnemyTarget, but for a heal or buff -- picks from `selectedSprite`'s OWN side instead of the opposing one."""
    allowSelf = canTargetSelf(skillDef)
    candidates = [
        sprite for sprite in sprites
        if sprite["side"] == selectedSprite["side"] and not sprite["dead"]
        and (allowSelf or sprite is not selectedSprite)
        and sprite["stats"].rect.collidepoint(pos)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda sprite: (sprite["stats"].rect.centerx - pos[0]) ** 2 + (sprite["stats"].rect.centery - pos[1]) ** 2
    )

def previewActionTargets(sprites, primary, skillDef):
    """Every sprite `skillDef` would actually hit/heal if `primary` were confirmed as its target right now."""
    if primary is None:
        return []
    targets = [primary]
    if skillDef is not None and getattr(skillDef, "targetCount", 1) >= 3:
        targets += [
            sprite for sprite in sprites
            if sprite is not primary and sprite["side"] == primary["side"] and not sprite["dead"]
        ]
    return targets

# ---------- Skill kind helpers ----------
def getSkillDef(charName, skillName):
    for skill in CHARACTER[charName]["skills"]:
        if skill.name == skillName:
            return skill
    return None

def isGuardSkill(skillDef):
    """True for a dodge/block skill -- identified by icon, the same convention SKILL_ANIMATIONS_CONFIG/DODGE_BLOCK_CONFIG already use."""
    return skillDef is not None and skillDef.icon in ("dodge", "block")

def isSelfSkill(skillDef):
    """Guard stances plus any skill flagged selfOnly: the caster is always the target."""
    return skillDef is not None and (isGuardSkill(skillDef) or getattr(skillDef, "selfOnly", False))

def isHealSkill(skillDef):
    """True for a heal skill -- identified by SkillDef.kind == "heal" (see classes.SkillDef), NOT by icon anymore."""
    return skillDef is not None and skillDef.kind == "heal"

def isBuffSkill(skillDef):
    """True for a buff skill."""
    return skillDef is not None and skillDef.kind == "buff"

def isDebuffSkill(skillDef):
    """True for a debuff skill."""
    return skillDef is not None and skillDef.kind == "debuff"

def isFriendlyTargetSkill(skillDef):
    """True for any skill that targets the CASTER'S OWN side."""
    return isHealSkill(skillDef) or isBuffSkill(skillDef)


# ---------- Action queue ----------

def queueAction(actionQueue, sprite, buttonIndex, target, sprites=None):
    """`sprites` is the full battle sprite list -- pass it so an AOE skill can later work out who else is on the target's side."""
    skillName = sprite["buttonSkills"][buttonIndex]
    skillDef = getSkillDef(sprite["name"], skillName)

    # Defensive backstop.
    if skillDef is not None and skillLockedBySanity(sprite, skillDef):
        return

    # A guard skill is a stance on yourself, not an attack.
    if skillDef is not None and isSelfSkill(skillDef):
        target = sprite

    # A single-target heal/buff can't be aimed at its own caster.
    if (skillDef is not None and not isSelfSkill(skillDef)
            and target is sprite and not canTargetSelf(skillDef)):
        return

    newAction = {
        "sprite": sprite,
        "skillName": skillName,
        "skillDef": skillDef,
        "target": target,
        "_allSprites": sprites,
    }

    # already queued this round?
    for i, existing in enumerate(actionQueue):
        if existing["sprite"] is sprite:
            actionQueue[i] = newAction
            break
    else:
        actionQueue.append(newAction)

    sprite["acted"] = True
    sprite["selected"] = False

# ---------- Enemy AI ----------
# Each enemy scores every (skill, target) it can legally use and picks the best.
AI_RANDOMNESS = 0.08        # +/- noise on every score so enemies aren't predictable (lower = plays the best move more often)
AI_KILL_BONUS = 60          # finishing a player off
AI_OVERKILL_FACTOR = 0.2    # a target already doomed by an earlier enemy this round
AI_EFFECT_BONUS = 12        # each status effect that isn't already active
AI_SANITY_COST_WEIGHT = 15  # per point of sanity a skill costs (low, so enemies actually use their ults)
AI_REPEAT_FACTOR = 0.93     # same skill as last round
AI_WEAKEST_BONUS = 8        # lean toward the most wounded player (was 16, which sent every enemy at the same target)
AI_SPREAD_FACTOR = 0.55     # x per enemy that already picked this player THIS round (spreads group attacks around)
AI_TARGET_JITTER = 0.25     # +/- random weight per target, so which player gets hit isn't a fixed order
AI_SAME_TARGET_FACTOR = 0.85  # x if this enemy hit the same player last round
AI_PICK_WINDOW = 0.80       # any option scoring within 80% of the best can be chosen (weighted by score)
AI_DESPERATION = 0.6        # at 0 HP an enemy's attack scores are up to +60%: hurt enemies get MORE aggressive
AI_GUARD_BASE = 3           # a guard stance's flat appeal
AI_GUARD_DANGER = 22        # extra guard appeal at 0 HP (was 55, which beat almost every attack)
AI_BOSS_GUARD_FACTOR = 0.35 # bosses ("ultChance") rarely turtle
AI_BOSS_ENRAGE_ULT = 0.35   # a boss's ult chance rises by up to this much as its HP drops

def _hasStatus(sprite, effectFn):
    return any(statusEffect.apply is effectFn for statusEffect in sprite.get("statusEffects", []))

def _hitValue(caster, skillDef, target, fraction=1.0):
    """Expected damage (or heal, for a heal skill) of one hit on `target`."""
    mult = caster["stats"].attackMult * sanityDamageMultiplier(caster.get("sanity", 0.5))
    if isHealSkill(skillDef):
        return skillDef.damage * fraction * sanityDamageMultiplier(caster.get("sanity", 0.5))
    return skillDef.damage * fraction * max(0.0, 1 - target["stats"].defense) * mult

def _missingEffects(skillDef, caster, target):
    """How many of the skill's status effects wouldn't change anything new on their recipients."""
    count = sum(1 for targetEffect in skillDef.effects if not _hasStatus(target, targetEffect.effect))
    count += sum(1 for selfEffect in skillDef.selfEffects if not _hasStatus(caster, selfEffect.effect))
    return count

def _aoeTargets(skillDef, primary, group):
    """(sprite, fraction) pairs hit by a skill aimed at `primary` among `group`."""
    pairs = [(primary, 1.0)]
    if getattr(skillDef, "targetCount", 1) >= 3:
        pairs += [(sprite, AOE_SPLASH_DAMAGE_FRACTION) for sprite in group if sprite is not primary]
    return pairs

def _chooseEnemyAction(enemy, skills, players, allies, projectedHp, targeted=None):
    """Best (score, skillDef, target) for `enemy`, or None if it can't act."""
    stats = enemy["stats"]
    targeted = targeted if targeted is not None else {}
    candidates = []

    def consider(score, skillDef, target):
        score *= random.uniform(1 - AI_RANDOMNESS, 1 + AI_RANDOMNESS)
        if skillDef.name == enemy.get("_aiLast"):
            score *= AI_REPEAT_FACTOR
        candidates.append((score, skillDef, target))

    danger = 1 - stats.hp / max(1, stats.maxHp)     # 0 = healthy, 1 = nearly dead
    isBoss = enemy.get("ultChance") is not None

    lockedOthers = any(skillLockedBySanity(enemy, candidateSkill)
                       for candidateSkill in CHARACTER[enemy["name"]]["skills"] if not isGuardSkill(candidateSkill))

    for skillDef in skills:
        if skillLockedBySanity(enemy, skillDef):
            continue
        # A boss with "ultChance" (stages.py) only considers its ult that often, even when it's available.
        # The chance climbs as the boss gets hurt, so a wounded boss gets more dangerous, not less.
        if (getattr(skillDef, "sanityCost", 0) > 0 and enemy.get("ultChance") is not None
                and random.random() > min(1.0, enemy["ultChance"] + danger * AI_BOSS_ENRAGE_ULT)):
            continue

        if isGuardSkill(skillDef):
            if enemy.get("guard"):
                continue    # a stance is already up
            recover = skillDef.sanityRecover * (80 if lockedOthers else 30)
            guardScore = AI_GUARD_BASE + danger * AI_GUARD_DANGER + recover
            if isBoss and not lockedOthers:
                guardScore *= AI_BOSS_GUARD_FACTOR
            consider(guardScore, skillDef, enemy)

        elif isHealSkill(skillDef):
            for target in allies:
                if target is enemy and not canTargetSelf(skillDef):
                    continue
                missing = target["stats"].maxHp - projectedHp[id(target)]
                if missing <= 0 or projectedHp[id(target)] / target["stats"].maxHp > 0.75:
                    continue
                value = 0.0
                for ally, fraction in _aoeTargets(skillDef, target, allies):
                    value += min(_hitValue(enemy, skillDef, ally, fraction),
                                 ally["stats"].maxHp - projectedHp[id(ally)])
                if projectedHp[id(target)] / target["stats"].maxHp < 0.3:
                    value += 15    # saving a nearly dead ally
                consider(value * 1.2 - AI_SANITY_COST_WEIGHT * skillDef.sanityCost,
                         skillDef, target)

        elif isBuffSkill(skillDef):
            for target in allies:
                if target is enemy and not canTargetSelf(skillDef):
                    continue
                missing = _missingEffects(skillDef, enemy, target)
                if missing:
                    consider(AI_EFFECT_BONUS * 1.5 * missing
                             - AI_SANITY_COST_WEIGHT * skillDef.sanityCost, skillDef, target)

        else:   # damage skill or debuff
            for target in players:
                hp = projectedHp[id(target)]
                total = 0.0
                for victim, fraction in _aoeTargets(skillDef, target, players):
                    total += _hitValue(enemy, skillDef, victim, fraction)
                expectedDamage = _hitValue(enemy, skillDef, target)
                score = total + AI_EFFECT_BONUS * _missingEffects(skillDef, enemy, target)
                score += (1 - hp / max(1, target["stats"].maxHp)) * AI_WEAKEST_BONUS     # prefer the weakest
                if hp <= 0:
                    score *= AI_OVERKILL_FACTOR
                elif expectedDamage >= hp:
                    score += AI_KILL_BONUS
                else:
                    score -= AI_SANITY_COST_WEIGHT * skillDef.sanityCost
                    # Not a finishing blow: spread the group out instead of all piling onto one player.
                    score *= AI_SPREAD_FACTOR ** targeted.get(id(target), 0)
                    score *= random.uniform(1 - AI_TARGET_JITTER, 1 + AI_TARGET_JITTER)
                    if enemy.get("_aiLastTarget") == id(target):
                        score *= AI_SAME_TARGET_FACTOR
                score *= 1 + danger * AI_DESPERATION      # a wounded enemy fights harder
                consider(score, skillDef, target)

    if not candidates:
        return None
    # Not always the single top score: anything close to it can be picked (higher score = likelier).
    top = max(candidate[0] for candidate in candidates)
    pool = [candidate for candidate in candidates if candidate[0] >= top * AI_PICK_WINDOW] if top > 0 else [max(candidates, key=lambda candidate: candidate[0])]
    return random.choices(pool, weights=[max(0.01, candidate[0]) for candidate in pool])[0]

def enemyAI(sprites, actionQueue):
    """Queues one action for every enemy that hasn't acted yet."""
    enemies = [sprite for sprite in sprites if sprite["side"] == "right" and not sprite["acted"] and not sprite["dead"]]
    players = [sprite for sprite in sprites if sprite["side"] == "left" and not sprite["dead"]]
    allies = [sprite for sprite in sprites if sprite["side"] == "right" and not sprite["dead"]]

    if not players:
        return

    # HP as it will stand once the enemies already decided this round have acted.
    projectedHp = {id(sprite): sprite["stats"].hp for sprite in sprites}
    targeted = {}      # id(player) -> how many enemies already chose it this round

    for enemy in enemies:
        skills = [sprite for sprite in CHARACTER[enemy["name"]]["skills"]
                  if not skillLockedBySanity(enemy, sprite)
                  and (not isFriendlyTargetSkill(sprite) or hasValidAllyTarget(sprites, enemy, sprite))]
        choice = _chooseEnemyAction(enemy, skills, players, allies, projectedHp, targeted) if skills else None
        enemy["acted"] = True
        if choice is None:
            continue

        _, skillDef, target = choice
        if isGuardSkill(skillDef):
            pass
        elif isHealSkill(skillDef):
            for ally, fraction in _aoeTargets(skillDef, target, allies):
                projectedHp[id(ally)] = min(ally["stats"].maxHp,
                                            projectedHp[id(ally)] + _hitValue(enemy, skillDef, ally, fraction))
        elif not isBuffSkill(skillDef):
            for victim, fraction in _aoeTargets(skillDef, target, players):
                projectedHp[id(victim)] -= _hitValue(enemy, skillDef, victim, fraction)
            targeted[id(target)] = targeted.get(id(target), 0) + 1
            enemy["_aiLastTarget"] = id(target)

        enemy["_aiLast"] = skillDef.name
        actionQueue.append({
            "sprite": enemy,
            "skillName": skillDef.name,
            "skillDef": skillDef,
            "target": target,
            "_allSprites": sprites,
        })


# ---------- Action-targeting arrows & turn highlight ----------

ARROW_PLAYER_COLOR = (90, 200, 255)   # arrows from a left-side (player) actor
ARROW_ENEMY_COLOR = (255, 90, 90)     # arrows from a right-side (enemy) actor
ARROW_WIDTH = 3
ARROW_HEAD_LEN = 14
ARROW_HEAD_ANGLE = 25          # degrees, half-angle of the arrowhead
ARROW_GAP = 12
ARROW_HEIGHT_OFFSET = 14
ARROW_CURVE = 0.18
ARROW_CLASH_CURVE = 0.32
ARROW_SEGMENTS = 24            # points used to approximate the curve

def _arrowColorForSide(side):
    return ARROW_PLAYER_COLOR if side == "left" else ARROW_ENEMY_COLOR

def _shortenLine(start, endPoint, gapLength):
    """Pull both ends of a line inward by `gap` px so the arrow doesn't start/end right on top of the sprites it connects."""
    startX, startY = start
    endX, endY = endPoint
    lineX, lineY = endX - startX, endY - startY
    dist = math.hypot(lineX, lineY)
    if dist <= gapLength * 2:
        return start, endPoint
    unitX, unitY = lineX / dist, lineY / dist
    return (startX + unitX * gapLength, startY + unitY * gapLength), (endX - unitX * gapLength, endY - unitY * gapLength)

def _drawArrowhead(window, tip, direction, color):
    angle = math.atan2(direction[1], direction[0])
    for sign in (1, -1):
        headAngle = angle + math.pi - math.radians(ARROW_HEAD_ANGLE) * sign
        headEnd = (tip[0] + math.cos(headAngle) * ARROW_HEAD_LEN, tip[1] + math.sin(headAngle) * ARROW_HEAD_LEN)
        pygame.draw.line(window, color, tip, headEnd, ARROW_WIDTH)

def _arcControlPoint(start, endPoint, bend):
    """Control point for a quadratic bezier that always bows the line upward by `bend`, as a fraction of the line's length."""
    midX, midY = (start[0] + endPoint[0]) / 2, (start[1] + endPoint[1]) / 2
    length = math.hypot(endPoint[0] - start[0], endPoint[1] - start[1]) or 1
    return (midX, midY - length * bend)

ARROW_ICON_SIZE = 30            # attacker's face on the arrow's tip
ARROW_V_HALF_W = 11             # the V under the face: half width ...
ARROW_V_HEIGHT = 9              # ... and height
ARROW_V_THICK = 4
ARROW_BADGE_SPACING = 34
ARROW_INK = (10, 8, 16)

_arrowIconCache = {}

def _arrowIcon(sprite):
    """The attacker's head icon (same one the turn-order tabs use), scaled small for the arrow tip."""
    name = sprite["name"]
    surf = _arrowIconCache.get(name)
    if surf is None:
        base = _queuePortrait(sprite)
        bounds = base.get_bounding_rect()
        if bounds.width and bounds.height:
            base = base.subsurface(bounds)
        ratio = min(ARROW_ICON_SIZE / base.get_width(), ARROW_ICON_SIZE / base.get_height())
        surf = pygame.transform.smoothscale(
            base, (max(1, round(base.get_width() * ratio)), max(1, round(base.get_height() * ratio)))).convert_alpha()
        _arrowIconCache[name] = surf
    return surf

def _bezierPoints(start, control, endPoint):
    curvePoints = []
    for i in range(ARROW_SEGMENTS + 1):
        curveProgress = i / ARROW_SEGMENTS
        curvePoints.append(((1 - curveProgress) ** 2 * start[0] + 2 * (1 - curveProgress) * curveProgress * control[0] + curveProgress ** 2 * endPoint[0],
                    (1 - curveProgress) ** 2 * start[1] + 2 * (1 - curveProgress) * curveProgress * control[1] + curveProgress ** 2 * endPoint[1]))
    return curvePoints

def _inkedPolyline(window, points, color, width):
    """Curve with the same dark outline + drop shadow the cards use."""
    inkWidth = width + 3
    for dx, dy, lineColor, lineWidth in ((1, 2, ARROW_INK, inkWidth), (0, 0, ARROW_INK, inkWidth), (0, 0, color, width)):
        shifted = [(x + dx, y + dy) for x, y in points]
        pygame.draw.lines(window, lineColor, False, shifted, lineWidth)
        for x, y in shifted:
            pygame.draw.circle(window, lineColor, (round(x), round(y)), max(1, lineWidth // 2))

def _drawArrowBadge(window, sprite, tip, color):
    """A downward V pointing at `tip`, with the attacking unit's face sitting in its notch."""
    chevronPoints = ((tip[0] - ARROW_V_HALF_W, tip[1] - ARROW_V_HEIGHT), tip, (tip[0] + ARROW_V_HALF_W, tip[1] - ARROW_V_HEIGHT))
    for dx, dy, lineColor, lineWidth in ((1, 2, ARROW_INK, ARROW_V_THICK + 3), (0, 0, ARROW_INK, ARROW_V_THICK + 3),
                           (0, 0, color, ARROW_V_THICK)):
        shiftedPoints = [(x + dx, y + dy) for x, y in chevronPoints]
        pygame.draw.lines(window, lineColor, False, shiftedPoints, lineWidth)
        for x, y in shiftedPoints:
            pygame.draw.circle(window, lineColor, (round(x), round(y)), max(1, lineWidth // 2))

    icon = _arrowIcon(sprite)
    iconRect = icon.get_rect(midbottom=(tip[0], tip[1] - ARROW_V_HEIGHT - 4))
    _blitInked(window, icon, iconRect.topleft, 1)
    return iconRect.center

ARROW_GLOW_PASSES = ((20, 26), (14, 46), (9, 78))

def _drawArrowGlow(window, points, badgeCentre=None):
    """Warm gold halo along the arc (and behind the face on the V), the same glow a hovered skill card gets."""
    pad = 14
    allX = [point[0] for point in points] + ([badgeCentre[0]] if badgeCentre else [])
    allY = [point[1] for point in points] + ([badgeCentre[1]] if badgeCentre else [])
    left, top = int(min(allX)) - pad - 30, int(min(allY)) - pad - 30
    width, height = int(max(allX)) - left + pad + 30, int(max(allY)) - top + pad + 30
    layer = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    local = [(x - left, y - top) for x, y in points]
    for glowWidth, alpha in ARROW_GLOW_PASSES:
        glowColor = (*CARD_GLOW_COLOR, alpha)
        pygame.draw.lines(layer, glowColor, False, local, glowWidth)
        for x, y in local:
            pygame.draw.circle(layer, glowColor, (round(x), round(y)), glowWidth // 2)
    if badgeCentre is not None:
        glow = _iconGlow(26)
        layer.blit(glow, glow.get_rect(center=(badgeCentre[0] - left, badgeCentre[1] - top)))
    window.blit(layer, (left, top))

def drawArchedArrow(window, start, endPoint, color=ARROW_PLAYER_COLOR, bend=ARROW_CURVE, attacker=None, lit=False):
    """An ink-outlined arc from start to end, arched toward the top of the screen, finishing in a V that carries the attacker's face."""
    if attacker is not None:
        badgeCentre = (endPoint[0], endPoint[1] - ARROW_V_HEIGHT - 4 - ARROW_ICON_SIZE // 2)
        arcEnd = badgeCentre
    else:
        badgeCentre = None
        arcEnd = endPoint
    start, arcEnd = _shortenLine(start, arcEnd, 4)
    control = _arcControlPoint(start, arcEnd, bend)
    points = _bezierPoints(start, control, arcEnd)
    if lit:
        _drawArrowGlow(window, points, badgeCentre)
    _inkedPolyline(window, points, color, ARROW_WIDTH + (1 if lit else 0))
    pygame.draw.circle(window, ARROW_INK, (round(start[0]), round(start[1])), 5)   # small ink dot where it leaves the actor
    pygame.draw.circle(window, CARD_HOVER_COLOR if lit else color, (round(start[0]), round(start[1])), 3)
    if attacker is not None:
        _drawArrowBadge(window, attacker, endPoint, color)

def _headPoint(sprite):
    """A point above the sprite's head."""
    x, top = sprite["stats"].rect.midtop
    return (x, top - ARROW_HEIGHT_OFFSET)

ARROW_DIM_TINT = (85, 85, 95, 255)
ARROW_DIM_ALPHA = 200                # and how opaque they stay (255 = fully)
_arrowDimSurfaces = {}

def _arrowDimLayer(size):
    """Scratch SRCALPHA layer the dimmed arrows are drawn onto, reused each frame."""
    layer = _arrowDimSurfaces.get(size)
    if layer is None:
        _arrowDimSurfaces.clear()
        layer = _arrowDimSurfaces[size] = pygame.Surface(size, pygame.SRCALPHA)
    return layer

def drawActionArrows(window, actionQueue, activeAction=None, dimAll=False):
    """One ink-outlined arc per queued action."""
    arrows = []
    for action in actionQueue:
        sprite, target = action["sprite"], action["target"]
        if target is sprite:
            continue
        arrows.append((sprite, target))

    perTarget = {}
    for sprite, target in arrows:
        perTarget.setdefault(id(target), []).append(sprite)

    if activeAction is None:
        litActions = []
    elif isinstance(activeAction, (list, tuple)):
        litActions = list(activeAction)
    else:
        litActions = [activeAction]
    litSprites = {id(litAction["sprite"]) for litAction in litActions}

    dimming = bool(litSprites) or dimAll
    dimLayer = None
    if dimming:
        dimLayer = _arrowDimLayer(window.get_size())

    def arrowGeometry(action):
        sprite, target = action["sprite"], action["target"]
        mutual = any(otherSprite is target and otherTarget is sprite for otherSprite, otherTarget in arrows)
        group = perTarget[id(target)]
        offset = (group.index(sprite) - (len(group) - 1) / 2) * ARROW_BADGE_SPACING
        start = _headPoint(sprite)
        x, y = _headPoint(target)
        arrowEnd = (x + offset, y)
        bend = ARROW_CLASH_CURVE if (mutual and sprite["side"] != "left") else ARROW_CURVE
        return sprite, target, start, arrowEnd, bend

    def drawOne(action, surface):
        sprite, target, start, end, bend = arrowGeometry(action)
        drawArchedArrow(surface, start, end, _arrowColorForSide(sprite["side"]), bend=bend,
                        attacker=sprite, lit=id(sprite) in litSprites)

    attacks = [litAction for litAction in actionQueue if litAction["target"] is not litAction["sprite"]]
    waiting = [litAction for litAction in attacks if id(litAction["sprite"]) not in litSprites] if dimming else []
    bright = [litAction for litAction in attacks if litAction not in waiting]

    # waiting arrows first, darkened and faded back a little (colour AND face)...
    if waiting:
        # Only the region the waiting arrows can touch is cleared, drawn, tinted and blitted.
        left = top = 10 ** 9
        right = bottom = -10 ** 9
        pad = 90
        for action in waiting:
            _, _, start, end, bend = arrowGeometry(action)
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            peak = min(start[1], end[1]) - length * max(bend, ARROW_CLASH_CURVE, ARROW_CURVE)
            left = min(left, start[0], end[0])
            right = max(right, start[0], end[0])
            top = min(top, peak)
            bottom = max(bottom, start[1], end[1])
        region = pygame.Rect(int(left) - pad, int(top) - pad,
                             int(right - left) + 2 * pad, int(bottom - top) + 2 * pad)
        region = region.clip(dimLayer.get_rect())
        if region.width > 0 and region.height > 0:
            dimLayer.set_clip(region)
            dimLayer.fill((0, 0, 0, 0))
            for action in waiting:
                drawOne(action, dimLayer)
            dimLayer.fill(ARROW_DIM_TINT, special_flags=pygame.BLEND_RGBA_MULT)
            dimLayer.set_clip(None)
            dimLayer.set_alpha(ARROW_DIM_ALPHA)
            window.blit(dimLayer, region.topleft, region)
    # ...then the lit / normal ones on top so their glow is never covered
    for action in bright:
        drawOne(action, window)


# ---------- turn highlight ----------

TURN_ATTACKER_COLOR = (255, 215, 0)   # outline on whoever's acting this turn
TURN_TARGET_COLOR = (230, 70, 70)     # outline on whoever's being hit this turn
TURN_HIGHLIGHT_WIDTH = 4

def drawTurnHighlight(window, action, attacker_image=None, attacker_rect=None,
                      target_image=None, target_rect=None):
    """Placeholder highlight: outlines the current action's attacker and target while that action is resolving."""
    if action is None:
        return
    drawCharacterGlow(window, action["sprite"], TURN_ATTACKER_COLOR, rect=attacker_rect, image=attacker_image)
    if action["target"] is not action["sprite"]:
        # Guard skills target the caster themselves.
        drawCharacterGlow(window, action["target"], TURN_TARGET_COLOR, rect=target_rect, image=target_image)


# ---------- Sort highlight ----------
SORT_ACTIVE_COLOR = CARD_GLOW_COLOR
SORT_ACTIVE_WIDTH = 3

def drawSortHighlight(window, sprite):
    """Outlines the sprite whose action is currently being inserted into the sorted action queue."""
    if sprite is None:
        return
    drawCharacterGlow(window, sprite, SORT_ACTIVE_COLOR)


# ---------- Sanity ----------

SANITY_ULT_MIN = 0.5

def skillLockedBySanity(sprite, skillDef):
    """True if `sprite` can't use `skillDef` right now because their sanity has fallen below the normal range (SANITY_ULT_MIN)."""
    cost = getattr(skillDef, "sanityCost", 0)
    if not cost:
        return False
    if sprite.get("ultChance") is not None:
        return sprite.get("ultLock", 0) > 0      # a boss: sanity is immune, only a sanity drain's ult-lock counts
    return sprite.get("sanity", 0.5) < SANITY_ULT_MIN

SANITY_COINFLIP_INFLUENCE = 0.6
SANITY_COINFLIP_MIN = 0.05
SANITY_COINFLIP_MAX = 0.95

def sanityHeadsChance(sanity):
    """Probability that one of this sprite's next coins lands heads, given a raw sanity value (0..1)."""
    sanity = max(0, min(sanity, 1))
    chance = 0.5 + (sanity - 0.5) * SANITY_COINFLIP_INFLUENCE
    return max(SANITY_COINFLIP_MIN, min(chance, SANITY_COINFLIP_MAX))

# Baseline (sanity 0.5) is a plain 1.0x, same as before sanity mattered.
SANITY_DAMAGE_MULT_AT_ZERO = 0.5
SANITY_DAMAGE_MULT_AT_FULL = 1.25

def sanityDamageMultiplier(sanity):
    """A second, independent multiplier on top of flipDamageMultiplier -- this one scales an action's damage by a raw sanity value."""
    sanity = max(0, min(sanity, 1))
    if sanity <= 0.5:
        return SANITY_DAMAGE_MULT_AT_ZERO + (1 - SANITY_DAMAGE_MULT_AT_ZERO) * (sanity / 0.5)
    return 1 + (SANITY_DAMAGE_MULT_AT_FULL - 1) * ((sanity - 0.5) / 0.5)

def applyActionSanityCost(action):
    """Drains the acting sprite's sanity by its skill's configured sanityCost."""
    action.setdefault("_sanityAtCast", action["sprite"].get("sanity", 0.5))

    if action.get("_sanityApplied"):
        return
    action["_sanityApplied"] = True

    cost = getattr(action["skillDef"], "sanityCost", 0)
    if cost:
        sprite = action["sprite"]
        before = sprite.get("sanity", 0.5)      # bosses pay the sanity cost of their ult like everyone else
        sprite["sanity"] = max(0, min(before - cost, 1))

# ---------- Guarding (dodge/block) ----------

ULT_BLOCK_CHANCE_MIN = 0.15
ULT_BLOCK_CHANCE_MAX = 0.20

def blockCatchesHit(skillDef):
    """Whether a currently-raised block actually catches this incoming hit at all."""
    if skillDef is not None and getattr(skillDef, "sanityCost", 0) > 0:
        return random.random() < random.uniform(ULT_BLOCK_CHANCE_MIN, ULT_BLOCK_CHANCE_MAX)
    return True

BLOCK_FLIP_MITIGATION_MULTIPLIERS = {0: 0.35, 1: 0.40, 2: 0.65}

# A dodge no longer negates a hit: it REDUCES it, by the fraction its own 2-coin flip lands (0 / 1 / 2 heads).
# Unlike a block it also works against ults (a block only catches those 15-20% of the time).
DODGE_FLIP_MITIGATION_MULTIPLIERS = {0: 0.25, 1: 0.50, 2: 0.75}

def rollDodgeMitigation(target):
    """Rolls the dodging sprite's own 2-coin flip; returns the fraction of the hit REMOVED."""
    heads = sum(flipCoins(sanityHeadsChance(target.get("sanity", 0.5))))
    return DODGE_FLIP_MITIGATION_MULTIPLIERS[heads]

def rollBlockMitigation(target):
    """Rolls the blocking sprite's own 2-coin flip."""
    heads = sum(flipCoins(sanityHeadsChance(target.get("sanity", 0.5))))
    return BLOCK_FLIP_MITIGATION_MULTIPLIERS[heads]

def activateGuard(action):
    """Raises `action`'s caster's guarding stance -- see the section note above."""
    sprite = action["sprite"]
    sprite["guard"] = action["skillDef"].icon   # "dodge" or "block"

    recover = getattr(action["skillDef"], "sanityRecover", 0)
    if recover:
        before = sprite.get("sanity", 0.5)
        sprite["sanity"] = max(0, min(before + recover, 1))

def consumeGuard(target):
    """If `target` is currently guarding."""
    kind = target.get("guard")
    if kind is not None:
        target["guard"] = None
    return kind

SANITY_REGEN_PER_HEAD = 0.08

def applyActionSanityRegen(action):
    """Landing heads is a moment of confidence/control."""
    if action.get("_sanityRegenApplied"):
        return
    action["_sanityRegenApplied"] = True

    heads = action.get("flipScore") or 0
    if heads:
        sprite = action["sprite"]
        before = sprite.get("sanity", 0.5)
        sprite["sanity"] = max(0, min(before + heads * SANITY_REGEN_PER_HEAD, 1))

# ---------- Coin-flip tiebreaker ----------

def flipCoins(headsChance=0.5):
    """Flip 2 coins, return their faces as [True, False] (True = heads)."""
    return [random.random() < headsChance for _ in range(2)]

def rollFlips(action):
    """Flip this action's 2 coins and store the faces + the heads count."""
    applyActionSanityCost(action)
    action["flips"] = flipCoins(sanityHeadsChance(action["_sanityAtCast"]))
    action["flipScore"] = sum(action["flips"])

def ensureFlips(action):
    """Flip only if this action hasn't flipped yet (an action flips once per round)."""
    if action.get("flips") is None:
        rollFlips(action)

def sortSpeed(skillDef):
    """The speed the turn-order sort uses. Dodge/block always go first (before every other skill, whatever its
    speed number); everything else sorts by its normal speed (lower = earlier)."""
    return float("-inf") if isGuardSkill(skillDef) else skillDef.speed

def isTie(actionA, actionB):
    """Two actions are tied only when they CLASH: same speed, and each one is targeting the other's sprite."""
    return (sortSpeed(actionA["skillDef"]) == sortSpeed(actionB["skillDef"])
            and actionA["target"] is actionB["sprite"]
            and actionB["target"] is actionA["sprite"])

def flipTiebreakCoin():
    """Decider coin for when both clashing actions landed the same number of heads."""
    return random.choice([True, False])

def clashWinner(actionA, actionB, tiebreakHeads=None):
    """Which of two clashing actions resolves first: more heads wins; if the heads are equal, the decider coin picks."""
    if actionA["flipScore"] != actionB["flipScore"]:
        return actionA if actionA["flipScore"] > actionB["flipScore"] else actionB
    return actionA if tiebreakHeads == (actionA["sprite"]["side"] == "left") else actionB

# Every action's own 2-coin flip also scales how much of its damage actually lands.
FLIP_DAMAGE_MULTIPLIERS = {0: 0.75, 1: 1, 2: 1.25}   # heads landed -> fraction of base damage

def flipDamageMultiplier(action):
    """Fraction of the skill's base damage this action deals, based on how many of its 2 coins landed heads."""
    return FLIP_DAMAGE_MULTIPLIERS[action["flipScore"]]

# ---------- Queue sorting and resolution ----------
def actionSort(actionQueue):
    """Instant (non-animated) sort: just runs the step generator to the end."""
    for _ in insertionSortSteps(actionQueue):
        pass
    return actionQueue

def insertionSortSteps(actionQueue):
    """Step-by-step insertion sort for the visualiser."""
    for action in actionQueue:
        action["flips"] = None
        action["flipScore"] = None

    yield actionQueue, None, None

    for i in range(1, len(actionQueue)):
        pivot = actionQueue[i]
        pivotSpeed = sortSpeed(pivot["skillDef"])

        # Is the pivot clashing with someone already sorted?
        partner = next((actionQueue[queueIndex] for queueIndex in range(i) if isTie(actionQueue[queueIndex], pivot)), None)
        mustPassPartner = False
        if partner is not None:
            animate = [partner["flips"] is None, pivot["flips"] is None]
            ensureFlips(partner)
            ensureFlips(pivot)

            tiebreak = None
            if partner["flipScore"] == pivot["flipScore"]:
                tiebreak = flipTiebreakCoin()
            mustPassPartner = clashWinner(pivot, partner, tiebreak) is pivot

            yield actionQueue, i, ([partner, pivot], animate, tiebreak)

        compareIndex = i - 1
        while compareIndex >= 0:
            other = actionQueue[compareIndex]
            otherSpeed = sortSpeed(other["skillDef"])

            if otherSpeed > pivotSpeed:
                pass                                   # slower action: pivot goes ahead of it
            elif otherSpeed == pivotSpeed and mustPassPartner:
                if other is partner:
                    mustPassPartner = False            # pivot passes its partner, then stops
            else:
                break

            actionQueue[compareIndex + 1] = actionQueue[compareIndex]
            compareIndex -= 1
            yield actionQueue, compareIndex + 1, None
        actionQueue[compareIndex + 1] = pivot
        yield actionQueue, compareIndex + 1, None

def applyQueueDamage(actionQueue):
    """Instant, silent resolve — kept for cases where you don't want per-action pacing."""
    for action in actionQueue:
        ensureFlips(action)
        for target, fraction in getActionTargets(action):
            damage = computeActionDamage(action, target, fraction)
            target["stats"].hp = max(0, target["stats"].hp - damage)

    actionQueue.clear()

def resolveQueue(actionQueue):
    actionSort(actionQueue)
    applyQueueDamage(actionQueue)

# ---------- Damage popups ----------

DAMAGE_POPUP_SPREAD_X = 0.5    # fraction of the target's width, each way
DAMAGE_POPUP_SPREAD_Y = 0.25

def createDamagePopup(popups, target, damage):
    """A popup roughly above the target, nudged by a random offset scaled to the target's own size."""
    stats = target["stats"]
    spreadX = stats.rect.width * DAMAGE_POPUP_SPREAD_X
    spreadY = stats.rect.height * DAMAGE_POPUP_SPREAD_Y
    popups.append({
        "text": f"-{damage:.0f}",
        "x": stats.rect.centerx + random.uniform(-spreadX, spreadX),
        "y": stats.rect.top + random.uniform(-spreadY, spreadY),
        "elapsed": 0,
    })

def createHealPopup(popups, target, heal):
    """Same spawn logic as createDamagePopup but for a positive heal amount."""
    stats = target["stats"]
    spreadX = stats.rect.width * DAMAGE_POPUP_SPREAD_X
    spreadY = stats.rect.height * DAMAGE_POPUP_SPREAD_Y
    popups.append({
        "text": f"+{heal:.0f}",
        "x": stats.rect.centerx + random.uniform(-spreadX, spreadX),
        "y": stats.rect.top + random.uniform(-spreadY, spreadY),
        "elapsed": 0,
        "kind": "heal",
    })

# ---------- Sanity popups ----------

SANITY_POPUP_MIN_CHANGE = 0.005
SANITY_POPUP_SIDE_GAP = 6
SANITY_POPUP_SCALE = 0.55

def createSanityPopup(popups, sprite, change):
    """Spawns a sanity popup next to `sprite`'s sanity bar."""
    if popups is None or abs(change) < SANITY_POPUP_MIN_CHANGE:
        return
    _bx, _by, _bw, _bh, sanityBarX, sanityBarWidth, sanityBarHeight, sanityBarY = _barGeometry(sprite)
    if sprite["side"] == "left":
        x, anchor = sanityBarX - SANITY_POPUP_SIDE_GAP, "right"
    else:
        x, anchor = sanityBarX + sanityBarWidth + SANITY_POPUP_SIDE_GAP, "left"
    sign = "+" if change > 0 else "-"
    popups.append({
        "text": f"{sign}{abs(change) * 100:.0f}%",
        "x": x,
        "y": sanityBarY + sanityBarHeight / 2,
        "elapsed": 0,
        "kind": "sanityUp" if change > 0 else "sanityDown",
        "scale": SANITY_POPUP_SCALE,
        "anchor": anchor,
        "float": False,
    })

def trackSanityChanges(sprites, popups):
    """Call once per frame."""
    for sprite in sprites:
        current = sprite.get("sanity", 0.5)
        previous = sprite.get("_popupSanity")
        sprite["_popupSanity"] = current
        if previous is None or sprite.get("dead"):
            continue
        change = current - previous
        if abs(change) >= SANITY_POPUP_MIN_CHANGE:
            createSanityPopup(popups, sprite, change)

def createStatusArrowPopup(statusPopups, sprite, kind):
    """Appends a one-shot buff/debuff arrow for `sprite` to `statusPopups`."""
    if statusPopups is None:
        return
    statusPopups.append({
        "sprite": sprite,
        "kind": kind,
        "x": sprite["stats"].rect.centerx,
        "elapsed": 0,
    })


# ---------- Healing (single-target + AOE) ----------

def computeActionHeal(action, target=None, fraction=1.0):
    """The full amount this action restores to `target`, before it's actually applied."""
    if target is None:
        target = action["target"]

    cache = action.setdefault("_totalHealByTarget", {})
    cacheKey = id(target)
    if cacheKey in cache:
        return cache[cacheKey]

    skillDef = action["skillDef"]
    sanityAtCast = action.get("_sanityAtCast", action["sprite"].get("sanity", 0.5))
    total = (skillDef.damage * fraction
             * flipDamageMultiplier(action)
             * sanityDamageMultiplier(sanityAtCast))

    cache[cacheKey] = total
    return total

def _applyHealToSprite(target, heal, popups):
    """Adds `heal` HP to `target`, capped at maxHp, spawns its green popup, and starts its heal glow."""
    stats = target["stats"]
    stats.hp = min(stats.maxHp, stats.hp + heal)
    createHealPopup(popups, target, heal)
    triggerHealFlash(target)

def applySplashHeal(action, popups):
    """AOE counterpart to applySplashDamage -- applies every swept-in ally's (fractional) heal in one shot, once."""
    if action.get("_splashApplied"):
        return
    action["_splashApplied"] = True

    targets = getActionTargets(action)[1:]
    action["_splashEffectTargets"] = [sprite for sprite, _ in targets]
    for sprite, fraction in targets:
        heal = computeActionHeal(action, sprite, fraction)
        _applyHealToSprite(sprite, heal, popups)

def applyActionHeal(action, popups):
    """Heal counterpart to applyActionDamage."""
    target = action["target"]
    heal = computeActionHeal(action, target)
    _applyHealToSprite(target, heal, popups)
    applySplashHeal(action, popups)
    return heal

def applyActionTickHeal(action, popups, tickIndex, ticks, combos=None):
    """Heal counterpart to applyActionTickDamage."""
    target = action["target"]
    total = computeActionHeal(action, target)
    applied = action.get("_appliedHeal", 0)

    if tickIndex >= ticks - 1:
        chunk = total - applied
    else:
        chunk = total / ticks
    action["_appliedHeal"] = applied + chunk

    target["stats"].hp = min(target["stats"].maxHp, target["stats"].hp + chunk)

    shownBefore = action.get("_shownHeal", 0)
    shownAfter = int(applied + chunk + 0.5)
    action["_shownHeal"] = shownAfter
    displayChunk = shownAfter - shownBefore

    createHealPopup(popups, target, displayChunk)
    triggerHealFlash(target)
    registerComboHit(combos, action, target, displayChunk, tickIndex, ticks)

    if tickIndex >= ticks - 1:
        applySplashHeal(action, popups)

    return chunk


# ---------- Status effects (buffs / debuffs) ----------

def statusEffectVisualKind(skillDef, effect):
    """Which of the four status-effect animations should play when the target effect function `effect` lands on a sprite."""
    if skillDef is None or effect is None:
        return None
    visualKind = EFFECT_VISUAL_KIND.get(effect)
    if visualKind is not None:
        return visualKind
    if skillDef.kind in ("buff", "debuff"):
        return skillDef.kind
    return None

def _playStatusEffectVisual(sprite, visualKind, statusPopups):
    """Shared by applyActionEffect/applyActionSelfEffect: fires whichever ON-DEMAND visual fits `visualKind`."""
    if visualKind in ("buff", "debuff", "cleanse"):
        createStatusArrowPopup(statusPopups, sprite, visualKind)
    elif visualKind == "dot":
        triggerDotFlash(sprite)
    elif visualKind == "bleed":
        triggerBleedFlash(sprite)

# ---------- When an effect lands ----------

def targetEffectFires(skillDef):
    """True if this skill's target effects are applied to its target: buff and debuff skills apply them INSTEAD of dealing damage."""
    return bool(skillDef.effects) and skillDef.kind in ("damage", "heal", "buff", "debuff")

def hasInstantEffect(skillDef):
    """True if this skill has an effect entry with no duration -- one that should land right when the action starts."""
    return ((targetEffectFires(skillDef) and any(targetEffect.duration <= 0 for targetEffect in skillDef.effects))
            or any(selfEffect.duration <= 0 for selfEffect in skillDef.selfEffects))

def hasTimedTargetEffect(skillDef):
    return targetEffectFires(skillDef) and any(targetEffect.duration > 0 for targetEffect in skillDef.effects)

def hasTimedEffect(skillDef):
    """True if this skill has an effect slot WITH a duration -- one that still waits for the cast animation to finish before landing."""
    return hasTimedTargetEffect(skillDef) or any(selfEffect.duration > 0 for selfEffect in skillDef.selfEffects)

def overwriteStatusEffect(sprite, effectFn, modifier=None, basis=None):
    """Decides whether a NEW timed status of type `effectFn` may land on `sprite`."""
    revert = EFFECT_REVERTS.get(effectFn)
    if revert is None:
        return True
    existing = [existingEffect for existingEffect in sprite.get("statusEffects", []) if existingEffect.apply is effectFn]
    if modifier is not None and any(
        effectStrength(effectFn, existingEffect.modifier, existingEffect.basis) > effectStrength(effectFn, modifier, basis) for existingEffect in existing
    ):
        return False
    remaining = []
    for statusEffect in sprite.get("statusEffects", []):
        if statusEffect.apply is effectFn:
            revert(sprite, statusEffect.modifier)
        else:
            remaining.append(statusEffect)
    sprite["statusEffects"] = remaining
    return True

def applyActionEffect(action, instant=None):
    """Applies every TargetEffect in this action's SkillDef.effects to its target(s) -- as many entries as the skill has (e.g."""
    skillDef = action["skillDef"]
    if not skillDef.effects:
        return []

    done = action.setdefault("_effectsApplied", set())
    todo = [
        (i, targetEffect) for i, targetEffect in enumerate(skillDef.effects)
        if i not in done and (instant is None or (targetEffect.duration <= 0) == instant)
    ]
    if not todo:
        return []

    targets = getActionTargets(action)
    if skillDef.kind in ("buff", "debuff") and not action.get("_splashEffectsRecorded"):
        # Only a buff/debuff records its splash targets for a splash animation copy here.
        action["_splashEffectsRecorded"] = True
        action["_splashEffectTargets"] = [sprite for sprite, _fraction in targets[1:]]

    pending = action.setdefault("_pendingEffectVisuals", [])
    affected = []
    for i, targetEffect in todo:
        done.add(i)
        revert = EFFECT_REVERTS.get(targetEffect.effect)
        visualKind = statusEffectVisualKind(skillDef, targetEffect.effect)
        for sprite, _fraction in targets:
            if sprite["dead"]:
                continue
            if targetEffect.requirement is not None and not targetEffect.requirement(sprite):
                continue
            basis = None
            amount = None
            if targetEffect.effect in EFFECT_PERCENT_OF_DAMAGE:
                basis = action.get("_totalDamageByTarget", {}).get(id(sprite), 0)
                if basis <= 0:
                    continue
                # Fixed ONCE, here: a whole number of HP lost every round.
                amount = max(1, int(targetEffect.modifier * basis + 0.5))
            # A stun ALWAYS gets a tracked effect (at least 1 round): one without would never be reverted.
            duration = targetEffect.duration if targetEffect.duration > 0 else (1 if targetEffect.effect is stun else 0)
            if duration > 0 and revert is not None:
                if not overwriteStatusEffect(sprite, targetEffect.effect, targetEffect.modifier, basis):
                    continue
            targetEffect.effect(sprite, targetEffect.modifier)
            if duration > 0 and revert is not None:
                sprite.setdefault("statusEffects", []).append(
                    EffectDef(skillDef.name, targetEffect.effect, targetEffect.modifier,
                              duration, kind=skillDef.kind, basis=basis, amount=amount)
                )
            if not any(pendingSprite is sprite and pendingKind == visualKind for pendingSprite, pendingKind in pending):
                pending.append((sprite, visualKind))
            if sprite not in affected:
                affected.append(sprite)

    return affected

def applyActionSelfEffect(action, instant=None):
    """Applies every SelfEffect in this action's SkillDef.selfEffects to the CASTER."""
    skillDef = action["skillDef"]
    caster = action["sprite"]
    done = action.setdefault("_selfEffectsApplied", set())
    landed = False

    for i, selfEffect in enumerate(skillDef.selfEffects):
        if i in done:
            continue
        if instant is not None and (selfEffect.duration <= 0) != instant:
            continue
        done.add(i)

        if caster["dead"]:
            continue
        if selfEffect.requirement is not None and not selfEffect.requirement(caster):
            continue

        if selfEffect.duration > 0 and EFFECT_REVERTS.get(selfEffect.effect) is not None:
            if not overwriteStatusEffect(caster, selfEffect.effect, selfEffect.modifier):
                done.add(i)
                continue
        selfEffect.effect(caster, selfEffect.modifier)
        if selfEffect.duration > 0 and EFFECT_REVERTS.get(selfEffect.effect) is not None:
            caster.setdefault("statusEffects", []).append(
                EffectDef(skillDef.name, selfEffect.effect, selfEffect.modifier, selfEffect.duration, kind="self")
            )

        visualKind = EFFECT_VISUAL_KIND.get(selfEffect.effect)
        pending = action.setdefault("_pendingSelfEffectVisuals", [])
        if not any(pendingKind == visualKind for _, pendingKind in pending):
            pending.append((caster, visualKind))
        landed = True

    return landed

def spawnEffectVisuals(action, statusPopups=None):
    """Flushes whatever applyActionEffect/applyActionSelfEffect queued up on `action`."""
    fired = False
    for sprite, visualKind in action.pop("_pendingEffectVisuals", []):
        _playStatusEffectVisual(sprite, visualKind, statusPopups)
        if visualKind in ("buff", "debuff", "dot", "bleed", "cleanse"):
            fired = True

    for caster, visualKind in action.pop("_pendingSelfEffectVisuals", []):
        _playStatusEffectVisual(caster, visualKind, statusPopups)
        if visualKind in ("buff", "debuff", "dot", "bleed", "cleanse"):
            fired = True

    return fired

def decayStatusEffects(sprites):
    """Ticks every sprite's active statusEffects down by one round, reverting and removing any whose duration just ran out."""
    for sprite in sprites:
        remaining = []
        for statusEffect in sprite.get("statusEffects", []):
            if getattr(statusEffect, "consumed", False):
                # This round's tick was already spent when the stun cost its victim an action (see consumeStun).
                statusEffect.consumed = False
                statusEffect.fresh = False
                remaining.append(statusEffect)
                continue
            wasFresh = statusEffect.fresh
            statusEffect.fresh = False
            if wasFresh and statusEffect.apply in EFFECT_COUNTDOWN_NEXT_ROUND:
                remaining.append(statusEffect)
                continue
            statusEffect.duration -= 1
            if statusEffect.duration <= 0:
                revert = EFFECT_REVERTS.get(statusEffect.apply)
                if revert is not None:
                    revert(sprite, statusEffect.modifier)
            else:
                remaining.append(statusEffect)
        sprite["statusEffects"] = remaining
    syncStun(sprites)


def consumeStun(sprite):
    """`sprite` just lost an action to a stun: that spends one round of the stun right now (so a sprite stunned
    mid-turn loses THIS action and is free next round, instead of also losing the next one). A longer stun keeps
    its remaining rounds; decayStatusEffects skips this round's tick for it."""
    remaining = []
    for entry in sprite.get("statusEffects", []):
        if entry.apply is stun:
            entry.duration -= 1
            if entry.duration <= 0:
                revert = EFFECT_REVERTS.get(stun)
                if revert is not None:
                    revert(sprite, entry.modifier)
                continue
            entry.consumed = True
            entry.fresh = False
        remaining.append(entry)
    sprite["statusEffects"] = remaining
    syncStun([sprite])


def syncStun(sprites):
    """The stunned flag must always match the live stun effects: a stun that has no effect on the sprite is a stuck
    stun, so clear it. Runs at every round end, so a stun can never outlive its effect."""
    for sprite in sprites:
        sprite["stats"].stunned = any(statusEffect.apply is stun for statusEffect in sprite.get("statusEffects", []))


def tickStatusEffects(sprites, popups=None, statusPopups=None, sanityTicks=None):
    """Runs every active status effect that does something each round on every living sprite."""
    ticks = []
    for sprite in sprites:
        if sprite["dead"]:
            continue
        for entry in sprite.get("statusEffects", []):
            tick = EFFECT_TICKS.get(entry.apply)
            if tick is None:
                continue
            amount = entry.modifier
            if entry.apply in EFFECT_PERCENT_OF_DAMAGE and entry.amount is not None:
                amount = entry.amount
            dealt = tick(sprite, amount)
            if entry.apply in SANITY_TICK_EFFECTS:
                if dealt != 0:
                    createStatusArrowPopup(statusPopups, sprite, EFFECT_VISUAL_KIND.get(entry.apply))
                    if sanityTicks is not None:
                        sanityTicks.append((sprite, dealt, entry))
                continue
            if dealt > 0:
                if popups is not None:
                    createDamagePopup(popups, sprite, dealt)
                triggerHitFlash(sprite)
                if EFFECT_VISUAL_KIND.get(entry.apply) == "bleed":
                    triggerBleedFlash(sprite)
                else:
                    triggerDotFlash(sprite)
                ticks.append((sprite, dealt, entry))
    return ticks


# ---------- Step-by-step action resolution ----------

# ---------- Targets (single-target + AOE splash) ----------

AOE_SPLASH_DAMAGE_FRACTION = 0.5

def getActionTargets(action):
    """Every sprite this action actually hits, as a list of pairs."""
    targets = action.get("_targets")
    if targets is not None:
        return targets

    primary = action["target"]
    targets = [(primary, 1.0)]

    targetCount = getattr(action["skillDef"], "targetCount", 1)
    if targetCount >= 3:
        allSprites = action.get("_allSprites") or []
        splash = [
            sprite for sprite in allSprites
            if sprite is not primary and sprite["side"] == primary["side"] and not sprite["dead"]
        ]
        targets += [(sprite, AOE_SPLASH_DAMAGE_FRACTION) for sprite in splash]

    action["_targets"] = targets
    return targets

# ---------- Damage calculation and application ----------
def computeActionDamage(action, target=None, fraction=1.0):
    """The full damage this action deals to `target` (defaults to the action's primary target, at fraction 1.0), before any of it lands."""
    if target is None:
        target = action["target"]

    cache = action.setdefault("_totalDamageByTarget", {})
    cacheKey = id(target)
    if cacheKey in cache:
        return cache[cacheKey]

    skillDef = action["skillDef"]
    sanityAtCast = action.get("_sanityAtCast", action["sprite"].get("sanity", 0.5))
    defenseMult = max(0.0, 1 - target["stats"].defense)
    total = (skillDef.damage * fraction * defenseMult
             * action["sprite"]["stats"].attackMult
             * flipDamageMultiplier(action)
             * sanityDamageMultiplier(sanityAtCast))

    guardKind = consumeGuard(target)
    if guardKind is not None:
        action.setdefault("_guardReactions", []).append((target, guardKind))

    if guardKind == "dodge":
        total *= 1 - rollDodgeMitigation(target)      # reduced, not negated (see DODGE_FLIP_MITIGATION_MULTIPLIERS)
    elif guardKind == "block":
        if blockCatchesHit(skillDef):
            # rollBlockMitigation returns the fraction REMOVED.
            total *= 1 - rollBlockMitigation(target)
        # else: an ult broke through -- the stance was still spent, it just didn't help.

    cache[cacheKey] = total
    return total

def popGuardReactions(action):
    """Pops (and clears) every (target, guardKind) guard-consumption computeActionDamage has recorded on `action` since the last call."""
    reactions = action.get("_guardReactions")
    if not reactions:
        return []
    action["_guardReactions"] = []
    return reactions

def popSplashEffectTargets(action):
    """Pops the AOE splash targets applySplashDamage/ applySplashHeal just applied to, since the last check."""
    targets = action.get("_splashEffectTargets")
    if not targets:
        return []
    action["_splashEffectTargets"] = []
    return targets

def applySplashDamage(action, popups):
    """Applies every AOE splash target's hit in one shot."""
    if action.get("_splashApplied"):
        return
    action["_splashApplied"] = True

    targets = getActionTargets(action)[1:]
    action["_splashEffectTargets"] = [sprite for sprite, _ in targets]
    for sprite, fraction in targets:
        damage = computeActionDamage(action, sprite, fraction)
        sprite["stats"].hp = max(0, sprite["stats"].hp - damage)
        createDamagePopup(popups, sprite, damage)
        triggerHitFlash(sprite)

def applyActionDamage(action, popups):
    """Applies one turn action's full damage in a single hit, creates the matching damage popup, and flashes the target red."""
    target = action["target"]
    damage = computeActionDamage(action, target)

    target["stats"].hp = max(0, target["stats"].hp - damage)
    createDamagePopup(popups, target, damage)
    triggerHitFlash(target)
    applySplashDamage(action, popups)
    return damage

# ---------- Combo hit tracking ----------
def registerComboHit(combos, action, target, displayChunk, tickIndex, ticks):
    """Tracks the running "xN HITS" / total-damage combo readout for a multi-tick action."""
    if combos is None:
        return None

    combo = action.get("_combo")
    if combo is None:
        combo = {
            "target": target,
            "hits": 0,
            "total": 0,
            "ticks": ticks,
            "pulse": 0,
            "finished": False,
            "finishedElapsed": 0,
        }
        action["_combo"] = combo
        combos.append(combo)

    combo["hits"] += 1
    combo["total"] += displayChunk
    combo["pulse"] = 0
    if tickIndex >= ticks - 1:
        combo["finished"] = True
    return combo

def applyActionTickDamage(action, popups, tickIndex, ticks, combos=None):
    """Applies one tick's slice of an action's total damage."""
    target = action["target"]
    total = computeActionDamage(action, target)
    applied = action.get("_appliedDamage", 0)

    if tickIndex >= ticks - 1:
        chunk = total - applied
    else:
        chunk = total / ticks
    action["_appliedDamage"] = applied + chunk

    target["stats"].hp = max(0, target["stats"].hp - chunk)

    # Popup display: don't round each tick's slice independently.
    shownBefore = action.get("_shownDamage", 0)
    shownAfter = int(applied + chunk + 0.5)
    action["_shownDamage"] = shownAfter
    displayChunk = shownAfter - shownBefore

    createDamagePopup(popups, target, displayChunk)
    triggerHitFlash(target)
    registerComboHit(combos, action, target, displayChunk, tickIndex, ticks)

    if tickIndex >= ticks - 1:
        applySplashDamage(action, popups)

    return chunk


# ---------- Action step generator ----------
def resolveActionSteps(actionQueue):
    """Resolves the action queue one action at a time, front to back (the order actionSort/insertionSortSteps already produced)."""
    while actionQueue:
        action = actionQueue[0]

        # Dead caster OR dead target -> the action dissolves, no coin flip, no attack.
        if isActionVoid(action):
            actionQueue.pop(0)
            continue

        # Stunned caster -> the action is skipped.
        if isStunned(action["sprite"]):
            applyActionSanityCost(action)
            consumeStun(action["sprite"])      # losing this action spends the stun
            actionQueue.pop(0)
            yield action, STUN_SKIP
            continue

        if action["flips"] is None:
            rollFlips(action)
            yield None, ([action], [True], None)

        actionQueue.pop(0)
        yield action, None