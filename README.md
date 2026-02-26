# Raspberry Pi Pico Handheld Arcade Console

A handheld gaming console powered by the Raspberry Pi Pico (RP2040), built entirely in MicroPython. It features a custom ST7789 framebuffer display driver and seven fully playable retro arcade games.

## Hardware Components
* Raspberry Pi Pico (RP2040)
* ST7789 240x240 Color LCD Display (SPI)
* Analog Thumbstick (X/Y)
* 2x Push Buttons (Action & Exit)
* Piezo Buzzer (PWM Audio)

## Pin Mapping & Wiring
| Component | GPIO Pin | Notes |
| :--- | :--- | :--- |
| Joystick X | 26 (ADC0) | Analog thumbstick |
| Joystick Y | 27 (ADC1) | Analog thumbstick |
| Button A (Exit) | 3 | Uses internal PULL_UP |
| Button B (Action)| 10 | Uses internal PULL_UP |
| Buzzer | 21 | PWM for sound |
| Display RST | 12 | ST7789 Reset |
| Display DC | 11 | ST7789 Data/Command |
| Display CS | 13 | ST7789 Chip Select |
| Display SCK | 6 | SPI Clock |
| Display MOSI| 7 | SPI Data |

## Included Games
1. **Snake:** Classic grid-based snake.
2. **Pong:** Retro paddle-and-ball game.
3. **Space Shooter:** Destroy falling asteroids.
4. **Flappy:** Navigate through pipe gaps.
5. **Dodger:** Avoid falling blocks.
6. **Cave Flyer:** Helicopter survival in shrinking tunnels.
7. **Dino:** Endless side-scrolling runner.

## Memory Management
The system uses a custom `ST7789_FB` class to manage the 112.5 KB framebuffer within the Pico's 264 KB SRAM limit. The framebuffer is allocated once during initialization, and game loops are optimized to avoid dynamic memory reallocation and prevent heap fragmentation.
