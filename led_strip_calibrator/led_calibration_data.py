from typing import Dict, Tuple
import csv

class LEDCalibrationData:
    """Handle LED calibration data loading and normalization."""

    def __init__(self, calibration_file: str | None = None):
        """Initialize with calibration data from CSV file."""
        self.led_positions: Dict[int, Tuple[float, float]] = {}
        self.image_width: int = 0
        self.image_height: int = 0
        if calibration_file:
            self.load_calibration(calibration_file)
        self.normalize_coordinates()

    def load_calibration(self, calibration_file: str) -> None:
        """Load LED positions from calibration CSV file."""
        with open(calibration_file, 'r') as f:
            reader = csv.DictReader(f)
            max_x, max_y = 0, 0

            for row in reader:
                if row['x'] and row['y']:  # Skip empty rows
                    led_index = int(row['led_index'])
                    x, y = int(row['x']), int(row['y'])
                    self.led_positions[led_index] = (x, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

            # Estimate image dimensions from max coordinates
            self.image_width = max_x + 100  # Add padding
            self.image_height = max_y + 100

        print(f"Loaded {len(self.led_positions)} LED positions")
        print(f"Estimated image dimensions: {self.image_width}x{self.image_height}")

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
