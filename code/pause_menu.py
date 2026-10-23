import os
import pygame
import settings
import function as fn

# ---------- Colors (battle HUD) ----------
TEXT = fn.CARD_TEXT_COLOR
GOLD = fn.CARD_HOVER_COLOR
DIM_TEXT = fn.CARD_STAT_LABEL_COLOR
INK = fn.CARD_INK

# ---------- Main-settings colors (copied from start.py so the sliders look identical) ----------
WHITE = (255, 255, 255)
ORANGE = (255, 170, 40)
PANEL_DARK = (55, 48, 42)
PANEL_BORDER = (120, 105, 90)

# ---------- Settings layout (same numbers as start.py) ----------
SLIDER_W = 500
SLIDER_H = 18
SLIDER_TITLES_Y = [110, 270, 430, 600]
SLIDER_OFFSET = 10
SETTINGS_BACK_RECT = pygame.Rect(80, 45, 140, 35)
PRESS_FRAMES = 10
MIN_SCALE = 0.90

SETTINGS_IMAGE_PATH = "assets/img/settings.png"
PAUSE_ICON_PATH = "assets/img/pause.png"      # optional: drop your own icon here and it's used instead
PAUSE_ICON_RECT = pygame.Rect(10, 10, 44, 44)


# ---------- HUD icons: pause / save / load (top-left, unenclosed, same inked style) ----------
ICON_SIZE = 44
ICON_GAP = 4
ICON_NAMES = ("pause", "save", "load")
ICON_LABELS = {"pause": "PAUSE  [ESC]", "save": "SAVE", "load": "LOAD"}
ICON_RECTS = {name: pygame.Rect(10 + i * (ICON_SIZE + ICON_GAP), 10, ICON_SIZE, ICON_SIZE)
              for i, name in enumerate(ICON_NAMES)}
PAUSE_ICON_RECT = ICON_RECTS["pause"]

# ---------- Slot menu: nudge each slot's y on its own (pixels; negative = up, positive = down) ----------
SLOT_Y_OFFSETS = (-25, -25, -25)       # (slot 1, slot 2, slot 3)
# The title and BACK button are placed from the slots' BASE positions (before the offsets above), so moving
# a slot never drags them along. Offset these two separately (pixels, same sign rule):
SLOT_TITLE_Y_OFFSET = 0
SLOT_BACK_Y_OFFSET = 0
ICON_IMAGE_PATH = "assets/img/{}.png"          # optional: assets/img/pause.png, save.png, load.png

_iconCache = {}
_toast = {"text": None, "start": 0}
TOAST_MS = 1800
TOAST_FADE_MS = 400


def showToast(text):
    """Short message shown next to the icons (e.g. "PROGRESS SAVED")."""
    _toast["text"] = text
    _toast["start"] = pygame.time.get_ticks()


def _glyph(name, color):
    """The bare icon shape in one flat color (no outline yet)."""
    surf = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
    clear = (0, 0, 0, 0)
    if name == "pause":
        pygame.draw.rect(surf, color, (10, 9, 8, 26), border_radius=2)
        pygame.draw.rect(surf, color, (26, 9, 8, 26), border_radius=2)
    elif name == "save":        # floppy disk
        pygame.draw.polygon(surf, color, [(7, 7), (29, 7), (37, 15), (37, 37), (7, 37)])
        pygame.draw.rect(surf, clear, (13, 10, 14, 8))      # shutter
        pygame.draw.rect(surf, color, (22, 11, 3, 6))       # shutter notch
        pygame.draw.rect(surf, clear, (12, 24, 20, 10))     # label
    elif name == "load":        # folder
        pygame.draw.polygon(surf, color, [(6, 11), (18, 11), (22, 15), (38, 15), (38, 35), (6, 35)])
        pygame.draw.rect(surf, clear, (6, 21, 32, 2))       # front flap line
    return surf


