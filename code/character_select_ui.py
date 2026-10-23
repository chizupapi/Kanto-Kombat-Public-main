import os
import pygame
from entities import CHARACTER
from stages import allEnemyNames, unlockedCharacters
from function import (
    FONT, BIG_FONT, fitIcon, drawFps,
    _cardRows, _iconAtSize, _ICON_SOURCES, STAT_ICON_FILES,
)

# Returned by runCharacterSelect when the player presses Esc.
CHARACTER_SELECT_BACK = "back"

# ---------- Layout constants ----------
TEAM_SIZE = 3

# One tall card per party slot, in the same look as the in-battle skill cards.
CARD_W = 270
CARD_H = 400
CARD_GAP = 50
CARD_PAD = 8
CARD_RADIUS = 14
CARD_ART_HEIGHT = 250        # portrait window at the top of the card
CARD_NAME_HEIGHT = 54        # name band under the portrait
CARD_STATS_HEIGHT = 30       # HP / DEF band

PALAG_W = 260
PALAG_H = 58
PALAG_GAP = 24

ARROW_W, ARROW_H = 34, 56
ARROW_INSET = 6

TITLE_CLEARANCE = 110

SLIDE_MS = 280

# The portrait fills the whole card.
GRADIENT_START = 0.38
GRADIENT_MAX_ALPHA = 250

# ---------- Portraits ----------
PORTRAIT_DIR = os.path.join("assets", "img", "charhover")
PORTRAIT_FILE_OVERRIDES = {
    # "Nanay Ehta": "nanayehta.png",
}
PORTRAIT_FOCUS_Y = 0.2

# ---------- Colors ----------
CARD_FILL = (40, 40, 40)
CARD_BORDER = (255, 255, 255)
CARD_GLOW = (255, 210, 110)
CARD_GLOW_ALPHA = 55
ART_BACKDROP = (22, 22, 28)
LINE_COLOR = (90, 90, 105)
NAME_COLOR = (255, 215, 0)
LABEL_COLOR = (150, 150, 160)
VALUE_COLOR = (235, 235, 235)

# ---------- Name font ----------
NAME_FONT_PATH = 'assets/font/monogram.ttf'
NAME_FONT_MAX_SIZE = 44
NAME_FONT_MIN_SIZE = 22
NAME_FONT_STEP = 4
_nameFontCache = {}

# ---------- Background overlay ----------
BG_COLOR = (96, 96, 100)
BG_ALPHA = 170

# ---------- Shadows and buttons ----------
SHADOW_BLUR = 8          # softness of the shadow edge, in px
SHADOW_OFFSET = (0, 10)
SHADOW_ALPHA = 170
ARROW_COLOR = (60, 60, 75)
ARROW_ALPHA = 190
START_BUTTON_COLOR = (40, 110, 60)
START_BUTTON_HOVER = (55, 140, 80)
PALAG_ALPHA = 215

TEXT_SHADOW_COLOR = (0, 0, 0, 190)
TEXT_SHADOW_OFFSET = (2, 2)


# ---------- Roster and character data ----------
def _enemyNames():
    """Every name that fights on the enemy (right) side of any stage in stages.py, plus anything flagged "enemy": True in CHARACTER."""
    names = set(allEnemyNames())   # every enemy any stage in stages.py uses
    names |= {name for name, entry in CHARACTER.items() if entry.get("enemy")}
    return names


def _rosterNames():
    """Every playable character -- has skill buttons and is not an enemy."""
    enemies = _enemyNames()
    unlocked = unlockedCharacters()           # starting team + characters handed out by unlocked chapters
    return [
        name for name in CHARACTER
        if CHARACTER[name].get("buttonSlots") and name not in enemies
        and name in unlocked                     # only characters the player has unlocked
    ]


def _artRect(cardRect):
    return pygame.Rect(cardRect.x + CARD_PAD, cardRect.y + CARD_PAD,
                       cardRect.width - 2 * CARD_PAD, CARD_ART_HEIGHT)


