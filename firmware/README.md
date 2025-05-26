# LED Strip Calibrator Firmware

This firmware runs on an ESP32 microcontroller and controls individually addressable LED strips (WS2811) for calibration purposes.

## Features

- Activates one LED at a time at full brightness
- Uses a button input to increment to the next LED
- Provides serial output indicating which LED is currently active

## Hardware Requirements

- ESP32 microcontroller
- Individually addressable LED strip (WS2811)
- Momentary push button
- Power supply appropriate for your LED strip

## Wiring

1. Connect the LED strip data line to GPIO 5 (configurable in `config.py`)
2. Connect the button between GPIO 0 (configurable) and GND
3. Connect the LED strip power and ground directly to the power supply
4. Connect the ESP32 and LED strip grounds together

## Installation

1. Install MicroPython on your ESP32
2. Copy all firmware files to the ESP32
3. Reboot the ESP32

## Configuration

Edit `config.py` to match your specific hardware setup:

- `LED_PIN`: GPIO pin connected to the LED strip data line
- `BUTTON_PIN`: GPIO pin connected to the button
- `NUM_LEDS`: Number of LEDs in the strip
- `LED_BRIGHTNESS`: Brightness level (0-255)

## Usage

1. Power up the ESP32
2. The first LED will illuminate at full brightness
3. Press the button to advance to the next LED
4. After each button press, take a picture of the illuminated LED
5. Repeat until all LEDs have been captured

## Troubleshooting

- If no LEDs light up, check power connections and data line
- If button presses are not registered, check button wiring
- For more detailed debugging, enable WiFi and WebREPL in `boot.py`