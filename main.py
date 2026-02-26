import time
import random
import gc
import framebuf
from machine import Pin, SPI, ADC, PWM

# ==========================================================
#                      CONFIGURATION
# ==========================================================
WIDTH = 240
HEIGHT = 320
BAUDRATE = 62_500_000 

joy_x = ADC(26)
joy_y = ADC(27)

BTN_A = Pin(3, Pin.IN, Pin.PULL_UP)  # Exit / Back
BTN_B = Pin(10, Pin.IN, Pin.PULL_UP)   # Action / Shoot / Select

onboard_led = Pin(25, Pin.OUT)
buzzer = PWM(Pin(21))
buzzer.duty_u16(0)

# Display Pins
rst = Pin(12, Pin.OUT)
dc = Pin(11, Pin.OUT)
cs = Pin(13, Pin.OUT)
sck = Pin(6)
mosi = Pin(7)

try:
    bl = Pin(14, Pin.OUT)
    bl.value(1)
except:
    pass

# ==========================================================
#                      DISPLAY DRIVER
# ==========================================================
class ST7789_FB:
    def __init__(self, spi, width, height, reset, dc, cs):
        self.width = width
        self.height = height
        self.spi = spi
        self.rst = reset
        self.dc = dc
        self.cs = cs
        self.cs.value(1)

        self.init_display()
        gc.collect()

        # Full framebuffer
        self.buffer = bytearray(self.width * self.height * 2)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.RGB565)

    def write_cmd(self, cmd):
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs.value(1)

    def write_data(self, buf):
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buf)
        self.cs.value(1)

    def init_display(self):
        self.rst.value(1); time.sleep(0.1)
        self.rst.value(0); time.sleep(0.1)
        self.rst.value(1); time.sleep(0.1)

        self.write_cmd(0x01); time.sleep(0.150)
        self.write_cmd(0x11); time.sleep(0.150)

        self.write_cmd(0x3A)
        self.write_data(bytearray([0x55]))  # 16-bit color

        # Orientation (your original setting)
        self.write_cmd(0x36)
        self.write_data(bytearray([0x40]))

        self.write_cmd(0x21)  # inversion
        self.write_cmd(0x13)
        self.write_cmd(0x29)

    def refresh(self):
        self.write_cmd(0x2A)
        self.write_data(bytearray([0,0,(self.width-1)>>8,(self.width-1)&0xFF]))
        self.write_cmd(0x2B)
        self.write_data(bytearray([0,0,(self.height-1)>>8,(self.height-1)&0xFF]))
        self.write_cmd(0x2C)

        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(self.buffer)
        self.cs.value(1)

# ==========================================================
#                   GLOBALS / COLORS
# ==========================================================
spi = SPI(0, baudrate=BAUDRATE, polarity=1, phase=1, sck=sck, mosi=mosi)
display = ST7789_FB(spi, WIDTH, HEIGHT, rst, dc, cs)
fb = display.fb

BLACK   = 0x0000
WHITE   = 0xFFFF
RED     = 0x00F8
GREEN   = 0xE007
BLUE    = 0x1F00
YELLOW  = 0xE0FF
CYAN    = 0x07FF
MAGENTA = 0xF81F

BAR_TOP = BLUE
BAR_SEL = YELLOW

# ==========================================================
#                   SUPPORT FUNCTIONS
# ==========================================================
def beep(freq, duration_ms):
    buzzer.freq(freq)
    buzzer.duty_u16(30000)
    time.sleep_ms(duration_ms)
    buzzer.duty_u16(0)

def center_text(text, y, color):
    x = (WIDTH - len(text)*8)//2
    fb.text(text, x, y, color)

def clean():
    gc.collect()
    time.sleep_ms(2)

def debounce_button(pin):
    last = pin.value()
    count = 0
    while count < 2:
        if pin.value() != last:
            count += 1
            last = pin.value()
            time.sleep_ms(8)
        else:
            break

def get_direction():
    x = joy_x.read_u16()
    y = joy_y.read_u16()
    low = 20000
    high = 45000
    # X inverted as you wanted
    if x < low:
        return "RIGHT"
    if x > high:
        return "LEFT"
    if y < low:
        return "UP"
    if y > high:
        return "DOWN"
    return None

