import pygame
import sys
import os
import json
import stages
import campaign
import tutorial
import saves
from settings import volume_settings, slider_order, update_music_volume, saveSettings

if getattr(sys, "frozen", False):
    os.chdir(sys._MEIPASS)   # assets and __file__-based paths resolve inside the bundle

# ---------- Initialization and window ----------
pygame.init()

WIDTH, HEIGHT = 1284, 702
FPS = 60  # frames per second the game is capped at

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Kanto Kombat")
clock = pygame.time.Clock()

# ---------- Colors ----------
WHITE = (255, 255, 255)  # text colour (RGB)
ORANGE = (255, 170, 40)  # highlight colour for hovered buttons (RGB)
PANEL_DARK = (55, 48, 42)  # button fill colour (RGB)
PANEL_BORDER = (120, 105, 90)  # button border colour (RGB)

# ---------- Fonts ----------
font_notice = pygame.font.SysFont("arial", 22)
font_button = pygame.font.SysFont("arialblack", 30)
font_preview = pygame.font.SysFont("arialblack", 40)
font_small = pygame.font.SysFont("arial", 22)
font_lock = pygame.font.SysFont("arialblack", 22)
font_back = pygame.font.SysFont("arialblack", 20)

# ---------- Images ----------
ui_image = pygame.image.load('assets/img/start.png').convert()
ui_image = pygame.transform.smoothscale(ui_image, (WIDTH, HEIGHT))

settings_image = pygame.image.load('assets/img/settings.png').convert()
settings_image = pygame.transform.smoothscale(settings_image, (WIDTH, HEIGHT))

characters_bg_image = pygame.image.load('assets/img/characters.png').convert()
characters_bg_image = pygame.transform.smoothscale(characters_bg_image, (WIDTH, HEIGHT))

chapter_bg_image = pygame.image.load('assets/img/chapter.png').convert()
chapter_bg_image = pygame.transform.smoothscale(chapter_bg_image, (WIDTH, HEIGHT))

# ---------- Background music ----------
BGM_PATH = 'assets/sounds/battlemusic/start.mp3'  # main menu music (loops)

pygame.mixer.init()
pygame.mixer.music.load(BGM_PATH)
pygame.mixer.music.play(-1)  # -1 = loop forever


# ---------- Save / Load ----------
SAVE_PATH = saves.AUTOSAVE_PATH  # file the 30-second autosave writes to (inside the save_data folder)

# volume_settings / slider_order live in settings.py (shared with the battle pause menu)

update_music_volume()

selected_character = None
selected_chapter = None


def load_game():
    """Reloads settings + stage progress from the save file. Returns True if a save was loaded."""
    global selected_character, selected_chapter
    if not os.path.exists(SAVE_PATH):
        print("No save file found.")
        return False
    try:
        with open(SAVE_PATH, "r") as saveFile:
            data = json.load(saveFile)
    except (OSError, ValueError) as err:
        print(f"Couldn't read save file: {err}")
        return False
    selected_character = data.get("selected_character", selected_character)     # (volume lives in settings.json)
    selected_chapter = data.get("selected_chapter", selected_chapter)
    stages.importProgress(data.get("stage_progress", {}))
    print("Game loaded:", data)
    return True


def save_game(silent=False):
    """Writes settings + stage progress to the save file. Returns True on success."""
    data = {
        "volume_settings": volume_settings,
        "selected_character": selected_character,
        "selected_chapter": selected_chapter,
        "stage_progress": stages.exportProgress(),   # stages cleared per chapter (0-3)
    }
    saves.ensureSaveDir()
    try:
        with open(SAVE_PATH, "w") as saveFile:
            json.dump(data, saveFile, indent=2)
    except OSError as err:
        print(f"Couldn't save: {err}")
        return False
    if not silent:
        print("Game saved:", data)
    return True


# ---------- Save slots (1-3) ----------
def save_to_slot(slot):
    """Writes the current progress + settings into slot 1-3. Returns True on success."""
    return saves.writeSlot(slot, {
        "selected_character": selected_character,
        "selected_chapter": selected_chapter,
    })


