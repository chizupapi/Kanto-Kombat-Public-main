import math
import os
import pygame

from scenes_function import (
    load_character,
    update_dialogue,
    draw_dialogue,
    draw_character,
)

from dialogues import (
    DIALOGUES,
    BG17_DIALOGUES,
    BG18_DIALOGUES,
)

try:
    from dialogues import BG19_DIALOGUES
except ImportError:
    BG19_DIALOGUES = [
        {"name": "Darit", "text": "Oyy Sandugo, anong nangyari?"},
        {"name": "Sandugo", "text": "Mahaba-habang kuwento ito."},
        {"name": "Darit", "text": "Sige, makikinig ako."},
    ]

try:
    from dialogues import BG20_DIALOGUES
except ImportError:
    BG20_DIALOGUES = [
        {"name": "Darit", "text": "Uy, Sandugo, may sasabihin sana ako."},
        {"name": "Sandugo", "text": "Ano naman iyon?"},
        {"name": "Darit", "text": "Teka lang, makinig ka muna."},
    ]


# ============================================================
# SETTINGS
# ============================================================

SCREEN_WIDTH = 1284  # window width in pixels (matches the game window)
SCREEN_HEIGHT = 702  # window height in pixels

CHAR_WIDTH = 500  # width in pixels each dialogue character picture is drawn at
CHAR_HEIGHT = 600  # height in pixels each dialogue character picture is drawn at

CONTINUATION_START = 8  # index in DIALOGUES where part 2 starts (the first 8 lines are part 1)

BLACK = (0, 0, 0)

SLIDE_DURATION = 0.30  # seconds a character takes to slide in
SLIDE_DISTANCE = 650  # pixels a character travels while sliding in
FADE_SPEED = 5  # fade-to-black speed: alpha (0-255) added every frame

BG17_PATH = "assets/scenes/background17.png"  # background image for part 3
BG18_PATH = "assets/scenes/background18.png"  # background image for part 4
BG19_PATH = "assets/scenes/background19.png"  # background image for part 5

SPEAKING_SCALE = 1.08  # how much bigger the current speaker is drawn (1.08 = 8% bigger)
ZOOM_SMOOTHNESS = 8.0  # how fast the speaker zoom eases in and out (higher = snappier)

# Outfit changes begin at Part 5 (BG19 / sink scene).
OUTFIT_CHANGE_PART = 5  # first part number that uses the new outfits

_CLICK_SOUND = None


# ============================================================
# SOUND
# ============================================================

def play_click_sound():
    global _CLICK_SOUND

    if _CLICK_SOUND is None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            sound_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets",
                "sounds",
                "click.wav",
            )

            _CLICK_SOUND = pygame.mixer.Sound(sound_path)
            _CLICK_SOUND.set_volume(0.45)

        except (pygame.error, OSError):
            return

    try:
        _CLICK_SOUND.play()
    except pygame.error:
        pass


# ============================================================
# COMMON IMAGE LOADER
# ============================================================

def load_scene_image(path):
    full_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        path,
    )

    image = pygame.image.load(full_path).convert()

    return pygame.transform.scale(
        image,
        (SCREEN_WIDTH, SCREEN_HEIGHT),
    )


# ============================================================
# NEW OUTFIT LOADER
# ============================================================

def load_new_outfit(image_path, original_character, char_info):
    """
    Load a separate holder for the new outfit.

    If a matching *_dark.png image exists, load it.
    Otherwise, use the new outfit image for both states.

    If the new outfit image is missing, retain the original holder.
    """

    base_dir = os.path.dirname(os.path.abspath(__file__))

    full_image_path = os.path.join(base_dir, image_path)

    dark_image_path = (
        os.path.splitext(image_path)[0] + "_dark.png"
    )

    full_dark_path = os.path.join(
        base_dir,
        dark_image_path,
    )

    if not os.path.isfile(full_image_path):
        print(
            f"Warning: New outfit not found: {image_path}. "
            "Using the original outfit."
        )
        return original_character

    # Use a separate dark image if one exists.
    if os.path.isfile(full_dark_path):
        try:
            return load_character(
                image_path,
                dark_image_path,
                CHAR_WIDTH,
                CHAR_HEIGHT,
                char_info["flip"],
            )
        except (pygame.error, OSError, FileNotFoundError):
            pass

    # Avoid mixing the original outfit into the new outfit holder.
    try:
        return load_character(
            image_path,
            image_path,
            CHAR_WIDTH,
            CHAR_HEIGHT,
            char_info["flip"],
        )

    except (pygame.error, OSError, FileNotFoundError) as error:
        print(
            f"Warning: Could not load {image_path}: {error}"
        )
        return original_character


