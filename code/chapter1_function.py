import pygame
import random

SCREEN_WIDTH = 1284
SCREEN_HEIGHT = 702
WHITE = (255, 255, 255)


def load_images():

    images = {}

    image_names = [
        "background1",
        "background2",
        "background3",
        "background4",
        "background5",
        "background6",
        "background7",
        "background8",
        "background9",
        "kanto_kombat"
    ]

    for name in image_names:

        image = pygame.image.load(
            f"assets/scenes/{name}.png"
        ).convert()

        image = pygame.transform.smoothscale(
            image,
            (
                SCREEN_WIDTH,
                SCREEN_HEIGHT
            )
        )

        images[name] = image

    return images


# ============================================================
# DIALOGUE
# ============================================================

def draw_dialogue(
    screen,
    text,
    dialogue_width=1120,
    dialogue_height=165
):

    dialogue_x = (
        SCREEN_WIDTH -
        dialogue_width
    ) // 2

    dialogue_y = 510

    dialogue_font = pygame.font.Font(
        None,
        32
    )

    dialogue_box = pygame.Surface(
        (
            dialogue_width,
            dialogue_height
        ),
        pygame.SRCALPHA
    )

    dialogue_box.fill(
        (0, 0, 0, 255)
    )

    pygame.draw.rect(
        dialogue_box,
        WHITE,
        (
            0,
            0,
            dialogue_width,
            dialogue_height
        ),
        2
    )

    screen.blit(
        dialogue_box,
        (
            dialogue_x,
            dialogue_y
        )
    )

    max_width = (
        dialogue_width -
        60
    )

    words = text.split(" ")

    lines = []

    current_line = ""

    for word in words:

        test_line = (
            current_line +
            word +
            " "
        )

        test_surface = dialogue_font.render(
            test_line,
            True,
            WHITE
        )

        if test_surface.get_width() <= max_width:

            current_line = test_line

        else:

            if current_line:

                lines.append(
                    current_line
                )

            current_line = (
                word +
                " "
            )

    if current_line:

        lines.append(
            current_line
        )

    text_x = (
        dialogue_x +
        30
    )

    text_y = (
        dialogue_y +
        30
    )

    line_spacing = 8

    for line in lines:

        text_surface = dialogue_font.render(
            line.strip(),
            True,
            WHITE
        )

        screen.blit(
            text_surface,
            (
                text_x,
                text_y
            )
        )

        text_y += (
            dialogue_font.get_height() +
            line_spacing
        )


# ============================================================
# SWOOSH BACKGROUND
# ============================================================