def load_from_slot(slot):
    """Applies slot 1-3 (settings + stage progress). Returns True if the slot had a save."""
    global selected_character, selected_chapter
    data = saves.readSlot(slot)
    if data is None:
        return False
    selected_character = data.get("selected_character", selected_character)     # (volume lives in settings.json)
    selected_chapter = data.get("selected_chapter", selected_chapter)
    stages.importProgress(data.get("stage_progress", {}))
    print(f"Slot {slot} loaded")
    return True


def open_load_menu():
    """Main-menu Load button: pick a slot, load it, then jump straight to the chapter + stage it resumes at."""
    global running, state
    from pause_menu import runSlotMenu     # imported here: it needs the display + fonts to exist
    slot = runSlotMenu(screen, clock, FPS, "load", saves.allSlotInfo())
    if slot == "quit":
        running = False
        return
    if slot is None or not load_from_slot(slot):
        return

    chapter, _stage = saves.resumePoint(stages.exportProgress())
    state = CHAPTERS                       # "back" from the chapter lands on the chapter screen
    if chapter is None:
        return                             # every chapter cleared: just show the chapter screen
    select_chapter(chapter)                # starts at the first uncleared stage -> its team select


# ---------- Autosave ----------
AUTOSAVE_INTERVAL_MS = 30_000  # milliseconds between autosaves
last_autosave_time = pygame.time.get_ticks()
autosave_notice_timer = 0

load_game()   # restore stage progress (unlocked chapters) from save_data/savegame.json

# ---------- Screen state ----------
MENU, SETTINGS, CHARACTERS, DETAIL, CHAPTERS = "menu", "settings", "characters", "detail", "chapters"
state = MENU

# ---------- Button press animation ----------
PRESS_FRAMES = 10  # frames the button squish takes (down, then back up)
MIN_SCALE = 0.90  # smallest size a pressed button shrinks to (0.90 = 90%)


def get_scale(phase, frame, min_scale=MIN_SCALE):
    if phase is None:
        return 1.0
    pressProgress = frame / PRESS_FRAMES
    if phase == "down":
        return 1.0 - (1.0 - min_scale) * pressProgress
    else:
        return min_scale + (1.0 - min_scale) * pressProgress


# ---------- Menu ----------
def start_game():
    """START = a NEW GAME: wipes stage progress and the tutorial flag, so Barangay opens with the story again.
    (Use the Load button to continue from a save slot.)"""
    global state
    stages.importProgress({})
    tutorial.resetProgress()
    campaign.resetStory()
    state = CHAPTERS


def open_characters():
    global state
    state = CHARACTERS


def open_settings():
    global state
    state = SETTINGS


btn_w, btn_h = 260, 42
btn_x = 39
start_y = 340

btn_w2, btn_h2 = 250, 30
btn_x2 = 40
start_y2 = 405
spacing = 22

buttons = [
    (pygame.Rect(btn_x, start_y, btn_w, btn_h), start_game),
    (pygame.Rect(btn_x2, start_y2, btn_w2, btn_h2), open_characters),
    (pygame.Rect(btn_x2, start_y2 + (btn_h2 + spacing) * 1, btn_w2, btn_h2), open_settings),
    (pygame.Rect(btn_x2, start_y2 + (btn_h2 + spacing) * 2, btn_w2, btn_h2), open_load_menu)
]

pressed_index = None
press_frame = 0
press_phase = None
pending_callback = None


def start_press(index):
    global pressed_index, press_frame, press_phase
    pressed_index = index
    press_frame = 0
    press_phase = "down"


# ---------- Settings ----------
slider_x = WIDTH // 2 - 250
slider_w = 500
slider_h = 18
slider_titles_y = [110, 270, 430, 600]
slider_offset = 10

sliders = {}
for i, name in enumerate(slider_order):
    y = slider_titles_y[i] + slider_offset
    sliders[name] = pygame.Rect(slider_x, y, slider_w, slider_h)

settings_back_rect = pygame.Rect(80, 45, 140, 35)
dragging_slider = None

back_pressed = False
back_press_frame = 0
back_press_phase = None
back_pending = False