def _inked(fg):
    """Dark outline + drop shadow around a flat glyph -- same look as the HUD text."""
    dark = pygame.mask.from_surface(fg).to_surface(setcolor=(*INK, 255), unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface(fg.get_size(), pygame.SRCALPHA)
    out.blit(dark, (1, 3))
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            if dx or dy:
                out.blit(dark, (dx, dy))
    out.blit(fg, (0, 0))
    return out


def _iconSurface(name, hovered):
    key = (name, bool(hovered))
    if key not in _iconCache:
        path = ICON_IMAGE_PATH.format(name)
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            surf = pygame.transform.smoothscale(img, (ICON_SIZE, ICON_SIZE))
            if hovered:
                surf.fill((70, 60, 0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            surf = _inked(_glyph(name, GOLD if hovered else TEXT))
        _iconCache[key] = surf
    return _iconCache[key]


def drawHudIcons(window, mousePos):
    """Draws pause / save / load in the top-left corner. Returns {name: click rect}."""
    hoveredName = None
    for name, rect in ICON_RECTS.items():
        hovered = mousePos is not None and rect.collidepoint(mousePos)
        if hovered:
            hoveredName = name
        window.blit(_iconSurface(name, hovered), rect.topleft)

    anchor = (ICON_RECTS[ICON_NAMES[-1]].right + 14, ICON_RECTS[ICON_NAMES[0]].centery)
    now = pygame.time.get_ticks()
    age = now - _toast["start"]
    if _toast["text"] and age < TOAST_MS:
        tmp = pygame.Surface((420, 44), pygame.SRCALPHA)
        fn._drawInkedText(tmp, _toast["text"], GOLD, 400, 28, 28, 1, midleft=(4, 22))
        fade = TOAST_MS - age
        tmp.set_alpha(255 if fade >= TOAST_FADE_MS else int(255 * fade / TOAST_FADE_MS))
        window.blit(tmp, tmp.get_rect(midleft=anchor))
    elif hoveredName is not None:
        fn._drawInkedText(window, ICON_LABELS[hoveredName], DIM_TEXT, 300, 22, 22, 1, midleft=anchor)
    return dict(ICON_RECTS)


# ---------- Settings-screen helpers (mirror start.py) ----------
_settingsArt = {}


def _settingsImage(size):
    if size not in _settingsArt:
        if os.path.exists(SETTINGS_IMAGE_PATH):
            img = pygame.image.load(SETTINGS_IMAGE_PATH).convert()
            _settingsArt[size] = pygame.transform.smoothscale(img, size)
        else:
            print(f"[pause] settings art missing: {SETTINGS_IMAGE_PATH}")
            _settingsArt[size] = None
    return _settingsArt[size]


def _sliderRects(width):
    x = width // 2 - SLIDER_W // 2
    return {name: pygame.Rect(x, SLIDER_TITLES_Y[i] + SLIDER_OFFSET, SLIDER_W, SLIDER_H)
            for i, name in enumerate(settings.slider_order)}


def _drawSlider(window, rect, value):
    pygame.draw.rect(window, PANEL_DARK, rect, border_radius=9)
    fill = int(rect.width * value / 100)
    if fill > 0:
        pygame.draw.rect(window, ORANGE, (rect.x, rect.y, fill, rect.height), border_radius=9)
    pygame.draw.rect(window, PANEL_BORDER, rect, width=2, border_radius=9)
    knob = (rect.x + fill, rect.y + rect.height // 2)
    pygame.draw.circle(window, WHITE, knob, 12)
    pygame.draw.circle(window, PANEL_BORDER, knob, 12, width=2)


def _setSliderFromMouse(rect, name, mouseX):
    value = int((mouseX - rect.x) / rect.width * 100)
    settings.volume_settings[name] = max(0, min(100, value))
    if name in ("Master Volume", "Music Volume"):
        settings.update_music_volume()


def _pressScale(phase, frame):
    pressProgress = frame / PRESS_FRAMES
    return 1.0 - (1.0 - MIN_SCALE) * pressProgress if phase == "down" else MIN_SCALE + (1.0 - MIN_SCALE) * pressProgress


# ---------- HUD-style menu text ----------
def _option(window, label, center, mouse, size=44):
    """One menu entry: inked text that goes gold + underlined on hover. Returns its click rect."""
    probe = fn.renderFittedText(label, TEXT, 700, size, size).get_rect(center=center).inflate(80, 20)
    hovered = probe.collidepoint(mouse)
    color = GOLD if hovered else TEXT
    textRect = fn._drawInkedText(window, label, color, 700, size, size, 2, center=center)
    if hovered:
        fn._drawFadeRule(window, GOLD, textRect.left - 20, textRect.right + 20, textRect.bottom + 4, 2, 1)
    return probe


def _title(window, text, cx, y, size=76):
    rect = fn._drawInkedText(window, text, GOLD, 900, size, size, 3, midtop=(cx, y))
    fn._drawFadeRule(window, GOLD, cx - 190, cx + 190, rect.bottom + 8, 2, 1)
    return rect


def runPauseMenu(window, clock=None, fps=60):
    size = window.get_size()
    windowWidth, windowHeight = size
    cx = windowWidth // 2
    snapshot = window.copy()
    dim = pygame.Surface(size, pygame.SRCALPHA)
    dim.fill((0, 0, 0, 175))
    clock = clock or pygame.time.Clock()

    view = "main"
    dragging = None
    backPress = None        # [phase, frame] while the Back button squishes
    rects = {}

    while True:
        clock.tick(fps)
        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if view == "main":
                    return "continue"
                view = "main"
                dragging = None
                backPress = None

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if view == "main":
                    if rects.get("continue") and rects["continue"].collidepoint(event.pos):
                        return "continue"
                    if rects.get("settings") and rects["settings"].collidepoint(event.pos):
                        view = "settings"
                    elif rects.get("menu") and rects["menu"].collidepoint(event.pos):
                        view = "confirm"
                elif view == "settings":
                    if backPress is None:
                        if SETTINGS_BACK_RECT.collidepoint(event.pos):
                            backPress = ["down", 0]
                        else:
                            for name, sliderRect in _sliderRects(windowWidth).items():
                                knobX = sliderRect.x + int(sliderRect.width * settings.volume_settings[name] / 100)
                                knob = pygame.Rect(knobX - 12, sliderRect.y - 6, 24, sliderRect.height + 12)
                                if sliderRect.collidepoint(event.pos) or knob.collidepoint(event.pos):
                                    dragging = name
                                    _setSliderFromMouse(sliderRect, name, event.pos[0])
                                    break
                elif view == "confirm":
                    if rects.get("leave") and rects["leave"].collidepoint(event.pos):
                        return "menu"
                    if rects.get("stay") and rects["stay"].collidepoint(event.pos):
                        view = "main"

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if dragging is not None:
                    settings.saveSettings()          # a slider was just let go: remember it
                dragging = None

            elif event.type == pygame.MOUSEMOTION and dragging and view == "settings":
                _setSliderFromMouse(_sliderRects(windowWidth)[dragging], dragging, event.pos[0])

        # ---------- Back-button squish (settings) ----------
        if backPress is not None:
            backPress[1] += 1
            if backPress[1] >= PRESS_FRAMES:
                if backPress[0] == "down":
                    backPress = ["up", 0]
                else:
                    backPress = None
                    view = "main"
                    dragging = None

        # ---------- Draw ----------
        rects = {}
        if view == "settings":
            art = _settingsImage(size)
            if art is not None:
                window.blit(art, (0, 0))
            else:
                window.fill((30, 26, 22))
            for name in settings.slider_order:
                _drawSlider(window, _sliderRects(windowWidth)[name], settings.volume_settings[name])
            if backPress is not None and art is not None:
                scale = _pressScale(*backPress)
                newW = max(1, int(SETTINGS_BACK_RECT.width * scale))
                newH = max(1, int(SETTINGS_BACK_RECT.height * scale))
                slice_ = art.subsurface(SETTINGS_BACK_RECT).copy()
                squished = pygame.transform.smoothscale(slice_, (newW, newH))
                window.blit(squished, squished.get_rect(center=SETTINGS_BACK_RECT.center))
        else:
            window.blit(snapshot, (0, 0))
            window.blit(dim, (0, 0))
            if view == "main":
                title = _title(window, "PAUSED", cx, windowHeight // 2 - 190)
                top = title.bottom + 80
                rects["continue"] = _option(window, "CONTINUE", (cx, top), mouse)
                rects["settings"] = _option(window, "SETTINGS", (cx, top + 75), mouse)
                rects["menu"] = _option(window, "MAIN MENU", (cx, top + 150), mouse)
                fn._drawInkedText(window, "[ESC] RESUME", DIM_TEXT, 300, 20, 20, 1,
                                  midbottom=(cx, windowHeight - 40))
            elif view == "confirm":
                title = _title(window, "LEAVE BATTLE?", cx, windowHeight // 2 - 170, size=64)
                for i, line in enumerate(("Your progress in this stage will be lost.",
                                          "Stages you already cleared are kept.")):
                    fn._drawInkedText(window, line, DIM_TEXT, 900, 30, 30, 1,
                                      midtop=(cx, title.bottom + 40 + i * 36))
                rects["leave"] = _option(window, "MAIN MENU", (cx - 190, windowHeight // 2 + 90), mouse, size=40)
                rects["stay"] = _option(window, "KEEP PLAYING", (cx + 190, windowHeight // 2 + 90), mouse, size=40)

        pygame.display.flip()


def runConfirm(window, clock, fps, title, lines, yesLabel, noLabel):
    """Blocking yes/no box in the pause style. Returns True (yes), False (no / Esc) or None (window closed)."""
    windowWidth, windowHeight = window.get_size()
    cx = windowWidth // 2
    snapshot = window.copy()
    dim = pygame.Surface((windowWidth, windowHeight), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 175))
    clock = clock or pygame.time.Clock()
    yesRect = noRect = None
    while True:
        clock.tick(fps)
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if yesRect and yesRect.collidepoint(event.pos):
                    return True
                if noRect and noRect.collidepoint(event.pos):
                    return False
        window.blit(snapshot, (0, 0))
        window.blit(dim, (0, 0))
        head = _title(window, title, cx, windowHeight // 2 - 170, size=64)
        for i, line in enumerate(lines):
            fn._drawInkedText(window, line, DIM_TEXT, 900, 30, 30, 1, midtop=(cx, head.bottom + 40 + i * 36))
        yesRect = _option(window, yesLabel, (cx - 190, windowHeight // 2 + 90), mouse, size=40)
        noRect = _option(window, noLabel, (cx + 190, windowHeight // 2 + 90), mouse, size=40)
        pygame.display.flip()


def runSlotMenu(window, clock, fps, mode, infos):
    """Blocking slot picker (3 slots). mode is "save" or "load"; `infos` is saves.allSlotInfo().
    Returns the slot number (1-3), None if cancelled, or "quit" if the window was closed.
    In load mode empty slots are greyed out and can't be picked."""
    windowWidth, windowHeight = window.get_size()
    cx = windowWidth // 2
    snapshot = window.copy()
    dim = pygame.Surface((windowWidth, windowHeight), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 185))
    clock = clock or pygame.time.Clock()
    EMPTY = (120, 120, 132)
    rowRects = [pygame.Rect(0, 0, 660, 88) for _ in infos]
    for i, rowRect in enumerate(rowRects):
        rowRect.center = (cx, windowHeight // 2 - 70 + i * 110 + SLOT_Y_OFFSETS[i])     # title + rows + BACK are centred as one block
    # Title / BACK anchors from the un-nudged layout (rows are 88 tall, 110 apart, first centre at h//2 - 70).
    firstTop = windowHeight // 2 - 70 - 44
    lastBottom = windowHeight // 2 - 70 + 110 * (len(rowRects) - 1) + 44
    titleY = firstTop - 150 + SLOT_TITLE_Y_OFFSET
    backY = lastBottom + 52 + SLOT_BACK_Y_OFFSET
    backRect = None

    def pickable(i):
        return mode == "save" or infos[i] is not None

    while True:
        clock.tick(fps)
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3) and pickable(event.key - pygame.K_1):
                    return event.key - pygame.K_1 + 1
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rowRect in enumerate(rowRects):
                    if rowRect.collidepoint(event.pos) and pickable(i):
                        return i + 1
                if backRect is not None and backRect.collidepoint(event.pos):
                    return None

        window.blit(snapshot, (0, 0))
        window.blit(dim, (0, 0))
        _title(window, "SAVE GAME" if mode == "save" else "LOAD GAME", cx, titleY, size=68)

        for i, rowRect in enumerate(rowRects):
            info = infos[i]
            isPickable = pickable(i)
            hovered = isPickable and rowRect.collidepoint(mouse)
            nameColor = GOLD if hovered else (TEXT if isPickable else EMPTY)
            if info is None:
                detail, detailColor = "EMPTY", EMPTY
            else:
                detail = info["summary"] + (f"   -   {info['time']}" if info["time"] else "")
                detailColor = GOLD if hovered else DIM_TEXT
            # Centre by the VISIBLE glyphs (font metrics leave blank space under the text), so the
            # name + detail pair sits exactly in the middle of the row.
            nameSurf = fn.renderFittedText(f"SLOT {i + 1}", nameColor, 600, 44, 44)
            detailSurf = fn.renderFittedText(detail, detailColor, 620, 26, 26)
            nameInk, detailInk = nameSurf.get_bounding_rect(), detailSurf.get_bounding_rect()
            rowGap = 12
            top = rowRect.centery - (nameInk.height + rowGap + detailInk.height) // 2
            nameCy = top + nameInk.height // 2
            detailCy = top + nameInk.height + rowGap + detailInk.height // 2
            fn._drawInkedText(window, f"SLOT {i + 1}", nameColor, 600, 44, 44, 2,
                              center=(cx, nameCy - (nameInk.centery - nameSurf.get_height() // 2)))
            fn._drawInkedText(window, detail, detailColor, 620, 26, 26, 1,
                              center=(cx, detailCy - (detailInk.centery - detailSurf.get_height() // 2)))
            if hovered:
                fn._drawFadeRule(window, GOLD, rowRect.left, rowRect.right, rowRect.bottom - 2, 2, 1)

        backRect = _option(window, "BACK", (cx, backY), mouse, size=36)
        fn._drawInkedText(window, "[ESC] CANCEL     [1-3] QUICK PICK", DIM_TEXT, 600, 20, 20, 1,
                          midbottom=(cx, windowHeight - 24))
        pygame.display.flip()