def _coverFit(img, size, focusY=PORTRAIT_FOCUS_Y):
    """Scales `img` to completely fill `size`, cropping whatever overflows (biased toward keeping the top, where faces are)."""
    imageWidth, imageHeight = img.get_size()
    scale = max(size[0] / imageWidth, size[1] / imageHeight)
    scaledWidth, scaledHeight = max(1, round(imageWidth * scale)), max(1, round(imageHeight * scale))
    scaled = pygame.transform.smoothscale(img, (scaledWidth, scaledHeight))
    cropX = (scaledWidth - size[0]) // 2
    cropY = round((scaledHeight - size[1]) * focusY)
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(scaled, (0, 0), pygame.Rect(cropX, cropY, size[0], size[1]))
    return out


def _roundedMask(size, radius):
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    return mask


def _bottomGradient(size):
    """Transparent at GRADIENT_START down the card, fading to dark at the bottom."""
    gradientWidth, gradientHeight = size
    grad = pygame.Surface(size, pygame.SRCALPHA)
    top = int(gradientHeight * GRADIENT_START)
    span = max(1, gradientHeight - top)
    for y in range(top, gradientHeight):
        fadeProgress = (y - top) / span
        alpha = int(GRADIENT_MAX_ALPHA * (fadeProgress ** 1.15))
        pygame.draw.line(grad, (8, 8, 12, alpha), (0, y), (gradientWidth, y))
    return grad


def _portraitPath(name):
    filename = PORTRAIT_FILE_OVERRIDES.get(name, name.lower().replace(" ", "") + ".png")
    return os.path.join(PORTRAIT_DIR, filename)


_characterDataCache = {}