def start_back_press():
    global back_pressed, back_press_frame, back_press_phase
    back_pressed = True
    back_press_frame = 0
    back_press_phase = "down"


def draw_slider(rect, value):
    pygame.draw.rect(screen, PANEL_DARK, rect, border_radius=9)
    fill_w = int(rect.width * value / 100)
    if fill_w > 0:
        pygame.draw.rect(screen, ORANGE, (rect.x, rect.y, fill_w, rect.height), border_radius=9)
    pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=9)

    knob_x = rect.x + fill_w
    pygame.draw.circle(screen, WHITE, (knob_x, rect.y + rect.height // 2), 12)
    pygame.draw.circle(screen, PANEL_BORDER, (knob_x, rect.y + rect.height // 2), 12, width=2)


def set_slider_from_mouse(name, mouse_x):
    rect = sliders[name]
    rel_x = mouse_x - rect.x
    value = int(rel_x / rect.width * 100)
    volume_settings[name] = max(0, min(100, value))
    if name in ("Master Volume", "Music Volume"):
        update_music_volume()


# ---------- Characters ----------
character_names = [
    "Sandugo", "Sampaguita",
    "Darit", "Salmonega",
    "Otab", "Doflaminguard",
    "Gulok", "Por",
    "Nanay Etha", "Yombits",
    "Popper", "< Return",
]

# (x, y, width, height) click box for each name on the Characters screen, same order as character_names
CHARACTER_GRID = [
    (41, 58, 308, 60), (410, 58, 317, 60),
    (41, 164, 308, 60), (410, 164, 317, 60),
    (41, 274, 308, 60), (410, 274, 317, 60),
    (41, 386, 308, 60), (410, 386, 317, 60),
    (41, 494, 308, 60), (410, 494, 317, 60),
    (41, 599, 308, 60), (410, 599, 317, 60),
]

character_boxes = [
    (pygame.Rect(*CHARACTER_GRID[i]), name) for i, name in enumerate(character_names)
]

RETURN_INDEX = len(character_names) - 1  # position of the "< Return" entry in character_names

DEBUG_SHOW_HITBOXES = False  # True = draw red outlines around clickable areas

pressed_card = None
card_press_frame = 0
card_press_phase = None
card_pending_action = None


def start_card_press(index, action):
    global pressed_card, card_press_frame, card_press_phase, card_pending_action
    pressed_card = index
    card_press_frame = 0
    card_press_phase = "down"
    card_pending_action = action


def name_slug(name):
    """Turn a display name into a filesystem-safe slug."""
    return name.lower().replace(" ", "_").replace("<", "").strip("_").strip()


# display name -> portrait file, used instead of the automatic file name
PORTRAIT_FILENAME_OVERRIDES = {
    "Sandugo": "sandugo.png",
    "Darit": "darit.png",
    "Otab": "otab.png",
    "Gulok": "gulok.png",
    "Nanay Etha": "nanayehta.png",
    "Popper": "popper.png",
    "Sampaguita": "sampaguita.png",
    "Salmonega": "salmonega.png",
    "Doflaminguard": "doflaminguard.png",
    "Por": "por.png",
    "Yombits": "yombits.png",
}

# display name -> full-detail image file, used instead of the automatic file name
FULLSCREEN_FILENAME_OVERRIDES = {
    "Sandugo": "sandugo.jpg",
    "Darit": "darit.jpg",
    "Otab": "otab.jpg",
    "Gulok": "gulok.jpg",
    "Nanay Etha": "nanayehta.jpg",
    "Popper": "popper.jpg",
    "Sampaguita": "sampaguita.jpg",
    "Salmonega": "salmonega.jpg",
    "Doflaminguard": "doflaminguard.jpg",
    "Por": "por.jpg",
    "Yombits": "yombits.jpg",
}


def portrait_path(name):
    filename = PORTRAIT_FILENAME_OVERRIDES.get(name, f"{name_slug(name)}.png")
    return os.path.join("assets", "img", "charhover", filename)


def full_detail_path(name):
    fullpress = FULLSCREEN_FILENAME_OVERRIDES.get(name, f"{name_slug(name)}.jpg")
    return os.path.join("assets", "img", "charpress", fullpress)


_portrait_cache = {}
_full_detail_cache = {}


def get_portrait(name):
    if name not in _portrait_cache:
        path = portrait_path(name)
        if os.path.exists(path):
            _portrait_cache[name] = pygame.image.load(path).convert_alpha()
        else:
            print(f"[portrait missing] {name} -> looked for {path}")
            _portrait_cache[name] = None
    return _portrait_cache[name]


def get_full_detail(name):
    if name not in _full_detail_cache:
        path = full_detail_path(name)
        if os.path.exists(path):
            _full_detail_cache[name] = pygame.image.load(path).convert()
        else:
            print(f"[full detail missing] {name} -> looked for {path}")
            _full_detail_cache[name] = None
    return _full_detail_cache[name]


def draw_outlined_text_centered(surface, text, font, center, fill_color, outline_color, outline_width=2):
    outline = font.render(text, True, outline_color)
    outline_rect = outline.get_rect(center=center)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx or dy:
                surface.blit(outline, (outline_rect.x + dx, outline_rect.y + dy))
    main = font.render(text, True, fill_color)
    surface.blit(main, main.get_rect(center=center))


def draw_character_box(index, rect, name, hovered):
    scale = 1.0
    if index == pressed_card and index == RETURN_INDEX:
        scale = get_scale(card_press_phase, card_press_frame)

    draw_rect = rect
    if scale != 1.0:
        new_w = max(1, int(rect.width * scale))
        new_h = max(1, int(rect.height * scale))
        draw_rect = pygame.Rect(0, 0, new_w, new_h)
        draw_rect.center = rect.center

    if index == pressed_card and scale != 1.0:
        box_slice = characters_bg_image.subsurface(rect).copy()
        squished = pygame.transform.smoothscale(box_slice, draw_rect.size)
        screen.blit(squished, draw_rect.topleft)

    if hovered:
        screen.blit(get_highlight(rect.size), rect.topleft)
        pygame.draw.rect(screen, WHITE, rect, width=3, border_radius=6)

    if DEBUG_SHOW_HITBOXES:
        pygame.draw.rect(screen, (255, 0, 0), rect, width=1)


# ---------- Render caches (avoid re-scaling / re-allocating every frame) ----------
_scaled_cache = {}
_highlight_cache = {}


def cached_smoothscale(key, img, size):
    """smoothscale once per (key, size); the result is reused every frame."""
    cacheKey = (key, size)
    surf = _scaled_cache.get(cacheKey)
    if surf is None:
        surf = pygame.transform.smoothscale(img, size)
        _scaled_cache[cacheKey] = surf
    return surf


def get_highlight(size):
    surf = _highlight_cache.get(size)
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((248, 248, 255, 60))
        _highlight_cache[size] = surf
    return surf


def draw_preview_panel(name):
    panel_rect = pygame.Rect(750, 60, 500, 600)
    img = get_portrait(name)
    if img is not None:
        scaled = cached_smoothscale(("preview", name), img, panel_rect.size)
        screen.blit(scaled, panel_rect.topleft)
    else:
        placeholder = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        placeholder.fill((0, 0, 0, 150))
        screen.blit(placeholder, panel_rect.topleft)
        pygame.draw.rect(screen, WHITE, panel_rect, width=3, border_radius=8)
        label = font_preview.render(name.upper(), True, WHITE)
        screen.blit(label, label.get_rect(center=panel_rect.center))


def draw_detail_screen():
    full_img = get_full_detail(selected_character)
    if full_img is not None:
        scaled = cached_smoothscale(("detail", selected_character), full_img, (WIDTH, HEIGHT))
        screen.blit(scaled, (0, 0))
    else:
        screen.blit(characters_bg_image, (0, 0))
        title = font_preview.render(selected_character.upper(), True, WHITE)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 80)))

        art_rect = pygame.Rect(WIDTH // 2 - 200, 160, 400, 440)
        img = get_portrait(selected_character)
        if img is not None:
            scaled = cached_smoothscale(("art", selected_character), img, art_rect.size)
            screen.blit(scaled, art_rect.topleft)
        else:
            placeholder = pygame.Surface(art_rect.size, pygame.SRCALPHA)
            placeholder.fill((0, 0, 0, 150))
            screen.blit(placeholder, art_rect.topleft)
            pygame.draw.rect(screen, WHITE, art_rect, width=3, border_radius=8)

    hint = font_small.render("PRESS ESC TO GO BACK", True, WHITE)
    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 30)))


