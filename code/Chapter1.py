import pygame
import sys
import random
import os

_CLICK_SOUND = None


def play_click_sound():
    """Play the UI click sound if assets/sounds/click.mp3 exists."""
    global _CLICK_SOUND

    if _CLICK_SOUND is None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            sound_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets", "sounds", "click.mp3"
            )

            _CLICK_SOUND = pygame.mixer.Sound(sound_path)
            _CLICK_SOUND.set_volume(0.45)

        except (pygame.error, OSError):
            return

    try:
        _CLICK_SOUND.play()
    except pygame.error:
        pass


from chapter1_function import (
    load_images,
    draw_dialogue,
    draw_swoosh_background,
    draw_picture3_shake,
    draw_kanto_kombat,
    draw_picture7_shock,
    draw_picture9_shake,
    draw_picture9_fade_out,
    draw_skip_button,
    load_background,
)

from scenes import run_scene


SCREEN_WIDTH = 1284  # window width in pixels
SCREEN_HEIGHT = 702  # window height in pixels


# ============================================================
# CUTSCENE 2: BACKGROUNDS 10–16
# ============================================================

def run_cutscene2(screen, clock):
    """Play the second part of Chapter 1 (backgrounds 10–16)."""

    backgrounds = [
        load_background(
            f"assets/scenes/background{i}.png",
            SCREEN_WIDTH,
            SCREEN_HEIGHT
        )
        for i in range(10, 17)
    ]

    dialogues = {
        2: [
            "Uyyyy, hanep iniiwasan kita ehh, sayang makukuha kona sana sapatos mo ulit"
        ],
        3: [
            "SABI KO NA EH, kaya ako nag iintay dine TAGAL MO ERP akin na sapatos ko"
        ],
        5: [
            "HUHHH?, sino yun?"
        ],
    }

    current_bg = 0
    current_dialogue = 0
    shake_timer = 0
    shake_duration = 250

    running = True
    fading_out = False
    fade_alpha = 0
    fade_speed = 300

    def advance_cutscene():
        nonlocal current_bg, current_dialogue
        nonlocal shake_timer, fading_out

        if current_bg == len(backgrounds) - 1:
            fading_out = True
            return

        if current_bg in dialogues:
            current_dialogue += 1

            if current_dialogue < len(dialogues[current_bg]):
                return

        if current_bg < len(backgrounds) - 1:
            current_bg += 1
            current_dialogue = 0

            if current_bg in (2, 3):
                shake_timer = shake_duration

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if not fading_out:
                if (
                    event.type == pygame.KEYDOWN
                    and event.key in (pygame.K_RETURN, pygame.K_SPACE)
                ):
                    play_click_sound()
                    advance_cutscene()

                elif (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                ):
                    play_click_sound()
                    advance_cutscene()

        if shake_timer > 0:
            shake_x = random.randint(-10, 10)
            shake_y = random.randint(-6, 6)
            shake_timer = max(
                0,
                shake_timer - clock.get_time()
            )
        else:
            shake_x = shake_y = 0

        screen.blit(
            backgrounds[current_bg],
            (shake_x, shake_y)
        )

        if current_bg in dialogues:
            draw_dialogue(
                screen,
                dialogues[current_bg][current_dialogue]
            )

        if fading_out:
            fade_alpha = min(
                255,
                fade_alpha + fade_speed * dt
            )

            fade_surface = pygame.Surface(
                (SCREEN_WIDTH, SCREEN_HEIGHT)
            )
            fade_surface.fill((0, 0, 0))
            fade_surface.set_alpha(int(fade_alpha))

            screen.blit(fade_surface, (0, 0))

            if fade_alpha >= 255:
                running = False

        pygame.display.flip()

    return True


# ============================================================
# CUTSCENE 3 SETTINGS
# ============================================================

CUTSCENE3_FIRST_BACKGROUND = 20  # first picture number of cutscene 3 (assets/scenes/background<N>.png)
CUTSCENE3_LAST_BACKGROUND = 23  # last picture number of cutscene 3 (shown after the first one, in order)


# ============================================================
# CUTSCENE 3: BACKGROUNDS 20–23
# ============================================================