# ============================================================
# FADE TRANSITION FOR BG17 AND BG18
# ============================================================

def show_fade_background(window, clock, image_path):
    image = load_scene_image(image_path)

    fade_surface = pygame.Surface(
        (SCREEN_WIDTH, SCREEN_HEIGHT)
    )
    fade_surface.fill(BLACK)

    alpha = 255

    while alpha > 0:
        dt = clock.tick(60) / 1000.0
        alpha = max(0, alpha - 300 * dt)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

        window.blit(image, (0, 0))
        fade_surface.set_alpha(int(alpha))
        window.blit(fade_surface, (0, 0))
        pygame.display.flip()

    waiting = True

    while waiting:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    play_click_sound()
                    waiting = False

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                play_click_sound()
                waiting = False

        window.blit(image, (0, 0))
        pygame.display.flip()

    alpha = 0

    while alpha < 255:
        dt = clock.tick(60) / 1000.0
        alpha = min(255, alpha + 300 * dt)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

        window.blit(image, (0, 0))
        fade_surface.set_alpha(int(alpha))
        window.blit(fade_surface, (0, 0))
        pygame.display.flip()

    return True


def show_background17(window, clock):
    return show_fade_background(window, clock, BG17_PATH)


def show_background18(window, clock):
    return show_fade_background(window, clock, BG18_PATH)


# ============================================================
# BACKGROUND 19 - ZOOM IN, THEN ZOOM OUT
# ============================================================

def show_background19(window, clock):
    image = load_scene_image(BG19_PATH)

    start_scale = 0.15
    end_scale = 1.0

    zoom_duration = 1.0
    hold_duration = 0.25
    zoom_out_duration = 0.8

    elapsed = 0.0
    phase = "in"

    fade_surface = pygame.Surface(
        (SCREEN_WIDTH, SCREEN_HEIGHT)
    )
    fade_surface.fill(BLACK)

    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

        elapsed += dt

        if phase == "in":
            progress = min(1.0, elapsed / zoom_duration)
            eased = progress * progress * (3 - 2 * progress)

            scale = start_scale + (
                end_scale - start_scale
            ) * eased

            if progress >= 1.0:
                phase = "hold"
                elapsed = 0.0

        elif phase == "hold":
            scale = end_scale

            if elapsed >= hold_duration:
                phase = "out"
                elapsed = 0.0

        else:
            progress = min(1.0, elapsed / zoom_out_duration)
            eased = progress * progress * (3 - 2 * progress)

            scale = end_scale + (
                start_scale - end_scale
            ) * eased

            if progress >= 1.0:
                running = False

        scaled_width = max(1, int(SCREEN_WIDTH * scale))
        scaled_height = max(1, int(SCREEN_HEIGHT * scale))

        scaled_image = pygame.transform.smoothscale(
            image,
            (scaled_width, scaled_height),
        )

        window.fill(BLACK)

        image_x = (SCREEN_WIDTH - scaled_width) // 2
        image_y = (SCREEN_HEIGHT - scaled_height) // 2

        window.blit(scaled_image, (image_x, image_y))
        pygame.display.flip()

    alpha = 0

    while alpha < 255:
        dt = clock.tick(60) / 1000.0
        alpha = min(255, alpha + 400 * dt)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

        window.fill(BLACK)
        fade_surface.set_alpha(int(alpha))
        window.blit(fade_surface, (0, 0))
        pygame.display.flip()

    return True


# ============================================================
# MAIN DIALOGUE SCENE
# ============================================================

