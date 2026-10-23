import pygame
import sys
import stages
import campaign
import saves

pygame.init()

WIDTH, HEIGHT = 1284, 702  # window size in pixels
FPS = 60  # frames per second the screen is capped at

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Kanto Kombat - Select Chapter")
clock = pygame.time.Clock()

WHITE = (255, 255, 255)

# ---------- Background art ----------
chapter_bg_image = pygame.image.load('assets/img/chapter.png').convert()
chapter_bg_image = pygame.transform.smoothscale(chapter_bg_image, (WIDTH, HEIGHT))

# ---------- Layout ----------
BACK_RECT = pygame.Rect(80, 45, 140, 35)  # (x, y, width, height) of the < BACK button

# (x, y, width, height) click box of each chapter card, left to right
CARD_GRID = [
    (46, 220, 265, 350),
    (361, 220, 255, 350),
    (667, 220, 255, 350),
    (971, 220, 265, 350)
]

CHAPTER_NAMES = ["Barangay", "City", "Province", "Country"]  # chapter shown on each card, left to right

chapter_boxes = [
    (pygame.Rect(*CARD_GRID[i]), name) for i, name in enumerate(CHAPTER_NAMES)
]

DEBUG_SHOW_HITBOXES = False  # True = draw red outlines around clickable areas

CHAPTER_ORDER = ["Barangay", "City", "Province", "Country"]  # story / unlock order: a chapter unlocks when all earlier ones are finished


SHADOW_ALPHA = 230          # 0 = invisible, 255 = fully black
LOCK_FONT = pygame.font.SysFont("arialblack", 22)
BACK_FONT = pygame.font.SysFont("arialblack", 20)


def is_chapter_locked(index):
    name = CHAPTER_NAMES[index]
    story_index = CHAPTER_ORDER.index(name)
    if story_index == 0:
        return False
    return not all(stages.isChapterCompleted(earlierChapterName) for earlierChapterName in CHAPTER_ORDER[:story_index])


def draw_lock_label(rect):
    label = LOCK_FONT.render("LOCKED", True, WHITE)
    screen.blit(label, label.get_rect(center=rect.center))


# ---------- Press animation (same squish pattern as your other buttons) ----------
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


# which element is currently being pressed: ("back",) or ("card", index)
pressed_target = None
press_frame = 0
press_phase = None
running = True  # read/written by select_chapter
pending_action = None


def start_press(target, action):
    global pressed_target, press_frame, press_phase, pending_action
    pressed_target = target
    press_frame = 0
    press_phase = "down"
    pending_action = action


# ---------- Callbacks: wire these up to your real navigation ----------
def go_back():
    # Standalone: leave the screen. (start.py has its own go_back_to_menu for the real flow.)
    global running
    running = False


def select_chapter(name):
    global running
    result = campaign.playChapter(screen, name, background=chapter_bg_image,
                                  onProgress=lambda: saves.writeSlot(1))   # standalone test: no save_game here, use slot 1
    if result in ("quit", "menu"):
        running = False


# ---------- Drawing ----------
def draw_back_button(mouse_pos):
    scale = 1.0
    if pressed_target == ("back",):
        scale = get_scale(press_phase, press_frame)

    draw_rect = pygame.Rect(0, 0, max(1, int(BACK_RECT.width * scale)), max(1, int(BACK_RECT.height * scale)))
    draw_rect.center = BACK_RECT.center

    hovered = BACK_RECT.collidepoint(mouse_pos)
    pygame.draw.rect(screen, (85, 74, 62) if hovered else (55, 48, 42), draw_rect, border_radius=8)
    pygame.draw.rect(screen, (255, 170, 40) if hovered else (120, 105, 90), draw_rect, width=3, border_radius=8)
    label = BACK_FONT.render("< BACK", True, WHITE)
    screen.blit(label, label.get_rect(center=draw_rect.center))

    if DEBUG_SHOW_HITBOXES:
        pygame.draw.rect(screen, (255, 0, 0), BACK_RECT, width=1)


def draw_chapter_card(index, rect, name, mouse_pos):
    locked = is_chapter_locked(index)

    scale = 1.0
    if not locked and pressed_target == ("card", index):
        scale = get_scale(press_phase, press_frame)

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
        shadow.fill((0, 0, 0, SHADOW_ALPHA))
        screen.blit(shadow, rect.topleft)
        draw_lock_label(rect)

    if DEBUG_SHOW_HITBOXES:
        pygame.draw.rect(screen, (255, 0, 0), rect, width=1)


def draw_chapters_screen(mouse_pos):
    screen.blit(chapter_bg_image, (0, 0))
    for i, (rect, name) in enumerate(chapter_boxes):
        draw_chapter_card(i, rect, name, mouse_pos)
    draw_back_button(mouse_pos)


# ---------- Input handling ----------
def handle_chapters_event(event):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if pressed_target is not None:
            return
        if BACK_RECT.collidepoint(event.pos):
            start_press(("back",), go_back)
            return
        for i, (rect, name) in enumerate(chapter_boxes):
            if rect.collidepoint(event.pos):
                if is_chapter_locked(i):
                    print(f"[chapters] {name} is locked - finish earlier chapters first")
                    return
                start_press(("card", i), lambda chapterName=name: select_chapter(chapterName))
                return
    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        if pressed_target is None:
            go_back()


def advance_chapters_animation():
    global pressed_target, press_frame, press_phase, pending_action
    if pressed_target is None:
        return
    press_frame += 1
    if press_phase == "down" and press_frame >= PRESS_FRAMES:
        press_phase = "up"
        press_frame = 0
    elif press_phase == "up" and press_frame >= PRESS_FRAMES:
        pressed_target = None
        press_phase = None
        if pending_action is not None:
            pending_action()
            pending_action = None


# ---------- Standalone run loop (for testing this screen on its own) ----------
if __name__ == "__main__":
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                handle_chapters_event(event)

        advance_chapters_animation()

        draw_chapters_screen(mouse_pos)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()