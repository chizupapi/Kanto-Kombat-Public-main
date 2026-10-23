import os
import pygame


# ============================================================
# LOAD CHARACTER IMAGE
# ============================================================

def load_character(
    image_path,
    dark_path,
    width,
    height,
    flip=False,
):
    image = pygame.image.load(image_path).convert_alpha()
    image = image.copy()

    image_width, image_height = image.get_size()

    max_width = width * 2
    max_height = height * 2

    scale = min(
        max_width / image_width,
        max_height / image_height,
        1.0,
    )

    if scale < 1.0:
        image = pygame.transform.smoothscale(
            image,
            (
                int(image_width * scale),
                int(image_height * scale),
            ),
        )

    if os.path.exists(dark_path):
        dark = pygame.image.load(dark_path).convert_alpha()
        dark = pygame.transform.smoothscale(dark, image.get_size())
    else:
        dark = image.copy()
        dark.fill(
            (85, 85, 85, 255),
            special_flags=pygame.BLEND_RGBA_MULT,
        )

    if flip:
        image = pygame.transform.flip(image, True, False)
        dark = pygame.transform.flip(dark, True, False)

    return {
        "image": image,
        "dark": dark,
        "size": (width, height),
    }


# ============================================================
# UPDATE DIALOGUE
# ============================================================

def update_dialogue(dialogues, characters, dialogue_index):
    if not dialogues:
        return "", "left", ""

    dialogue_index = max(
        0,
        min(dialogue_index, len(dialogues) - 1),
    )

    current = dialogues[dialogue_index]
    name = current["name"]
    text = current["text"]

    if name in characters:
        side = characters[name]["side"]
    else:
        side = "left"

    return name, side, text


# ============================================================
# WRAP TEXT
# ============================================================

def draw_wrapped_text(
    surface,
    text,
    font,
    color,
    rect,
    line_spacing=5,
):
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = (
            word
            if not current_line
            else current_line + " " + word
        )

        if font.size(test_line)[0] <= rect.width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    y = rect.y

    for line in lines:
        rendered = font.render(line, True, color)
        surface.blit(rendered, (rect.x, y))
        y += rendered.get_height() + line_spacing

        if y > rect.bottom:
            break


# ============================================================
# DRAW DIALOGUE BOX
# ============================================================

def draw_dialogue(
    window,
    name,
    text,
    side,
    font,
    small_font,
):
    box_x = 80
    box_y = 515
    box_width = 1088
    box_height = 160

    # Dark, nearly opaque background for easy reading.
    box_surface = pygame.Surface(
        (box_width, box_height),
        pygame.SRCALPHA,
    )
    box_surface.fill((8, 8, 12, 240))
    window.blit(box_surface, (box_x, box_y))

    pygame.draw.rect(
        window,
        (220, 220, 220),
        (box_x, box_y, box_width, box_height),
        2,
        border_radius=8,
    )

    name_width = max(150, small_font.size(name)[0] + 35)
    name_height = 38

    if side == "right":
        name_x = box_x + box_width - name_width - 20
    else:
        name_x = box_x + 20

    name_y = box_y - 28

    pygame.draw.rect(
        window,
        (15, 15, 20),
        (name_x, name_y, name_width, name_height),
        border_radius=6,
    )
    pygame.draw.rect(
        window,
        (220, 220, 220),
        (name_x, name_y, name_width, name_height),
        2,
        border_radius=6,
    )

    name_surface = small_font.render(name, True, (255, 255, 255))
    name_rect = name_surface.get_rect(
        center=(
            name_x + name_width // 2,
            name_y + name_height // 2,
        )
    )
    window.blit(name_surface, name_rect)

    text_rect = pygame.Rect(
        box_x + 28,
        box_y + 28,
        box_width - 56,
        box_height - 45,
    )

    draw_wrapped_text(
        window,
        text,
        font,
        (255, 255, 255),
        text_rect,
        line_spacing=5,
    )


# ============================================================
# DRAW CHARACTER
# ============================================================

_scaled_cache = {}


def draw_character(
    window,
    character,
    position,
    scale=1.0,
    speaking=False,
):
    # Bright image for the active speaker, dark image for the listener.
    image = character["image"] if speaking else character["dark"]

    base_width, base_height = character["size"]
    target_width = max(1, int(base_width * scale))
    target_height = max(1, int(base_height * scale))

    cache_key = (id(image), target_width, target_height)

    if cache_key not in _scaled_cache:
        _scaled_cache[cache_key] = pygame.transform.smoothscale(
            image,
            (target_width, target_height),
        )

    scaled_image = _scaled_cache[cache_key]

    x, y = position

    # Keep the character centered horizontally and anchored at the feet
    # while zooming, so the zoom doesn't look like the sprite is sliding.
    x -= (target_width - base_width) // 2
    y -= target_height - base_height

    window.blit(scaled_image, (int(x), int(y)))
