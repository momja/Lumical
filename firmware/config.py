"""
Configuration settings for LED strip calibration firmware.

This module contains all the configurable parameters for the LED calibration process.
Modify these values to match your specific hardware setup.
"""

# Hardware configuration
LED_PIN = 5  # GPIO pin connected to the LED strip data line
BUTTON_PIN = 0  # GPIO pin connected to the button
NUM_LEDS = 60  # Number of LEDs in the strip (change to match your strip)

# LED settings
LED_BRIGHTNESS = 255  # Full brightness (0-255)
LED_COLOR = (255, 255, 255)  # White (RGB)

# Button debouncing
DEBOUNCE_TIME_MS = 200  # Debounce time in milliseconds

# Serial communication
BAUD_RATE = 115200  # Serial baud rate