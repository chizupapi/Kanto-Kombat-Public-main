import pygame
import sys

pygame.init()

SCREEN_W = 800
SCREEN_H = 800

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Comic Scene")

background = pygame.image.load("assets/scenes/background5.png").convert()
background = pygame.transform.scale(background, (SCREEN_W, SCREEN_H))

pictures = [
    "assets/scenes/background1.png",
    "assets/scenes/background2.png",
    "assets/scenes/background3.png",
    "assets/scenes/background4.png"
]
images = []

for path in pictures:
    image = pygame.image.load(path).convert_alpha()
    images.append(image)

current_picture = 0

panel_width = 380
panel_height = 380

positions = [
    (20, 20),
    (400, 20),
    (20, 400),
    (400, 400)
]


def fit_image(image, width, height):
    image_width, image_height = image.get_size()

    scale = min(
        width / image_width,
        height / image_height
    )

    new_width = int(image_width * scale)
    new_height = int(image_height * scale)

    image = pygame.transform.smoothscale(
        image,
        (new_width, new_height)
    )

    return image


running = True

while running:

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_RETURN:

                if current_picture < 4:
                    current_picture += 1

    screen.blit(background, (0, 0))

    for i in range(current_picture):

        image = fit_image(
            images[i],
            panel_width,
            panel_height
        )

        x, y = positions[i]

        image_x = x + (panel_width - image.get_width()) // 2
        image_y = y + (panel_height - image.get_height()) // 2

        screen.blit(image, (image_x, image_y))

    pygame.display.flip()

pygame.quit()
sys.exit()