# ---------- Chapters (from chapters.py) ----------
CHAPTER_BACK_RECT = pygame.Rect(80, 45, 140, 35)  # (x, y, width, height) of the < BACK button on the chapter screen

# (x, y, width, height) click box of each chapter card, left to right
CHAPTER_GRID = [
    (46, 220, 265, 350),
    (361, 220, 255, 350),
    (667, 220, 255, 350),
    (971, 220, 265, 350)
]

# Left-to-right display order, matching the card art.
CHAPTER_NAMES = ["Barangay", "City", "Country", "Province"]

chapter_boxes = [
    (pygame.Rect(*CHAPTER_GRID[i]), name) for i, name in enumerate(CHAPTER_NAMES)
]

# Actual story/unlock order: Province is chapter 3.
CHAPTER_ORDER = ["Barangay", "City", "Province", "Country"]

# A chapter counts as completed once its boss stage is cleared.

CHAPTER_SHADOW_ALPHA = 180  # darkness of the LOCKED overlay, 0 (invisible) to 255 (black)


def is_chapter_locked(index):
    """A chapter is locked until every chapter before it in story order (CHAPTER_ORDER) has been completed."""
    name = CHAPTER_NAMES[index]
    story_index = CHAPTER_ORDER.index(name)
    if story_index == 0:
        return False
    return not all(stages.isChapterCompleted(earlierChapterName) for earlierChapterName in CHAPTER_ORDER[:story_index])


