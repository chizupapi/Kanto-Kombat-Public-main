import pygame
import sys

pygame.init()

# Screen setup
WIDTH, HEIGHT = 600, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Adaptive Skill Animation")

clock = pygame.time.Clock()

frames = []

for i in range(1, 9):
    image = pygame.image.load(f"assets/animations/Vice Yorme/second/second_{i}.png").convert_alpha()
    frames.append(image)

current_frame = 0
frame_time = 120
last_update = pygame.time.get_ticks()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    now = pygame.time.get_ticks()
    if now - last_update > frame_time:
        current_frame = (current_frame + 1) % len(frames)
        last_update = now

    frame = frames[current_frame]
    frame_rect = frame.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    screen.fill((30, 30, 30))
    screen.blit(frame, frame_rect)
    pygame.display.flip()

    clock.tick(60)

pygame.quit()
sys.exit()