def run_cutscene3(screen, clock):
    """
    Display backgrounds 20–23 first.
    Afterward, start the separate dialogue scene (part 6)
    using the existing character and dialogue system in scenes.py.
    """

    backgrounds = []

    for number in range(
        CUTSCENE3_FIRST_BACKGROUND,
        CUTSCENE3_LAST_BACKGROUND + 1
    ):
        path = f"assets/scenes/background{number}.png"

        try:
            backgrounds.append(
                load_background(
                    path,
                    SCREEN_WIDTH,
                    SCREEN_HEIGHT
                )
            )

        except (pygame.error, OSError, FileNotFoundError) as error:
            print(
                f"Could not load Cutscene 3 background: {path}\n"
                f"{error}"
            )
            return False

    if not backgrounds:
        print("Cutscene 3 has no backgrounds configured.")
        return False

    # --------------------------------------------------------
    # PHASE 1: SHOW BACKGROUNDS 20–23
    # --------------------------------------------------------

    current_bg = 0

    while current_bg < len(backgrounds):
        clock.tick(60)

        advance_background = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif (
                event.type == pygame.KEYDOWN
                and event.key in (
                    pygame.K_RETURN,
                    pygame.K_SPACE
                )
            ):
                play_click_sound()
                advance_background = True
                break

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                play_click_sound()
                advance_background = True
                break

        if advance_background:
            current_bg += 1

        if current_bg < len(backgrounds):
            screen.blit(
                backgrounds[current_bg],
                (0, 0)
            )
            pygame.display.flip()

    # --------------------------------------------------------
    # PHASE 2: START THE NEW DIALOGUE SCENE
    # --------------------------------------------------------
    # Part 6 uses BG20_DIALOGUES from dialogues.py.
    # It uses the character sprites, speaker zoom, transitions,
    # and dialogue box from scenes.py.

    run_scene(screen, clock, part=6)

    return True


# ============================================================
# MAIN CHAPTER 1
# ============================================================

