"""
LED Strip Calibration Firmware for ESP32.

This firmware controls individually addressable LED strips (WS2811) for calibration purposes.
It turns on one LED at a time at full brightness and provides a button input to
increment to the next LED.
"""

import time

import machine
import neopixel

# Configuration
LED_PIN = 5  # GPIO pin connected to the LED strip data line
BUTTON_PIN = 0  # GPIO pin connected to the button
NUM_LEDS = 60  # Number of LEDs in the strip
LED_BRIGHTNESS = 255  # Full brightness (0-255)
DEBOUNCE_TIME_MS = 200  # Debounce time in milliseconds

# Initialize hardware
led_strip = neopixel.NeoPixel(machine.Pin(LED_PIN), NUM_LEDS)
button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

# Global state
current_led = 0
last_button_time = 0


def clear_all_leds():
    """Turn off all LEDs in the strip."""
    for i in range(NUM_LEDS):
        led_strip[i] = (0, 0, 0)
    led_strip.write()


def set_current_led():
    """Turn on only the current LED at full brightness (white)."""
    clear_all_leds()
    led_strip[current_led] = (LED_BRIGHTNESS, LED_BRIGHTNESS, LED_BRIGHTNESS)
    led_strip.write()


def button_pressed(pin):
    """
    Button press interrupt handler.

    Increments to the next LED with debounce protection.
    """
    global current_led, last_button_time

    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_button_time) > DEBOUNCE_TIME_MS:
        current_led = (current_led + 1) % NUM_LEDS
        set_current_led()
        print(f"LED {current_led} activated")
        last_button_time = current_time


def main():
    """Main program entry point."""
    # Set up button interrupt
    button.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_pressed)

    # Initialize by turning on the first LED
    set_current_led()
    print(f"LED calibration started. LED {current_led} activated.")
    print("Press button to advance to next LED.")

    # Main loop - keep the program running
    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        # Clean up on error
        clear_all_leds()