def show_game_over(title, score):
    fb.fill(BLACK)
    fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
    center_text(title.upper(), 10, BLACK)
    center_text("GAME OVER", 130, RED)
    center_text("SCORE %d" % score, 160, WHITE)
    center_text("A/B: MENU", 190, YELLOW)
    display.refresh()

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 2500:
        if not BTN_A.value() or not BTN_B.value():
            # Clear any bounce
            if not BTN_A.value():
                debounce_button(BTN_A)
            if not BTN_B.value():
                debounce_button(BTN_B)
            break
        time.sleep_ms(20)

# ==========================================================
#                   GAME 1: SNAKE
# ==========================================================
def game_snake():
    clean()
    SEG = 12
    cols = WIDTH // SEG
    rows = (HEIGHT - 40) // SEG

    snake = [(cols//2, rows//2)]
    direction = (1, 0)
    food = (random.randint(0, cols-1), random.randint(0, rows-1))

    speed = 0.16  # starts a bit easier
    frame = 0
    score = 0
    onboard_led.value(1)

    trail_colors = [CYAN, GREEN, YELLOW, MAGENTA]

    while True:
        frame += 1

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("SNAKE - A Exit", 10, BLACK)

        # Food with border
        fx, fy = food
        fb.fill_rect(fx*SEG-1, 40+fy*SEG-1, SEG+2, SEG+2, WHITE)
        fb.fill_rect(fx*SEG, 40+fy*SEG, SEG, SEG, RED)

        # Snake
        for idx, (sx, sy) in enumerate(snake):
            if idx == 0:
                fb.fill_rect(sx*SEG-1, 40+sy*SEG-1, SEG+2, SEG+2, WHITE)
                fb.fill_rect(sx*SEG, 40+sy*SEG, SEG, SEG, GREEN)
            else:
                c = trail_colors[idx % len(trail_colors)]
                fb.fill_rect(sx*SEG, 40+sy*SEG, SEG, SEG, c)

        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        d = get_direction()
        if d == "LEFT" and direction != (1, 0):
            direction = (-1, 0)
        elif d == "RIGHT" and direction != (-1, 0):
            direction = (1, 0)
        elif d == "UP" and direction != (0, 1):
            direction = (0, -1)
        elif d == "DOWN" and direction != (0, -1):
            direction = (0, 1)

        nx = (snake[0][0] + direction[0]) % cols
        ny = (snake[0][1] + direction[1]) % rows

        if (nx, ny) in snake:
            beep(300, 200)
            break

        snake.insert(0, (nx, ny))

        if (nx, ny) == food:
            beep(800, 35)
            score += 1
            while True:
                food = (random.randint(0, cols-1), random.randint(0, rows-1))
                if food not in snake:
                    break
        else:
            snake.pop()

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        # difficulty ramp
        if frame % 30 == 0 and speed > 0.055:
            speed -= 0.005

        if frame % 30 == 0:
            gc.collect()

        time.sleep(speed)

    onboard_led.value(0)
    show_game_over("Snake", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 2: PONG
# ==========================================================
def game_pong():
    clean()
    px = WIDTH//2 - 25
    py = HEIGHT - 40
    paddle_w = 50
    paddle_h = 8

    bx = WIDTH//2
    by = HEIGHT//2
    bdx = 3  # start a bit slower
    bdy = 3

    score = 0
    speed = 0.03  # start easier
    frame = 0

    onboard_led.value(1)

    while True:
        frame += 1

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("PONG - A Exit", 10, BLACK)

        # Paddle with border
        fb.fill_rect(px-2, py-2, paddle_w+4, paddle_h+4, WHITE)
        fb.fill_rect(px, py, paddle_w, paddle_h, GREEN)

        # Ball with border
        fb.fill_rect(bx-1, by-1, 12, 12, WHITE)
        fb.fill_rect(bx, by, 10, 10, YELLOW)

        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        d = get_direction()
        if d == "LEFT" and px > 0:
            px -= 10
        elif d == "RIGHT" and px < WIDTH - paddle_w:
            px += 10

        bx += bdx
        by += bdy

        if bx <= 0 or bx >= WIDTH - 10:
            bdx = -bdx
        if by <= 30:
            bdy = -bdy

        if (by >= py - 10) and (px <= bx <= px + paddle_w):
            bdy = -bdy
            score += 1
            beep(650, 34)

        if by > HEIGHT - 10:
            beep(350, 170)
            break

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        # difficulty ramp
        if frame % 40 == 0 and abs(bdx) < 13:
            bdx += 1 if bdx > 0 else -1
            bdy += 1 if bdy > 0 else -1
            speed *= 0.95

        if frame % 30 == 0:
            gc.collect()

        time.sleep(speed)

    onboard_led.value(0)
    show_game_over("Pong", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 3: SPACE
# ==========================================================
def game_space():
    clean()
    ship_x = WIDTH // 2
    ship_y = HEIGHT - 32

    shots = []
    asteroids = [[random.randint(0, WIDTH - 14), -random.randint(30, 180)] for _ in range(4)]

    score = 0
    speed = 0.055  # slightly easier start
    asteroid_speed = 5
    frame = 0
    shot_cooldown = 0  # will be small for fast shooting

    onboard_led.value(1)

    while True:
        frame += 1

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("SPACE - A Exit", 10, BLACK)

        # Ship with border + cockpit
        fb.fill_rect(ship_x - 10, ship_y - 2, 20, 15, WHITE)
        fb.fill_rect(ship_x - 8, ship_y, 16, 11, GREEN)
        fb.fill_rect(ship_x - 2, ship_y + 5, 4, 7, YELLOW)

        for sx, sy in shots:
            fb.fill_rect(sx - 2, sy, 4, 14, WHITE)

        for ax, ay in asteroids:
            fb.fill_rect(ax, ay, 14, 14, RED)
            fb.rect(ax, ay, 14, 14, WHITE)

        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        d = get_direction()
        if d == "LEFT" and ship_x > 14:
            ship_x -= 10
        elif d == "RIGHT" and ship_x < WIDTH - 14:
            ship_x += 10

        # Shooting â faster: smaller cooldown
        if (not BTN_B.value()) and shot_cooldown == 0 and len(shots) < 5:
            shots.append([ship_x, ship_y])
            beep(1000, 15)
            shot_cooldown = 3   # was 6 â faster fire

        if shot_cooldown > 0:
            shot_cooldown -= 1

        # Move shots (slightly faster)
        for s in shots:
            s[1] -= 15
        shots = [s for s in shots if s[1] > -20]

        # Move asteroids
        for a in asteroids:
            a[1] += asteroid_speed

        for i, a in enumerate(asteroids):
            if a[1] > HEIGHT:
                asteroids[i] = [random.randint(0, WIDTH - 14), -random.randint(40, 200)]

        # Shots vs asteroids
        for s in shots[:]:
            for i, a in enumerate(asteroids):
                if abs(s[0] - a[0]) < 13 and abs(s[1] - a[1]) < 13:
                    asteroids[i] = [random.randint(0, WIDTH - 14), -random.randint(40, 200)]
                    score += 1
                    beep(890, 25)
                    if s in shots:
                        shots.remove(s)
                    break

        # Ship vs asteroids
        for a in asteroids:
            if abs(ship_x - a[0]) < 13 and abs(ship_y - a[1]) < 13:
                beep(310, 220)
                frame = 0
                onboard_led.value(0)
                shots.clear()
                gc.collect()
                show_game_over("Space", score)
                clean()
                gc.collect()
                return

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        # difficulty ramp
        if frame % 50 == 0 and asteroid_speed < 16:
            asteroid_speed += 1
            if speed > 0.02:
                speed *= 0.93

        if frame % 30 == 0:
            gc.collect()

        time.sleep(speed)

    onboard_led.value(0)
    show_game_over("Space", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 4: FLAPPY
# ==========================================================
def game_flappy():
    clean()
    x = 50
    y = HEIGHT // 2
    vel = 0

    pipes = []
    gap = 95   # start easier: bigger gap
    frame = 0
    score = 0
    spd = 0.03  # a bit slower start

    onboard_led.value(1)

    while True:
        frame += 1

        if frame % 80 == 0 and gap > 56:
            gap -= 4

        if frame % 80 == 0 and spd > 0.012:
            spd *= 0.96

        if frame % 60 == 0:
            top = random.randint(36, HEIGHT - 170)
            pipes.append([WIDTH, top, top + gap])

        vel += 1
        y += vel

        if y < 0:
            y = 0
        if y > HEIGHT - 22:
            beep(330, 240)
            break

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("FLAPPY - A Exit", 10, BLACK)

        # Bird with outline and "wing"
        fb.fill_rect(x - 2, y - 2, 18, 18, WHITE)
        fb.fill_rect(x, y, 14, 14, GREEN)
        fb.fill_rect(x + 8, y + 3, 5, 3, YELLOW)

        for p in pipes:
            fb.fill_rect(p[0], 0, 24, p[1], RED)
            fb.fill_rect(p[0], p[2], 24, HEIGHT - p[2], RED)
            fb.rect(p[0], p[1], 24, gap, WHITE)

        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        if not BTN_B.value():
            vel = -9
            beep(820, 23)

        for p in pipes:
            p[0] -= 5
        pipes = [p for p in pipes if p[0] + 24 > 0]

        for p in pipes:
            if x + 14 > p[0] and x < p[0] + 24:
                if not (p[1] < y < p[2]):
                    beep(330, 240)
                    onboard_led.value(0)
                    show_game_over("Flappy", score)
                    clean()
                    gc.collect()
                    return

        score = frame // 80

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        if frame % 40 == 0:
            gc.collect()

        time.sleep(spd)

    onboard_led.value(0)
    show_game_over("Flappy", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 5: DODGER
# ==========================================================
def game_dodger():
    clean()
    px = WIDTH // 2
    py = HEIGHT // 2 + 80

    score = 0
    speed = 0.04  # a bit slower start
    nblocks = 4
    blocks = [[random.randint(10, WIDTH - 30), -random.randint(30, 250)] for _ in range(nblocks)]
    frame = 0

    onboard_led.value(1)

    while True:
        frame += 1

        if frame % 60 == 0 and len(blocks) < 11:
            blocks.append([random.randint(10, WIDTH - 30), -random.randint(30, 250)])

        if frame % 60 == 0 and speed > 0.012:
            speed *= 0.96

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("DODGER - A Exit", 10, BLACK)

        # Player with glow
        fb.fill_rect(px - 14, py - 14, 28, 28, CYAN)
        fb.fill_rect(px - 12, py - 12, 24, 24, WHITE)
        fb.fill_rect(px - 8, py - 8, 16, 16, YELLOW)

        for bx, by in blocks:
            fb.fill_rect(bx, by, 18, 18, RED)
            fb.rect(bx, by, 18, 18, WHITE)

        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        d = get_direction()
        if d == "LEFT" and px > 12:
            px -= 13
        elif d == "RIGHT" and px < WIDTH - 12:
            px += 13
        elif d == "UP" and py > 32:
            py -= 13
        elif d == "DOWN" and py < HEIGHT - 20:
            py += 13

        for i in range(len(blocks)):
            blocks[i][1] += 12
            if blocks[i][1] > HEIGHT:
                blocks[i] = [random.randint(10, WIDTH - 30), -random.randint(30, 250)]
                score += 1

        for bx, by in blocks:
            if abs(px - bx) < 20 and abs(py - by) < 20:
                beep(300, 240)
                onboard_led.value(0)
                show_game_over("Dodger", score)
                clean()
                gc.collect()
                return

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        if frame % 40 == 0:
            gc.collect()

        time.sleep(speed)

    onboard_led.value(0)
    show_game_over("Dodger", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 6: CAVE
# ==========================================================
def game_cave():
    clean()
    x = 40
    y = HEIGHT // 2
    vel = 0

    cave_top = 40
    cave_bottom = HEIGHT - 40
    scroll = 0
    gap = 190   # easier start
    speed = 0.035
    frame = 0
    score = 0

    onboard_led.value(1)

    while True:
        frame += 1

        # difficulty ramp
        if frame % 70 == 0 and gap > 90:
            gap -= 6
        if frame % 60 == 0 and speed > 0.014:
            speed *= 0.97

        vel += 1
        y += vel

        if not BTN_B.value():
            vel = -7
            beep(700, 15)

        # Cave bounds check
        if y < cave_top + 12 or y > cave_bottom - 12:
            beep(305, 185)
            break

        scroll += 4
        if scroll >= 22:
            scroll = 0
            cave_top += random.randint(-10, 10)
            cave_bottom = cave_top + gap
            if cave_top < 20:
                cave_top = 20
            if cave_bottom > HEIGHT - 20:
                cave_bottom = HEIGHT - 20

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("CAVE - A Exit", 10, BLACK)

        fb.fill_rect(0, 0, WIDTH, cave_top, RED)
        fb.fill_rect(0, cave_bottom, WIDTH, HEIGHT - cave_bottom, RED)

        # Helicopter: bold square
        fb.fill_rect(x - 2, y - 2, 20, 20, WHITE)
        fb.fill_rect(x, y, 16, 16, GREEN)

        score = frame // 20
        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        if frame % 40 == 0:
            gc.collect()

        time.sleep(speed)

    onboard_led.value(0)
    show_game_over("Cave", score)
    clean()
    gc.collect()

# ==========================================================
#                   GAME 7: DINO
# ==========================================================
def game_dino():
    clean()
    ground_y = HEIGHT - 40
    dino_x = 40
    dino_y = ground_y - 20
    dino_vy = 0
    gravity = 1
    on_ground = True

    obstacles = []
    frame = 0
    score = 0
    speed = 6  # world scroll speed (starts easy)

    onboard_led.value(1)

    while True:
        frame += 1

        # spawn obstacles â less frequent at start, then faster
        if frame % max(25, 80 - score*2) == 0:
            h = random.randint(20, 28)
            obstacles.append([WIDTH, ground_y - h, h])

        # difficulty ramp
        if frame % 120 == 0 and speed < 13:
            speed += 1

        # physics
        dino_vy += gravity
        dino_y += dino_vy

        if dino_y >= ground_y - 20:
            dino_y = ground_y - 20
            dino_vy = 0
            on_ground = True

        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("DINO - A Exit", 10, BLACK)

        # ground line
        fb.fill_rect(0, ground_y, WIDTH, 2, WHITE)

        # dino sprite (border + body)
        fb.fill_rect(dino_x - 2, dino_y - 2, 24, 24, WHITE)
        fb.fill_rect(dino_x, dino_y, 20, 20, GREEN)
        fb.fill_rect(dino_x + 12, dino_y + 4, 3, 3, BLACK)  # eye

        # obstacles
        for ox, oy, oh in obstacles:
            fb.fill_rect(ox, oy, 12, oh, RED)
            fb.rect(ox, oy, 12, oh, WHITE)

        score = frame // 10
        center_text("SCORE %d" % score, 300, WHITE)
        display.refresh()

        # jump
        if not BTN_B.value() and on_ground:
            dino_vy = -13
            on_ground = False
            beep(840, 20)

        # move obstacles
        for i in range(len(obstacles)):
            obstacles[i][0] -= speed

        obstacles = [o for o in obstacles if o[0] + 12 > 0]

        # collision
        for ox, oy, oh in obstacles:
            if (dino_x + 20 > ox) and (dino_x < ox + 12) and (dino_y + 20 > oy):
                beep(310, 200)
                onboard_led.value(0)
                show_game_over("Dino", score)
                clean()
                gc.collect()
                return

        if not BTN_A.value():
            debounce_button(BTN_A)
            break

        if frame % 40 == 0:
            gc.collect()

        time.sleep(0.02)

    onboard_led.value(0)
    show_game_over("Dino", score)
    clean()
    gc.collect()

# ==========================================================
#                   MAIN MENU
# ==========================================================
GAMES = [
    "Snake",
    "Pong",
    "Space",
    "Flappy",
    "Dodger",
    "Cave",
    "Dino"
]

GAME_FUNCS = [
    game_snake,
    game_pong,
    game_space,
    game_flappy,
    game_dodger,
    game_cave,
    game_dino
]

def main():
    sel = 0
    onboard_led.value(1)
    time.sleep(0.2)
    onboard_led.value(0)

    while True:
        fb.fill(BLACK)
        fb.fill_rect(0, 0, WIDTH, 30, BAR_TOP)
        center_text("ARCADE PRO", 10, BLACK)

        fb.fill_rect(0, HEIGHT - 20, WIDTH, 20, BAR_TOP)
        fb.text("B=PLAY  A=RESET", 42, HEIGHT - 15, BLACK)

        d = get_direction()
        if d == "DOWN":
            sel = (sel + 1) % len(GAMES)
            beep(200, 16)
            time.sleep(0.12)
        elif d == "UP":
            sel = (sel - 1) % len(GAMES)
            beep(200, 16)
            time.sleep(0.12)

        for i, g in enumerate(GAMES):
            y = 50 + i * 30
            if i == sel:
                fb.fill_rect(20, y - 2, 200, 18, BAR_SEL)
                fb.text(g, 80, y + 2, BLACK)
            else:
                fb.text(g, 80, y + 2, WHITE)

        display.refresh()

        if not BTN_B.value():
            debounce_button(BTN_B)
            beep(620, 33)
            center_text("LOADING...", 150, RED)
            display.refresh()
            time.sleep(0.32)
            GAME_FUNCS[sel]()
            gc.collect()

        if not BTN_A.value():
            debounce_button(BTN_A)
            sel = 0
            beep(290, 29)
            time.sleep(0.17)
            gc.collect()

main()