def run_chapter1(screen=None, clock=None):
    """
    Play the intro, existing scenes and then Cutscene 3.
    """

    pygame.init()

    if screen is None:
        screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )

    if clock is None:
        clock = pygame.time.Clock()

    pygame.display.set_caption("Kanto Kombat")

    images = load_images()

    backgrounds = [
        images[f"background{i}"]
        for i in range(1, 10)
    ]

    kanto_kombat = images["kanto_kombat"]

    dialogues_picture2 = [
        "AHh pota asan sapatos ko?",
        "Taena dito lang yun eh",
        "Naiwan ko ba kila Sandugo?",
        "sige puta takbuhin ko baka asa knila nga",
    ]

    dialogues_picture3 = [
        "Ay puta, baka nandito lang pala.",
        "Sandali, saan ko nga ba huling nakita?",
        "Ahh oo! Naalala ko na.",
    ]

    dialogues_picture6 = [
        "Hanep naiwan ko ata nakasaksak yung plantsa",
        "hahh, maaamoy na ni lola yun",
    ]

    dialogues_picture9 = [
        "SABI KO NAAA"
    ]

    # --------------------------------------------------------
    # INTRO STATES
    # --------------------------------------------------------

    intro_state = 0
    current_dialogue = 0

    now = pygame.time.get_ticks()

    shake_start_time = now
    swoosh_start_time = now
    logo_start_time = now
    shock_start_time = now
    picture9_shake_start_time = now
    picture9_fade_start_time = now

    running = True
    intro_finished = False

    skip_button = pygame.Rect(
        SCREEN_WIDTH - 150,
        20,
        120,
        45
    )

    # --------------------------------------------------------
    # ADVANCE INTRO
    # --------------------------------------------------------

    def advance_intro():
        nonlocal intro_state, current_dialogue
        nonlocal shake_start_time, swoosh_start_time
        nonlocal logo_start_time, shock_start_time
        nonlocal picture9_shake_start_time
        nonlocal picture9_fade_start_time

        if intro_state == 0:
            intro_state = 1
            current_dialogue = 0

        elif intro_state == 1:
            current_dialogue += 1

            if current_dialogue >= len(dialogues_picture2):
                intro_state = 2
                shake_start_time = pygame.time.get_ticks()

        elif intro_state == 2:
            intro_state = 3
            current_dialogue = 0

        elif intro_state == 3:
            current_dialogue += 1

            if current_dialogue >= len(dialogues_picture3):
                intro_state = 4
                swoosh_start_time = pygame.time.get_ticks()

        elif intro_state == 4:
            intro_state = 5
            logo_start_time = pygame.time.get_ticks()

        elif intro_state == 5:
            # The logo advances automatically.
            pass

        elif intro_state == 6:
            intro_state = 7
            swoosh_start_time = pygame.time.get_ticks()

        elif intro_state == 7:
            intro_state = 8
            current_dialogue = 0

        elif intro_state == 8:
            current_dialogue += 1

            if current_dialogue >= len(dialogues_picture6):
                intro_state = 9
                shock_start_time = pygame.time.get_ticks()

        elif intro_state == 9:
            intro_state = 10

        elif intro_state == 10:
            intro_state = 11
            current_dialogue = 0

            picture9_shake_start_time = pygame.time.get_ticks()

        elif intro_state == 11:
            current_dialogue += 1

            if current_dialogue >= len(dialogues_picture9):
                intro_state = 12
                picture9_fade_start_time = pygame.time.get_ticks()

    # --------------------------------------------------------
    # INTRO LOOP
    # --------------------------------------------------------

    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False
                intro_finished = False

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                play_click_sound()

                if skip_button.collidepoint(event.pos):
                    running = False
                    intro_finished = True
                else:
                    advance_intro()

            elif (
                event.type == pygame.KEYDOWN
                and event.key in (
                    pygame.K_RETURN,
                    pygame.K_SPACE
                )
            ):
                play_click_sound()
                advance_intro()

        if not running:
            break

        # ----------------------------------------------------
        # DRAW INTRO STATES
        # ----------------------------------------------------

        if intro_state == 0:
            screen.blit(backgrounds[0], (0, 0))

        elif intro_state == 1:
            screen.blit(backgrounds[1], (0, 0))
            draw_dialogue(
                screen,
                dialogues_picture2[current_dialogue]
            )

        elif intro_state == 2:
            draw_picture3_shake(
                screen,
                backgrounds[2],
                shake_start_time
            )

        elif intro_state == 3:
            screen.blit(backgrounds[2], (0, 0))
            draw_dialogue(
                screen,
                dialogues_picture3[current_dialogue]
            )

        elif intro_state == 4:
            draw_swoosh_background(
                screen,
                backgrounds[3],
                swoosh_start_time,
                250
            )

        elif intro_state == 5:
            draw_kanto_kombat(
                screen,
                kanto_kombat,
                logo_start_time
            )

            if (
                pygame.time.get_ticks() - logo_start_time
                >= 1800
            ):
                intro_state = 6
                swoosh_start_time = pygame.time.get_ticks()

        elif intro_state == 6:
            draw_swoosh_background(
                screen,
                backgrounds[4],
                swoosh_start_time,
                250
            )

        elif intro_state == 7:
            draw_swoosh_background(
                screen,
                backgrounds[5],
                swoosh_start_time,
                250
            )

        elif intro_state == 8:
            screen.blit(backgrounds[5], (0, 0))
            draw_dialogue(
                screen,
                dialogues_picture6[current_dialogue]
            )

        elif intro_state == 9:
            draw_picture7_shock(
                screen,
                backgrounds[6],
                shock_start_time
            )

        elif intro_state == 10:
            screen.blit(backgrounds[7], (0, 0))

        elif intro_state == 11:
            draw_picture9_shake(
                screen,
                backgrounds[8],
                picture9_shake_start_time
            )

            draw_dialogue(
                screen,
                dialogues_picture9[current_dialogue]
            )

        elif intro_state == 12:
            draw_picture9_fade_out(
                screen,
                backgrounds[8],
                picture9_fade_start_time,
                1000
            )

            if (
                pygame.time.get_ticks()
                - picture9_fade_start_time >= 1000
            ):
                running = False
                intro_finished = True

        if running:
            draw_skip_button(screen, skip_button)

        pygame.display.flip()
        clock.tick(60)

    # --------------------------------------------------------
    # RUN THE EXISTING SCENES, THEN CUTSCENE 3
    # --------------------------------------------------------

    if intro_finished:

        # Existing scene sequence:
        # dialogue parts 1–5, including backgrounds 17–19.
        scene_result = run_scene(screen, clock)

        if scene_result is False:
            return False

        # New Cutscene 3:
        # backgrounds 20–23, followed by dialogue part 6.
        cutscene3_result = run_cutscene3(screen, clock)

        if cutscene3_result is False:
            return False

        return True

    return False


# ============================================================
# RUN CHAPTER 1
# ============================================================

if __name__ == "__main__":
    result = run_chapter1()
    pygame.quit()
    sys.exit(0 if result is not False else 1)