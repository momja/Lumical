import csv
import io
import json
from typing import Dict, Tuple


class LEDCalibrationData:
    """Handle LED calibration data loading and normalization."""

    def __init__(self, calibration_file: str | None = None):
        """Initialize with calibration data from JSON file."""
        self.led_positions: Dict[int, Tuple[float, float]] = {}
        self.image_width: int = 0
        self.image_height: int = 0
        if calibration_file:
            self.load_calibration(calibration_file)
        self.normalize_coordinates()

    def load_calibration(self, calibration_file: str) -> None:
        """Load LED positions from calibration JSON file."""
        with open(calibration_file, "r") as f:
            # Load the JSON data
            data = json.load(f)

            # Get dimensions from JSON
            self.image_height = data.get("height", 0)
            self.image_width = data.get("width", 0)

            # Parse the embedded CSV data
            csv_data = data.get("coords", "")
            csv_reader = csv.DictReader(io.StringIO(csv_data))

            for row in csv_reader:
                if row.get("x") and row.get("y"):  # Skip empty rows
                    led_index = int(row["led_index"])
                    x, y = int(row["x"]), int(row["y"])
                    self.led_positions[led_index] = (x, y)

        print(f"Loaded {len(self.led_positions)} LED positions")
        print(f"Image dimensions: {self.image_width}x{self.image_height}")

    def normalize_coordinates(self) -> None:
        """Normalize LED coordinates to 0-1 range for web canvas."""
        self.normalized_positions: Dict[int, Tuple[float, float]] = {}

        for led_index, (x, y) in self.led_positions.items():
            norm_x = x / self.image_width
            norm_y = y / self.image_height
            self.normalized_positions[led_index] = (norm_x, norm_y)

    def add_led(self, led_index: int, x: float, y: float) -> Tuple[float, float]:
        """Add a new LED position using normalized coordinates (0-1 range).

        Args:
            led_index: The index of the LED
            x: Normalized x-coordinate (0-1)
            y: Normalized y-coordinate (0-1)

        Returns:
            Tuple of the raw (x, y) coordinates
        """
        # Add to normalized positions
        self.normalized_positions[led_index] = (x, y)

        # Convert back to original coordinates for raw positions
        raw_x = x * self.image_width
        raw_y = y * self.image_height
        self.led_positions[led_index] = (raw_x, raw_y)

        return (raw_x, raw_y)


if __name__ == "__main__":
    # This block allows the module to be run directly as a script for testing purposes.
    # It provides a simple way to verify that the calibration data loading works correctly
    # without needing to invoke the full application.
    #
    # Example usage:
    #   python -m led_strip_calibrator.led_calibration_data
    #   python -m led_strip_calibrator.led_calibration_data path/to/custom_calibration.json

    import sys

    # Use the provided file or default to led_calibration.json
    calibration_file = sys.argv[1] if len(sys.argv) > 1 else "led_calibration.json"

    # Create the calibration data object
    calibration = LEDCalibrationData(calibration_file)

    # Print the loaded data
    print(f"\nLoaded {len(calibration.led_positions)} LED positions:")
    for led_index in sorted(calibration.led_positions.keys()):
        x, y = calibration.led_positions[led_index]
        print(f"LED {led_index}: ({x:.1f}, {y:.1f})")

    print(f"\nImage dimensions: {calibration.image_width}x{calibration.image_height}")

    print("\nNormalized positions:")
    for led_index in sorted(calibration.normalized_positions.keys())[
        :5
    ]:  # Show first 5 for brevity
        nx, ny = calibration.normalized_positions[led_index]
        print(f"LED {led_index}: ({nx:.3f}, {ny:.3f})")