def draw_lock_label(rect):
    label = font_lock.render("LOCKED", True, WHITE)
    screen.blit(label, label.get_rect(center=rect.center))


# which element is being pressed on the chapters screen: ("back",) or ("card", index)
pressed_chapter_target = None
chapter_press_frame = 0
chapter_press_phase = None
chapter_pending_action = None


def start_chapter_press(target, action):
    global pressed_chapter_target, chapter_press_frame, chapter_press_phase, chapter_pending_action
    pressed_chapter_target = target
    chapter_press_frame = 0
    chapter_press_phase = "down"
    chapter_pending_action = action


def go_back_to_menu():
    global state
    state = MENU


def select_chapter(name):
    # Plays the chapter progressively: team select + battle for whichever one is picked.
    global selected_chapter, running, state
    selected_chapter = name
    result = campaign.playChapter(
        screen, name,
        background=chapter_bg_image,
        menuMusic=BGM_PATH,
        onProgress=lambda: save_game(silent=True),   # autosave right after a stage is cleared
        onSave=save_to_slot,                         # battle HUD save icon (slot 1-3)
        onLoad=load_from_slot,                       # battle HUD load icon (slot 1-3)
    )
    if result == "quit":
        running = False
    elif result == "menu":
        state = MENU          # "Main Menu" chosen from the battle pause menu


def draw_chapter_back_button(mouse_pos):
    """A real, visible Back button (squishes when pressed, like the other buttons)."""
    scale = 1.0
    if pressed_chapter_target == ("back",):
        scale = get_scale(chapter_press_phase, chapter_press_frame)

    draw_rect = pygame.Rect(0, 0, max(1, int(CHAPTER_BACK_RECT.width * scale)),
                            max(1, int(CHAPTER_BACK_RECT.height * scale)))
    draw_rect.center = CHAPTER_BACK_RECT.center

    hovered = CHAPTER_BACK_RECT.collidepoint(mouse_pos)
    pygame.draw.rect(screen, (85, 74, 62) if hovered else PANEL_DARK, draw_rect, border_radius=8)
    pygame.draw.rect(screen, ORANGE if hovered else PANEL_BORDER, draw_rect, width=3, border_radius=8)
    label = font_back.render("< BACK", True, WHITE)
    screen.blit(label, label.get_rect(center=draw_rect.center))

    if DEBUG_SHOW_HITBOXES:
        pygame.draw.rect(screen, (255, 0, 0), CHAPTER_BACK_RECT, width=1)