def _characterData(name):
    """Everything a card needs about a roster character, built ONCE: hp/defense, and the portrait already cropped to the art window."""
    if name not in _characterDataCache:
        charObj = CHARACTER[name]["make"]()
        artSize = (CARD_W, CARD_H)   # portrait covers the whole card

        art = pygame.Surface(artSize, pygame.SRCALPHA)
        art.fill((*ART_BACKDROP, 255))
        path = _portraitPath(name)
        if os.path.exists(path):
            art.blit(_coverFit(pygame.image.load(path).convert_alpha(), artSize), (0, 0))
        else:
            print(f"[character select] portrait missing for {name} -> looked for {path}; using battle sprite")
            sprite = fitIcon(charObj.image, min(artSize) - 20)
            art.blit(sprite, sprite.get_rect(center=(artSize[0] // 2, artSize[1] // 3 + 20)))

        # dark gradient over the bottom so the text/icons stay readable
        art.blit(_bottomGradient(artSize), (0, 0))

        # round the card's corners
        art.blit(_roundedMask(artSize, CARD_RADIUS), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

        _characterDataCache[name] = {
            "hp": charObj.hp,
            "defense": charObj.defense,
            "art": art,
        }
    return _characterDataCache[name]


# ---------- Text rendering helpers ----------
def _shadowed(surf, offset=TEXT_SHADOW_OFFSET, shadowColor=TEXT_SHADOW_COLOR):
    """Adds a drop shadow behind a rendered text surface."""
    mask = pygame.mask.from_surface(surf)
    shadow = mask.to_surface(setcolor=shadowColor, unsetcolor=(0, 0, 0, 0))
    result = pygame.Surface((surf.get_width() + offset[0], surf.get_height() + offset[1]), pygame.SRCALPHA)
    result.blit(shadow, offset)
    result.blit(surf, (0, 0))
    return result


_textCache = {}

def _renderText(font, text, color):
    """Render text with FONT/BIG_FONT and give it a drop shadow in one step."""
    key = (id(font), text, color)
    surf = _textCache.get(key)
    if surf is None:
        surf = _textCache[key] = _shadowed(font.render(text, True, color))
    return surf


def _nameFont(size):
    if size not in _nameFontCache:
        _nameFontCache[size] = pygame.font.Font(NAME_FONT_PATH, size)
    return _nameFontCache[size]


_nameCache = {}

def _fitNameSurface(text, maxWidth, color):
    """Renders `text` as large as possible while staying within maxWidth, stepping the font size down until it fits."""
    key = (text, maxWidth, color)
    cached = _nameCache.get(key)
    if cached is not None:
        return cached
    size = NAME_FONT_MAX_SIZE
    surf = _nameFont(size).render(text, True, color)
    while surf.get_width() > maxWidth and size > NAME_FONT_MIN_SIZE:
        size = max(NAME_FONT_MIN_SIZE, size - NAME_FONT_STEP)
        surf = _nameFont(size).render(text, True, color)
    _nameCache[key] = _shadowed(surf)
    return _nameCache[key]


# ---------- Layout geometry ----------
def _blockHeight():
    return CARD_H + PALAG_GAP + PALAG_H


def _contentTop(screenHeight):
    """Vertically centers the cards + Palag button within the space left below the title, instead of pinning them to a fixed y."""
    available = screenHeight - TITLE_CLEARANCE
    return TITLE_CLEARANCE + max(0, (available - _blockHeight()) // 2)


def _cardRect(index, screenWidth, screenHeight):
    total = TEAM_SIZE * CARD_W + (TEAM_SIZE - 1) * CARD_GAP
    left = (screenWidth - total) // 2
    return pygame.Rect(left + index * (CARD_W + CARD_GAP), _contentTop(screenHeight), CARD_W, CARD_H)


def _palagRect(screenWidth, screenHeight):
    cardBottom = _contentTop(screenHeight) + CARD_H
    return pygame.Rect((screenWidth - PALAG_W) // 2, cardBottom + PALAG_GAP, PALAG_W, PALAG_H)


def _arrowRects(cardRect):
    """The < and > buttons, floating on the portrait's left/right edges."""
    art = _artRect(cardRect)
    left = pygame.Rect(art.left + ARROW_INSET, art.centery - ARROW_H // 2, ARROW_W, ARROW_H)
    right = pygame.Rect(art.right - ARROW_INSET - ARROW_W, art.centery - ARROW_H // 2, ARROW_W, ARROW_H)
    return left, right


def _skillCells(cardRect):
    """The 4 skill-icon cells along the card's bottom edge (screen rects)."""
    top = cardRect.y + CARD_PAD + CARD_ART_HEIGHT + CARD_NAME_HEIGHT + CARD_STATS_HEIGHT
    height = cardRect.bottom - CARD_PAD - top
    width = (cardRect.width - 2 * CARD_PAD) / 4
    return [pygame.Rect(round(cardRect.x + CARD_PAD + i * width), top, round(width), height) for i in range(4)]


# ---------- Drawing primitives ----------
_panelCache = {}

def _drawTranslucentRect(window, rect, color, alpha, borderColor=None, borderWidth=0, borderRadius=0):
    """Draws a rect that lets the background show through."""
    key = (rect.size, color, alpha, borderColor, borderWidth, borderRadius)
    panel = _panelCache.get(key)
    if panel is None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((0, 0, 0, 0))
        pygame.draw.rect(panel, (*color, alpha), panel.get_rect(), border_radius=borderRadius)
        if borderColor is not None and borderWidth > 0:
            pygame.draw.rect(panel, borderColor, panel.get_rect(), borderWidth, border_radius=borderRadius)
        panel = panel.convert_alpha()
        _panelCache[key] = panel
    window.blit(panel, rect.topleft)


_shadowCache = {}
_SHADOW_PAD = SHADOW_BLUR * 3

def _boxShadow(size, borderRadius=0):
    """Blurred shadow for a box of `size`, with the box's own footprint cut out."""
    key = (size, borderRadius)
    shadow = _shadowCache.get(key)
    if shadow is None:
        width, height = size
        pad = _SHADOW_PAD
        shadow = pygame.Surface((width + 2 * pad, height + 2 * pad), pygame.SRCALPHA)
        shadowBox = pygame.Rect(pad + SHADOW_OFFSET[0], pad + SHADOW_OFFSET[1], width, height)
        pygame.draw.rect(shadow, (0, 0, 0, SHADOW_ALPHA), shadowBox, border_radius=borderRadius)
        # cheap blur: shrink, then smooth-scale back up
        full = shadow.get_size()
        small = pygame.transform.smoothscale(shadow, (max(1, full[0] // SHADOW_BLUR), max(1, full[1] // SHADOW_BLUR)))
        shadow = pygame.transform.smoothscale(small, full)
        pygame.draw.rect(shadow, (0, 0, 0, 0), (pad, pad, width, height), border_radius=borderRadius)
        shadow = shadow.convert_alpha()
        _shadowCache[key] = shadow
    return shadow


def _bakeShadow(stage, rect, borderRadius=0):
    """Paint `rect`'s drop shadow onto the (static) background `stage`."""
    stage.blit(_boxShadow(rect.size, borderRadius), (rect.x - _SHADOW_PAD, rect.y - _SHADOW_PAD))


def _drawArrow(window, rect, direction, hovered=False):
    """Bare < / > glyph (no container): dark outline so it reads over the portrait, gold on hover."""
    char = "<" if direction < 0 else ">"
    front = _renderText(BIG_FONT, char, (255, 215, 0) if hovered else (255, 255, 255))
    dark = _renderText(BIG_FONT, char, (10, 8, 16))
    pos = front.get_rect(center=rect.center)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        window.blit(dark, pos.move(dx, dy))
    window.blit(front, pos)


def _drawPalagButton(window, rect, hovered=False):
    color = START_BUTTON_HOVER if hovered else START_BUTTON_COLOR
    _drawTranslucentRect(window, rect, color, PALAG_ALPHA, (255, 255, 255), 3 if hovered else 2, borderRadius=10)
    label = _renderText(BIG_FONT, "Palag", (255, 255, 255))
    window.blit(label, label.get_rect(center=rect.center))


# ---------- Card faces ----------
_cardFaceCache = {}

def _cardFace(name, icons, hovered, border=True):
    key = (name, hovered, border)
    face = _cardFaceCache.get(key)
    if face is not None:
        return face

    data = _characterData(name)
    face = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
    local = face.get_rect()

    pygame.draw.rect(face, CARD_FILL, local, border_radius=CARD_RADIUS)

    # full-card portrait (gradient already baked in)
    art = _artRect(local)
    face.blit(data["art"], (0, 0))

    # name band
    nameBand = pygame.Rect(local.x + CARD_PAD, art.bottom, local.width - 2 * CARD_PAD, CARD_NAME_HEIGHT)
    nameSurf = _fitNameSurface(name, nameBand.width - 16, NAME_COLOR)
    face.blit(nameSurf, nameSurf.get_rect(center=nameBand.center))

    # stats band: HP and DEF side by side, each with a dim label + bright value
    statsBand = pygame.Rect(nameBand.x, nameBand.bottom, nameBand.width, CARD_STATS_HEIGHT)
    halves = (
        ("HP", f"{data['hp']:.0f}", statsBand.centerx - 60),
        ("DEF", f"{data['defense']:.2f}", statsBand.centerx + 60),
    )
    for label, value, cx in halves:
        labelSurf = _renderText(FONT, label, LABEL_COLOR)
        valueSurf = _renderText(FONT, value, VALUE_COLOR)
        total = labelSurf.get_width() + 6 + valueSurf.get_width()
        x = cx - total // 2
        face.blit(labelSurf, (x, statsBand.centery - labelSurf.get_height() // 2))
        face.blit(valueSurf, (x + labelSurf.get_width() + 6, statsBand.centery - valueSurf.get_height() // 2))

    # skill icons along the bottom edge
    for cell, skill in zip(_skillCells(local), CHARACTER[name]["skills"][:4]):
        icon = icons.get(skill.icon)
        if icon is not None:
            face.blit(icon, icon.get_rect(center=cell.center))

    if border:
        pygame.draw.rect(face, CARD_GLOW if hovered else CARD_BORDER, local, 3 if hovered else 2, border_radius=CARD_RADIUS)

    face = face.convert_alpha()
    _cardFaceCache[key] = face
    return face


_tooltipCache = {}
_tipFonts = {}

def _tipFont(size):
    if size not in _tipFonts:
        _tipFonts[size] = pygame.font.Font(NAME_FONT_PATH, size)
    return _tipFonts[size]


def _skillTooltipFace(charName, skill, icons):
    """Compact info chip for a skill: small icon + name, then SPD / DMG (or HEAL / RED) / EFF / SAN as label-value rows."""
    key = (charName, skill.name)
    face = _tooltipCache.get(key)
    if face is not None:
        return face

    rows = [(label, value) for label, value in _cardRows(skill)]
    parts = []
    if skill.sanityCost > 0:
        parts.append(f"-{round(skill.sanityCost * 100)}%")
    if skill.sanityRecover > 0:
        parts.append(f"+{round(skill.sanityRecover * 100)}%")
    rows.append(("SAN", " ".join(parts) if parts else "-"))

    valueColors = {"SAN": (225, 130, 130) if skill.sanityCost > 0 else VALUE_COLOR}
    if skill.sanityRecover > 0 and skill.sanityCost <= 0:
        valueColors["SAN"] = (130, 210, 150)

    nameSurf = _tipFont(24).render(skill.name, True, NAME_COLOR)
    label = _tipFont(18)
    value = _tipFont(18)
    STAT_ICON_PX = 17

    def statLabel(labelText):
        """The row's stat icon (same files as the battle skill cards); falls back to the text label if that icon file isn't loaded."""
        fileName = STAT_ICON_FILES.get(labelText)
        if fileName in _ICON_SOURCES:
            return _iconAtSize(fileName, STAT_ICON_PX)
        return label.render(labelText, True, LABEL_COLOR)

    rendered = [(statLabel(statLabelText), value.render(statValueText, True, valueColors.get(statLabelText, VALUE_COLOR))) for statLabelText, statValueText in rows]

    icon = icons.get(skill.icon)
    iconSize = 22
    if icon is not None:
        icon = fitIcon(icon, iconSize)

    pad, columnGap, rowHeight = 9, 14, 20
    headerW = nameSurf.get_width() + (iconSize + 6 if icon is not None else 0)
    rowsW = max(statLabelText.get_width() + columnGap + statValueText.get_width() for statLabelText, statValueText in rendered)
    width = max(headerW, rowsW) + 2 * pad
    width = max(width, 110)
    height = pad + max(iconSize, nameSurf.get_height()) + 6 + 1 + 5 + rowHeight * len(rendered) + pad - 2

    face = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(face, (18, 18, 24, 238), face.get_rect(), border_radius=8)
    pygame.draw.rect(face, (255, 255, 255, 200), face.get_rect(), 1, border_radius=8)

    x = pad
    headerH = max(iconSize, nameSurf.get_height())
    if icon is not None:
        face.blit(icon, icon.get_rect(midleft=(x, pad + headerH // 2)))
        x += iconSize + 6
    face.blit(nameSurf, nameSurf.get_rect(midleft=(x, pad + headerH // 2)))

    y = pad + headerH + 6
    pygame.draw.line(face, LINE_COLOR, (pad, y), (width - pad, y), 1)
    y += 5
    for statLabelText, statValueText in rendered:
        face.blit(statLabelText, statLabelText.get_rect(midleft=(pad, y + rowHeight // 2)))
        face.blit(statValueText, statValueText.get_rect(midright=(width - pad, y + rowHeight // 2)))
        y += rowHeight

    face = face.convert_alpha()
    _tooltipCache[key] = face
    return face


def _drawSkillTooltip(window, charName, skill, icons, anchorRect, bounds):
    """Small popup above a hovered skill icon."""
    face = _skillTooltipFace(charName, skill, icons)
    box = face.get_rect()
    box.midbottom = (anchorRect.centerx, anchorRect.top - 4)
    box.clamp_ip(bounds)
    window.blit(face, box.topleft)


# ---------- Character select screen loop ----------
def runCharacterSelect(window, screenWidth, screenHeight, icons, camera, background=None,
                       subtitle=None, subtitleColor=(255, 215, 0), overlay=None, defaultTeam=None, lockTeam=False):
    """Pre-battle screen: 3 portrait cards, one per party slot, each showing the character's art, name, HP / DEF and its 4 skill icons."""
    roster = _rosterNames()
    indices = list(range(min(TEAM_SIZE, len(roster))))
    # Optional pre-picked team (the tutorial stage uses this); ignored if any name isn't playable.
    if defaultTeam and len(defaultTeam) == TEAM_SIZE and all(characterName in roster for characterName in defaultTeam):
        indices = [roster.index(characterName) for characterName in defaultTeam]

    # Pay for every character's image load/scale/crop and card face once.
    for name in roster:
        _characterData(name)
        _cardFace(name, icons, False)
        _cardFace(name, icons, True)
        _cardFace(name, icons, False, border=False)
        for skill in CHARACTER[name]["skills"][:4]:
            _skillTooltipFace(name, skill, icons)

    bigSurface = camera.bigSurface
    contentSurface = camera.sceneSurface

    bigSize = bigSurface.get_size()
    margin = camera.margin
    if background is not None:
        stage = background.copy()
        grey = pygame.Surface(bigSize, pygame.SRCALPHA)
        grey.fill((*BG_COLOR, BG_ALPHA))
        stage.blit(grey, (0, 0))
    else:
        stage = pygame.Surface(bigSize).convert()
        stage.fill(BG_COLOR)
    # Shadows belong to the cards.
    shadowBlits = []
    for rect, radius in (
        [(_cardRect(i, screenWidth, screenHeight), CARD_RADIUS) for i in range(TEAM_SIZE)]
        + [(_palagRect(screenWidth, screenHeight), 10)]
    ):
        rect = rect.move(margin, margin)
        shadowBlits.append((_boxShadow(rect.size, radius), (rect.x - _SHADOW_PAD, rect.y - _SHADOW_PAD)))

    clock = camera.clock

    subtitleSurf = None
    if subtitle:
        subtitleSurf = _renderText(pygame.font.Font('assets/font/monogram.ttf', 36), subtitle, subtitleColor)

    flips = [None] * TEAM_SIZE
    # Cards can only be swapped when there is somebody NEW to swap in (more unlocked characters than team slots)
    # and the team isn't locked (tutorial). Otherwise the arrows are hidden and do nothing.
    canChange = (not lockTeam) and len(roster) > TEAM_SIZE
    cardMask = _roundedMask((CARD_W, CARD_H), CARD_RADIUS)

    def cycle(i, direction):
        idx = indices[i]
        others = {indices[otherSlot] for otherSlot in range(TEAM_SIZE) if otherSlot != i}
        for _ in range(len(roster)):
            idx = (idx + direction) % len(roster)
            if idx not in others:
                flips[i] = {"start": pygame.time.get_ticks(), "from": roster[indices[i]], "to": roster[idx], "dir": direction}
                indices[i] = idx
                return

    sceneBounds = pygame.Rect(0, 0, screenWidth, screenHeight)

    while True:
        dt = clock.tick(60)
        now = pygame.time.get_ticks()
        palagRect = _palagRect(screenWidth, screenHeight)

        # the shared camera's faint glance-around-the-shot lean
        camera.update(dt)

        # mouse in scene space (undoes the camera's pan), for hover + clicks
        mouse = camera.toScene(pygame.mouse.get_pos())

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clickPos = camera.toScene(event.pos)
                if palagRect.collidepoint(clickPos):
                    return [roster[i] for i in indices]
                for i in range(TEAM_SIZE):
                    if flips[i] is not None or not canChange:
                        continue   # mid-slide, a locked team, or no new character to swap in: ignore clicks
                    leftArrow, rightArrow = _arrowRects(_cardRect(i, screenWidth, screenHeight))
                    if leftArrow.collidepoint(clickPos):
                        cycle(i, -1)
                    elif rightArrow.collidepoint(clickPos):
                        cycle(i, 1)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                return [roster[i] for i in indices]
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return CHARACTER_SELECT_BACK

        bigSurface.blit(stage, camera.backgroundOffset())   # far layer: leans less than the cards
        for shadow, pos in shadowBlits:
            bigSurface.blit(shadow, pos)

        title = _renderText(BIG_FONT, "Choose Your Team", (255, 255, 255))
        titleY = 40 if subtitleSurf is not None else 50
        contentSurface.blit(title, title.get_rect(center=(screenWidth // 2, titleY)))
        if subtitleSurf is not None:
            contentSurface.blit(subtitleSurf, subtitleSurf.get_rect(center=(screenWidth // 2, 88)))

        tooltip = None
        for i in range(TEAM_SIZE):
            rect = _cardRect(i, screenWidth, screenHeight)
            flip = flips[i]

            if flip is not None:
                flipProgress = (now - flip["start"]) / SLIDE_MS
                if flipProgress >= 1:
                    flips[i] = flip = None
            if flip is not None:
                # slide: old card exits one way while the new one enters from the other.
                easedProgress = 1 - (1 - flipProgress) ** 3   # ease-out
                flipDirection = flip["dir"]
                comp = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
                comp.blit(_cardFace(flip["from"], icons, False, border=False), (round(-flipDirection * CARD_W * easedProgress), 0))
                comp.blit(_cardFace(flip["to"], icons, False, border=False), (round(flipDirection * CARD_W * (1 - easedProgress)), 0))
                comp.blit(cardMask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                pygame.draw.rect(comp, CARD_BORDER, comp.get_rect(), 2, border_radius=CARD_RADIUS)
                contentSurface.blit(comp, rect.topleft)
                continue

            name = roster[indices[i]]
            hovered = rect.collidepoint(mouse)
            contentSurface.blit(_cardFace(name, icons, hovered), rect.topleft)

            if canChange:
                leftArrow, rightArrow = _arrowRects(rect)
                _drawArrow(contentSurface, leftArrow, -1, leftArrow.collidepoint(mouse))
                _drawArrow(contentSurface, rightArrow, 1, rightArrow.collidepoint(mouse))

            for cell, skill in zip(_skillCells(rect), CHARACTER[name]["skills"][:4]):
                if cell.collidepoint(mouse):
                    pygame.draw.rect(contentSurface, CARD_GLOW, cell.inflate(-6, -6), 1, border_radius=6)
                    tooltip = (name, skill, cell)

        _drawPalagButton(contentSurface, palagRect, palagRect.collidepoint(mouse))

        # drawn last so it floats above every card
        if tooltip is not None:
            _drawSkillTooltip(contentSurface, tooltip[0], tooltip[1], icons, tooltip[2], sceneBounds)

        camera.present(window)
        if overlay is not None:
            overlay(window)      # screen-space extras (the tutorial tip)
        drawFps(window, clock)

        pygame.display.update()