import pygame
import sys

pygame.init()

SCREEN_W = 800
SCREEN_H = 800

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Comic Scene")

pictures = [
    "assets/scenes/background1.png",
    "assets/scenes/background2.png",
    "assets/scenes/background3.png",
    "assets/scenes/background4.png",

    "assets/scenes/background5.png",
    "assets/scenes/background6.png",
    "assets/scenes/background7.png",
    "assets/scenes/background8.png"
]

images = []

for path in pictures:
    image = pygame.image.load(path).convert()
    images.append(image)

current_panel = 0

GAP = 5

PANEL_W = (SCREEN_W - GAP) // 2
PANEL_H = (SCREEN_H - GAP) // 2

positions = [
    (0, 0),
    (PANEL_W + GAP, 0),
    (0, PANEL_H + GAP),
    (PANEL_W + GAP, PANEL_H + GAP)
]


def fit_image(image, width, height):

    image_width, image_height = image.get_size()

    scale = max(
        width / image_width,
        height / image_height
    )

    new_width = int(image_width * scale)
    new_height = int(image_height * scale)

    image = pygame.transform.smoothscale(
        image,
        (new_width, new_height)
    )

    crop_x = (new_width - width) // 2
    crop_y = (new_height - height) // 2

    image = image.subsurface(
        (crop_x, crop_y, width, height)
    ).copy()

    return image


running = True

while running:

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_RETURN:

                if current_panel < len(images):
                    current_panel += 1

                else:
                    current_panel = 0

    screen.fill((0, 0, 0))

    page_start = (current_panel // 4) * 4

    if current_panel > 0:
        page_start = ((current_panel - 1) // 4) * 4

    panels_on_page = current_panel - page_start

    if current_panel == len(images):
        panels_on_page = 4

    for i in range(panels_on_page):

        image_index = page_start + i

        if image_index < len(images):

            image = fit_image(
                images[image_index],
                PANEL_W,
                PANEL_H
            )

            x, y = positions[i]

            screen.blit(image, (x, y))

    pygame.display.flip()

pygame.quit()
sys.exit()