def draw_swoosh_background(
    screen,
    background,
    start_time,
    duration
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    if elapsed < duration:

        progress = (
            elapsed /
            duration
        )

        offset_x = int(
            -300 *
            (1 - progress)
        )

        screen.blit(
            background,
            (
                offset_x,
                0
            )
        )

        for i in range(14):

            line_y = (
                20 +
                i * 55
            )

            start_x = random.randint(
                -250,
                100
            )

            line_length = random.randint(
                150,
                400
            )

            line_width = random.randint(
                2,
                5
            )

            pygame.draw.line(
                screen,
                WHITE,
                (
                    start_x,
                    line_y
                ),
                (
                    start_x +
                    line_length,
                    line_y
                ),
                line_width
            )

    else:

        screen.blit(
            background,
            (0, 0)
        )


# ============================================================
# PICTURE 3 SHAKE
# ============================================================

def draw_picture3_shake(
    screen,
    background,
    start_time,
    duration=400,
    amount=12
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    if elapsed < duration:

        shake_x = random.randint(
            -amount,
            amount
        )

        shake_y = random.randint(
            -amount,
            amount
        )

        screen.blit(
            background,
            (
                shake_x,
                shake_y
            )
        )

    else:

        screen.blit(
            background,
            (0, 0)
        )


# ============================================================
# KANTO KOMBAT LOGO
# ============================================================

def draw_kanto_kombat(
    screen,
    image,
    start_time,
    duration=1800
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    if elapsed < duration:

        progress = (
            elapsed /
            duration
        )

        if progress < 0.5:

            zoom_progress = (
                progress /
                0.5
            )

            scale = (
                0.3 +
                zoom_progress *
                0.9
            )

        else:

            zoom_progress = (
                (progress - 0.5) /
                0.5
            )

            scale = (
                1.2 -
                zoom_progress *
                0.2
            )

        image_width = int(
            SCREEN_WIDTH *
            scale
        )

        image_height = int(
            SCREEN_HEIGHT *
            scale
        )

        scaled_image = pygame.transform.smoothscale(
            image,
            (
                image_width,
                image_height
            )
        )

        image_x = (
            SCREEN_WIDTH -
            image_width
        ) // 2

        image_y = (
            SCREEN_HEIGHT -
            image_height
        ) // 2

        screen.blit(
            scaled_image,
            (
                image_x,
                image_y
            )
        )

    else:

        screen.blit(
            image,
            (0, 0)
        )


# ============================================================
# PICTURE 7 SHOCK
# ============================================================

def draw_picture7_shock(
    screen,
    background,
    start_time,
    duration=500,
    amount=25
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    if elapsed < duration:

        progress = (
            elapsed /
            duration
        )

        shake_strength = int(
            amount *
            (1 - progress)
        )

        shake_x = random.randint(
            -shake_strength,
            shake_strength
        )

        shake_y = random.randint(
            -shake_strength,
            shake_strength
        )

        if progress < 0.25:

            zoom_progress = (
                progress /
                0.25
            )

            scale = (
                1.0 +
                zoom_progress *
                0.18
            )

        else:

            zoom_progress = (
                (progress - 0.25) /
                0.75
            )

            scale = (
                1.18 -
                zoom_progress *
                0.18
            )

        image_width = int(
            SCREEN_WIDTH *
            scale
        )

        image_height = int(
            SCREEN_HEIGHT *
            scale
        )

        scaled_background = pygame.transform.smoothscale(
            background,
            (
                image_width,
                image_height
            )
        )

        image_x = (
            SCREEN_WIDTH -
            image_width
        ) // 2 + shake_x

        image_y = (
            SCREEN_HEIGHT -
            image_height
        ) // 2 + shake_y

        screen.blit(
            scaled_background,
            (
                image_x,
                image_y
            )
        )

        if elapsed < 80:

            flash_alpha = int(
                255 *
                (
                    1 -
                    elapsed /
                    80
                )
            )

            flash = pygame.Surface(
                (
                    SCREEN_WIDTH,
                    SCREEN_HEIGHT
                )
            )

            flash.fill(
                WHITE
            )

            flash.set_alpha(
                flash_alpha
            )

            screen.blit(
                flash,
                (0, 0)
            )

    else:

        screen.blit(
            background,
            (0, 0)
        )


# ============================================================
# PICTURE 9 SHAKE
# ============================================================

def draw_picture9_shake(
    screen,
    background,
    start_time,
    duration=500,
    amount=18
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    if elapsed < duration:

        progress = (
            elapsed /
            duration
        )

        shake_strength = int(
            amount *
            (1 - progress)
        )

        shake_x = random.randint(
            -shake_strength,
            shake_strength
        )

        shake_y = random.randint(
            -shake_strength,
            shake_strength
        )

        screen.blit(
            background,
            (
                shake_x,
                shake_y
            )
        )

    else:

        screen.blit(
            background,
            (0, 0)
        )


# ============================================================
# PICTURE 9 FADE OUT
# ============================================================

def draw_picture9_fade_out(
    screen,
    background,
    start_time,
    duration=1000
):

    current_time = pygame.time.get_ticks()

    elapsed = (
        current_time -
        start_time
    )

    screen.blit(
        background,
        (0, 0)
    )

    progress = min(
        elapsed /
        duration,
        1.0
    )

    fade = pygame.Surface(
        (
            SCREEN_WIDTH,
            SCREEN_HEIGHT
        )
    )

    fade.fill(
        (0, 0, 0)
    )

    fade.set_alpha(
        int(
            255 *
            progress
        )
    )

    screen.blit(
        fade,
        (0, 0)
    )


# ============================================================
# SKIP BUTTON
# ============================================================

def draw_skip_button(
    screen,
    button_rect
):

    mouse_pos = pygame.mouse.get_pos()

    if button_rect.collidepoint(mouse_pos):

        background_color = (
            70,
            70,
            70
        )

    else:

        background_color = (
            25,
            25,
            25
        )


    button_surface = pygame.Surface(
        (
            button_rect.width,
            button_rect.height
        ),
        pygame.SRCALPHA
    )

    button_surface.fill(
        (
            background_color[0],
            background_color[1],
            background_color[2],
            210
        )
    )


    pygame.draw.rect(
        button_surface,
        WHITE,
        (
            0,
            0,
            button_rect.width,
            button_rect.height
        ),
        2
    )


    font = pygame.font.Font(
        None,
        28
    )


    text = font.render(
        "SKIP",
        True,
        WHITE
    )


    text_x = (
        button_rect.width -
        text.get_width()
    ) // 2

    text_y = (
        button_rect.height -
        text.get_height()
    ) // 2


    button_surface.blit(
        text,
        (
            text_x,
            text_y
        )
    )


    screen.blit(
        button_surface,
        button_rect.topleft
    )


# ============================================================
# CUTSCENE 2 HELPERS
# ============================================================

def load_background(path, width, height):
    """Load and scale a background image for Chapter 1's second cutscene."""
    image = pygame.image.load(path).convert()
    image = pygame.transform.scale(image, (width, height))
    return image


def draw_background(screen, background, offset_x=0, offset_y=0):
    """Draw a background with an optional position offset."""
    screen.blit(background, (offset_x, offset_y))