def run_scene(window, clock, part=1):

    # --------------------------------------------------------
    # CHARACTER DEFINITIONS
    # --------------------------------------------------------

    CHARACTERS = {
        "Darit": {
            "image": "assets/scenes/dialog/player/daritph.png",
            "dark": "assets/scenes/dialog/player/daritph_dark.png",
            "new_image": "assets/scenes/dialog/player/daritph_new.png",
            "side": "left",
            "x": 100,
            "y": SCREEN_HEIGHT - CHAR_HEIGHT + 50,
            "flip": False,
        },

        "Sandugo": {
            "image": "assets/scenes/dialog/player/sandugoph.png",
            "dark": "assets/scenes/dialog/player/sandugoph_dark.png",
            "new_image": "assets/scenes/dialog/player/sandugoph_new.png",
            "side": "right",
            "x": SCREEN_WIDTH - CHAR_WIDTH - 100,
            "y": SCREEN_HEIGHT - CHAR_HEIGHT + 20,
            "flip": True,
        },

        "Otab": {
            "image": "assets/scenes/dialog/player/otabph.png",
            "dark": "assets/scenes/dialog/player/otabph_dark.png",
            "new_image": "assets/scenes/dialog/player/otabph_new.png",
            "side": "left",
            "x": 100,
            "y": SCREEN_HEIGHT - CHAR_HEIGHT + 50,
            "flip": False,
        },
    }

    RIGHT_POSITION = {
        "x": SCREEN_WIDTH - CHAR_WIDTH - 100,
        "y": SCREEN_HEIGHT - CHAR_HEIGHT + 20,
    }

    # --------------------------------------------------------
    # LOAD ORIGINAL OUTFITS
    # --------------------------------------------------------

    original_characters = {}

    for name, info in CHARACTERS.items():
        original_characters[name] = load_character(
            info["image"],
            info["dark"],
            CHAR_WIDTH,
            CHAR_HEIGHT,
            info["flip"],
        )

    # --------------------------------------------------------
    # LOAD NEW OUTFITS INTO SEPARATE HOLDERS
    # --------------------------------------------------------

    new_outfit_characters = {}

    for name, info in CHARACTERS.items():
        new_outfit_characters[name] = load_new_outfit(
            info["new_image"],
            original_characters[name],
            info,
        )

    # --------------------------------------------------------
    # RIGHT-FACING OTAB HOLDERS
    # --------------------------------------------------------

    def make_otab_right(holder):
        return {
            "image": pygame.transform.flip(
                holder["image"], True, False
            ),
            "dark": pygame.transform.flip(
                holder["dark"], True, False
            ),
            "size": holder["size"],
        }

    original_characters["OtabRight"] = make_otab_right(
        original_characters["Otab"]
    )

    new_outfit_characters["OtabRight"] = make_otab_right(
        new_outfit_characters["Otab"]
    )

    # --------------------------------------------------------
    # DIALOGUE BACKGROUNDS
    # --------------------------------------------------------

    dialogue_backgrounds = {
        1: "assets/scenes/dialog/dialogbg1.png",
        2: "assets/scenes/dialog/dialogbg2.png",
        3: "assets/scenes/dialog/dialogbg3.png",
        4: "assets/scenes/dialog/dialogbg4.png",
        5: "assets/scenes/dialog/dialogbg5.png",
        6: "assets/scenes/dialog/dialogbg5.png",
    }

    if part not in dialogue_backgrounds:
        return

    background_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        dialogue_backgrounds[part],
    )

    background = pygame.image.load(background_path).convert()
    background = pygame.transform.scale(
        background,
        (SCREEN_WIDTH, SCREEN_HEIGHT),
    )

    font = pygame.font.Font(None, 32)
    small_font = pygame.font.Font(None, 30)

    # --------------------------------------------------------
    # SELECT DIALOGUES
    # --------------------------------------------------------

    if part == 1:
        dialogues = DIALOGUES[:CONTINUATION_START]

    elif part == 2:
        dialogues = DIALOGUES[CONTINUATION_START:]

    elif part == 3:
        dialogues = BG17_DIALOGUES

    elif part == 4:
        dialogues = BG18_DIALOGUES

    elif part == 5:
        dialogues = BG19_DIALOGUES

    elif part == 6:
        dialogues = BG20_DIALOGUES

    else:
        return

    if not dialogues:
        return

    dialogue_index = 0

    dialogue_name, dialogue_side, dialogue_text = update_dialogue(
        dialogues,
        CHARACTERS,
        dialogue_index,
    )

    # --------------------------------------------------------
    # CHARACTER SLOTS
    # --------------------------------------------------------

    if part in (4, 5):
        slots = {
            "left": "Darit",
            "right": None,
        }
        otab_moved_right = False

    elif part == 6:
        slots = {
            "left": "Darit",
            "right": "Sandugo",
        }
        otab_moved_right = False

    elif part == 3:
        slots = {
            "left": "Darit",
            "right": "OtabRight",
        }
        otab_moved_right = True

    else:
        slots = {
            "left": "Darit",
            "right": "Sandugo",
        }
        otab_moved_right = False

    transition = None

    current_scales = {
        name: 1.0 for name in original_characters
    }

    fade_alpha = 0
    fading_out = False

    # --------------------------------------------------------
    # CONSISTENT OUTFIT SELECTION
    # --------------------------------------------------------

    def get_character_holder(character_name):
        """
        Always select the same outfit for a character throughout
        the current part, including both phases of a slide.

        Parts 1-4 use original outfits.
        Part 5 onward uses new outfit holders.

        This function does not change slots, reload images, or
        draw additional characters.
        """

        if part >= OUTFIT_CHANGE_PART:
            return new_outfit_characters[character_name]

        return original_characters[character_name]

    # --------------------------------------------------------
    # CHARACTER HELPERS
    # --------------------------------------------------------

    def get_character_info(character_name):
        if character_name == "OtabRight":
            return RIGHT_POSITION

        return CHARACTERS[character_name]

    def get_scale(character_name):
        return current_scales.get(character_name, 1.0)

    def is_speaking(character_name):
        if character_name == "OtabRight":
            return dialogue_name == "Otab"

        return character_name == dialogue_name

    # --------------------------------------------------------
    # CHARACTER SLIDE TRANSITION
    # --------------------------------------------------------

    def start_transition(side, new_character):
        nonlocal transition

        old_character = slots[side]

        if old_character == new_character:
            return

        direction = -1 if side == "left" else 1

        transition = {
            "side": side,
            "old": old_character,
            "new": new_character,
            "phase": "out",
            "elapsed": 0.0,
            "duration": SLIDE_DURATION,
            "direction": direction,
        }

    # --------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------

    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                return False

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False

                if (
                    event.key in (pygame.K_RETURN, pygame.K_SPACE)
                    and not fading_out
                    and transition is None
                ):
                    play_click_sound()
                    dialogue_index += 1

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and not fading_out
                and transition is None
            ):
                play_click_sound()
                dialogue_index += 1

        # ----------------------------------------------------
        # UPDATE DIALOGUE
        # ----------------------------------------------------

        if dialogue_index >= len(dialogues):
            fading_out = True

        elif not fading_out and transition is None:

            dialogue_name, dialogue_side, dialogue_text = (
                update_dialogue(
                    dialogues,
                    CHARACTERS,
                    dialogue_index,
                )
            )

            if part in (4, 5):
                dialogue_side = "left"

            elif (
                dialogue_name == "Otab"
                and dialogue_text.strip() == "Ayy hello"
            ):
                dialogue_side = "right"
                otab_moved_right = True
                start_transition("right", "OtabRight")

            elif dialogue_name in CHARACTERS:

                if dialogue_name == "Otab" and otab_moved_right:
                    desired_side = "right"
                    desired_character = "OtabRight"
                    dialogue_side = "right"

                else:
                    desired_side = CHARACTERS[dialogue_name]["side"]
                    desired_character = dialogue_name

                if part == 6:
                    if slots[desired_side] != desired_character:
                        start_transition(
                            desired_side,
                            desired_character,
                        )

                elif slots[desired_side] != desired_character:
                    start_transition(
                        desired_side,
                        desired_character,
                    )

        # ----------------------------------------------------
        # UPDATE SLIDE TRANSITION
        # ----------------------------------------------------

        if transition is not None:
            transition["elapsed"] += dt

            if transition["elapsed"] >= transition["duration"]:

                if transition["phase"] == "out":
                    transition["phase"] = "in"
                    transition["elapsed"] = 0.0

                else:
                    slots[transition["side"]] = transition["new"]
                    transition = None

        # ----------------------------------------------------
        # FADE OUT AT THE END OF EACH PART
        # ----------------------------------------------------

        if fading_out:
            fade_alpha = min(255, fade_alpha + FADE_SPEED)

            if fade_alpha >= 255:

                if part == 1:
                    from Chapter1 import run_cutscene2

                    result = run_cutscene2(window, clock)

                    if result is False:
                        return False

                    run_scene(window, clock, part=2)

                elif part == 2:
                    if not show_background17(window, clock):
                        return False

                    if BG17_DIALOGUES:
                        run_scene(window, clock, part=3)

                elif part == 3:
                    if not show_background18(window, clock):
                        return False

                    if BG18_DIALOGUES:
                        run_scene(window, clock, part=4)

                elif part == 4:
                    if not show_background19(window, clock):
                        return False

                    if BG19_DIALOGUES:
                        run_scene(window, clock, part=5)

                return True

        # ----------------------------------------------------
        # SPEAKER ZOOM
        # ----------------------------------------------------

        zoom_amount = 1.0 - math.exp(
            -ZOOM_SMOOTHNESS * dt
        )

        for character_name in current_scales:
            target_scale = (
                SPEAKING_SCALE
                if is_speaking(character_name)
                else 1.0
            )

            current_scales[character_name] += (
                target_scale - current_scales[character_name]
            ) * zoom_amount

        # ----------------------------------------------------
        # DRAW BACKGROUND
        # ----------------------------------------------------

        window.blit(background, (0, 0))

        # ----------------------------------------------------
        # DRAW CHARACTER SLOTS
        # Exactly one selected holder is drawn per slot.
        # ----------------------------------------------------

        for side in ("left", "right"):

            if (
                transition is not None
                and transition["side"] == side
            ):
                progress = min(
                    1.0,
                    transition["elapsed"] / transition["duration"],
                )

                eased = progress * progress * (3 - 2 * progress)

                old_name = transition["old"]
                new_name = transition["new"]

                if transition["phase"] == "out":

                    if old_name is not None:
                        old_info = get_character_info(old_name)

                        old_x = (
                            old_info["x"]
                            + transition["direction"]
                            * SLIDE_DISTANCE
                            * eased
                        )

                        # Use the same outfit-selection function
                        # used by normal character drawing.
                        draw_character(
                            window,
                            get_character_holder(old_name),
                            (int(old_x), old_info["y"]),
                            scale=get_scale(old_name),
                            speaking=is_speaking(old_name),
                        )

                else:

                    if new_name is not None:
                        new_info = get_character_info(new_name)

                        start_x = (
                            -CHAR_WIDTH
                            if side == "left"
                            else SCREEN_WIDTH
                        )

                        target_x = new_info["x"]

                        new_x = (
                            start_x
                            + (target_x - start_x) * eased
                        )

                        # Incoming characters use the same
                        # outfit selection as outgoing characters.
                        draw_character(
                            window,
                            get_character_holder(new_name),
                            (int(new_x), new_info["y"]),
                            scale=get_scale(new_name),
                            speaking=is_speaking(new_name),
                        )

            else:
                character_name = slots[side]

                if character_name is None:
                    continue

                info = get_character_info(character_name)

                draw_character(
                    window,
                    get_character_holder(character_name),
                    (info["x"], info["y"]),
                    scale=get_scale(character_name),
                    speaking=is_speaking(character_name),
                )

        # ----------------------------------------------------
        # DIALOGUE BOX
        # ----------------------------------------------------

        draw_dialogue(
            window,
            dialogue_name,
            dialogue_text,
            dialogue_side,
            font,
            small_font,
        )

        # ----------------------------------------------------
        # FADE OVERLAY
        # ----------------------------------------------------

        if fade_alpha > 0:
            fade_surface = pygame.Surface(
                (SCREEN_WIDTH, SCREEN_HEIGHT)
            )
            fade_surface.fill(BLACK)
            fade_surface.set_alpha(fade_alpha)
            window.blit(fade_surface, (0, 0))

        pygame.display.flip()