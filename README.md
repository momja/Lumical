# LED Strip Calibrator

A tool for real-world calibration of individually addressable LED light strips. Determines the 2D coordinates of each LED pixel when projected onto a plane parallel to the camera image plane.

## Overview

This project consists of two main components:

1. **Firmware**: MicroPython code that runs on an ESP32 microcontroller. Controls the LED strip by turning on one LED at a time and provides a button interface to advance to the next LED.

2. **Calibration Software**: Python application that processes images of the illuminated LEDs to determine their 2D coordinates, outputting a CSV mapping file.

## Installation

### Firmware

See the [firmware README](firmware/README.md) for detailed instructions on installing and using the ESP32 firmware.

### Calibration Software

Requirements:
- Python 3.14+

Run using `uv`:

## Usage

### Calibration Process

1. Set up the LED strip and camera so they are parallel to each other
2. Flash the ESP32 with the firmware
3. Start with the first LED illuminated
4. Take a photo of the illuminated LED
5. Press the button to advance to the next LED
6. Repeat steps 4-5 until all LEDs have been captured
7. Process the images using the calibration software

### Processing Images

```bash
uv run -m led_strip_calibrator process path/to/images --output calibration.csv
```

Additional options:
- `--method`, `-m`: Centroid detection method (`threshold` or `weighted`, default is `weighted`)
- `--threshold`, `-t`: Brightness threshold (0-255) (default: 200)
  - For `threshold` method: Pixels above this value are considered part of the LED
  - For `weighted` method: Only pixels above this value contribute to the centroid calculation
- `--visualize`, `-v`: Create overlay visualizations showing detected LED positions on each original image

Example with all options:
```bash
uv run -m led_strip_calibrator process path/to/images --output calibration.csv --method threshold --threshold 180 --visualize
```

**IMPORTANT**: Images must be named according to this pattern:
- `led_0.jpg` - First LED
- `led_1.jpg` - Second LED
- `led_2.jpg` - Third LED
- etc.

The number in the filename must match the position of the LED on the strip.
If multiple LED strips are used, post-processing might be required before streaming
to your LED driver.

## Output

The calibration process produces:
- A JSON file with attributes
    - "coords": CSV string with rows as `led_index`, `x`, `y` for each LED
    - "height": The height of the calibration images (they must all be the same dimensions)
    - "width": The width of the calibration images.
- (Optionally) A visualization image showing all LED positions

When using the `--visualize` option:
- An `overlays` directory is created with individual overlays
- Each LED image gets an overlay showing the detected center point
- Files are named `led_X_overlay.jpg` where X is the LED index
- A composite image is created that blends all LED images together
- The composite shows all detected LED positions with color-coded markers
- This composite is saved as `[output_name]_composite.jpg`

## Development

```bash
# Run tests
pytest

# Check code style
uv run ruff check .

# Format code
uv run ruff format .

# Check types
mypy led_strip_calibrator
```

## License

[MIT](LICENSE)