def draw_chapter_card(index, rect, name):
    locked = is_chapter_locked(index)

    scale = 1.0
    if not locked and pressed_chapter_target == ("card", index):
        scale = get_scale(chapter_press_phase, chapter_press_frame)

    draw_rect = rect
    if scale != 1.0:
        new_w = max(1, int(rect.width * scale))
        new_h = max(1, int(rect.height * scale))
        draw_rect = pygame.Rect(0, 0, new_w, new_h)
        draw_rect.center = rect.center
        slice_ = chapter_bg_image.subsurface(rect).copy()
        squished = pygame.transform.smoothscale(slice_, draw_rect.size)
        screen.blit(squished, draw_rect.topleft)

    if locked:
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        shadow.fill((0, 0, 0, CHAPTER_SHADOW_ALPHA))
        screen.blit(shadow, rect.topleft)
        draw_lock_label(rect)

    if DEBUG_SHOW_HITBOXES:
        pygame.draw.rect(screen, (255, 0, 0), rect, width=1)


def draw_chapters_screen(mouse_pos):
    screen.blit(chapter_bg_image, (0, 0))
    for i, (rect, name) in enumerate(chapter_boxes):
        draw_chapter_card(i, rect, name)
    draw_chapter_back_button(mouse_pos)


# ---------- Main loop ----------
running = True
while running:
    mouse_pos = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if state == SETTINGS:
                state = MENU
            elif state == CHARACTERS:
                state = MENU
            elif state == DETAIL:
                state = CHARACTERS
            elif state == CHAPTERS:
                if pressed_chapter_target is None:
                    state = MENU
            else:
                running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if state == MENU:
                for i, (rect, callback) in enumerate(buttons):
                    if rect.collidepoint(event.pos):
                        start_press(i)
                        pending_callback = callback

            elif state == SETTINGS:
                if settings_back_rect.collidepoint(event.pos):
                    start_back_press()
                    back_pending = True
                else:
                    for name, rect in sliders.items():
                        knob_x = rect.x + int(rect.width * volume_settings[name] / 100)
                        knob_rect = pygame.Rect(knob_x - 12, rect.y - 6, 24, rect.height + 12)
                        if rect.collidepoint(event.pos) or knob_rect.collidepoint(event.pos):
                            dragging_slider = name
                            set_slider_from_mouse(name, event.pos[0])

            elif state == CHARACTERS:
                for i, (rect, name) in enumerate(character_boxes):
                    if rect.collidepoint(event.pos):
                        action = "return" if i == RETURN_INDEX else "select"
                        start_card_press(i, action)

            elif state == CHAPTERS:
                if pressed_chapter_target is not None:
                    pass
                elif CHAPTER_BACK_RECT.collidepoint(event.pos):
                    start_chapter_press(("back",), go_back_to_menu)
                else:
                    for i, (rect, name) in enumerate(chapter_boxes):
                        if rect.collidepoint(event.pos):
                            if is_chapter_locked(i):
                                print(f"[chapters] {name} is locked - finish earlier chapters first")
                            else:
                                start_chapter_press(("card", i), lambda n=name: select_chapter(n))
                            break

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if dragging_slider is not None:
                saveSettings()          # a slider was just let go: remember it
            dragging_slider = None

        elif event.type == pygame.MOUSEMOTION and dragging_slider:
            set_slider_from_mouse(dragging_slider, event.pos[0])

    # ---------- Advance menu button animation ----------
    if pressed_index is not None:
        press_frame += 1
        if press_phase == "down" and press_frame >= PRESS_FRAMES:
            press_phase = "up"
            press_frame = 0
        elif press_phase == "up" and press_frame >= PRESS_FRAMES:
            pressed_index = None
            press_phase = None
            if pending_callback is not None:
                pending_callback()
                pending_callback = None

    # ---------- Advance settings back-button animation ----------
    if back_pressed:
        back_press_frame += 1
        if back_press_phase == "down" and back_press_frame >= PRESS_FRAMES:
            back_press_phase = "up"
            back_press_frame = 0
        elif back_press_phase == "up" and back_press_frame >= PRESS_FRAMES:
            back_pressed = False
            back_press_phase = None
            if back_pending:
                state = MENU
                back_pending = False

    # ---------- Advance character-card animation ----------
    if pressed_card is not None:
        card_press_frame += 1
        if card_press_phase == "down" and card_press_frame >= PRESS_FRAMES:
            card_press_phase = "up"
            card_press_frame = 0
        elif card_press_phase == "up" and card_press_frame >= PRESS_FRAMES:
            if card_pending_action == "return":
                state = MENU
            elif card_pending_action == "select":
                selected_character = character_boxes[pressed_card][1]
                state = DETAIL
            pressed_card = None
            card_press_phase = None
            card_pending_action = None

    # ---------- Advance chapter-card / chapter-back animation ----------
    if pressed_chapter_target is not None:
        chapter_press_frame += 1
        if chapter_press_phase == "down" and chapter_press_frame >= PRESS_FRAMES:
            chapter_press_phase = "up"
            chapter_press_frame = 0
        elif chapter_press_phase == "up" and chapter_press_frame >= PRESS_FRAMES:
            pressed_chapter_target = None
            chapter_press_phase = None
            if chapter_pending_action is not None:
                chapter_pending_action()
                chapter_pending_action = None

    # ---------- Autosave ----------
    now = pygame.time.get_ticks()
    if now - last_autosave_time >= AUTOSAVE_INTERVAL_MS:
        save_game(silent=True)
        last_autosave_time = now
        autosave_notice_timer = 90

    if autosave_notice_timer > 0:
        autosave_notice_timer -= 1

    # ---------- Draw ----------
    if state == MENU:
        screen.blit(ui_image, (0, 0))
        for i, (rect, _) in enumerate(buttons):
            if i == pressed_index:
                scale = get_scale(press_phase, press_frame)
                new_w = max(1, int(rect.width * scale))
                new_h = max(1, int(rect.height * scale))
                button_slice = ui_image.subsurface(rect).copy()
                squished = pygame.transform.smoothscale(button_slice, (new_w, new_h))
                dest = squished.get_rect(center=rect.center)
                screen.blit(squished, dest)

    elif state == SETTINGS:
        screen.blit(settings_image, (0, 0))
        for name in slider_order:
            draw_slider(sliders[name], volume_settings[name])

        if back_pressed:
            scale = get_scale(back_press_phase, back_press_frame)
            new_w = max(1, int(settings_back_rect.width * scale))
            new_h = max(1, int(settings_back_rect.height * scale))
            back_slice = settings_image.subsurface(settings_back_rect).copy()
            squished = pygame.transform.smoothscale(back_slice, (new_w, new_h))
            dest = squished.get_rect(center=settings_back_rect.center)
            screen.blit(squished, dest)

    elif state == CHARACTERS:
        screen.blit(characters_bg_image, (0, 0))
        hovered_name = None
        for i, (rect, name) in enumerate(character_boxes):
            hovered = rect.collidepoint(mouse_pos)
            if hovered and name != "< Return":
                hovered_name = name
            draw_character_box(i, rect, name, hovered)
        if hovered_name:
            draw_preview_panel(hovered_name)

    elif state == DETAIL:
        draw_detail_screen()

    elif state == CHAPTERS:
        draw_chapters_screen(mouse_pos)

    # ---------- Autosave notice (drawn over whichever screen is active) ----------
    if autosave_notice_timer > 0:
        notice = font_notice.render("Autosaved", True, WHITE)
        bg_rect = notice.get_rect(bottomright=(WIDTH - 20, HEIGHT - 20)).inflate(24, 14)
        overlay = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, bg_rect.topleft)
        screen.blit(notice, notice.get_rect(bottomright=(WIDTH - 20, HEIGHT - 20)))

    pygame.display.flip()
    clock.tick(FPS)

save_game(silent=True)
saveSettings()
pygame.quit()
sys.exit()