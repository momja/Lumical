"""
Tests for the centroid detection module.
"""

from typing import Tuple

import numpy as np

from led_strip_calibrator.centroid import find_brightest_point, find_led_center_weighted


def create_test_image(
    size: Tuple[int, int] = (100, 100),
    center: Tuple[int, int] = (50, 50),
    radius: int = 5,
    brightness: int = 255,
) -> np.ndarray:
    """
    Create a test image with a bright spot at the specified center.

    Args:
        size: Image size (width, height)
        center: Center of the bright spot (x, y)
        radius: Radius of the bright spot
        brightness: Brightness value (0-255)

    Returns:
        Grayscale image with bright spot
    """
    # Create blank grayscale image
    image = np.zeros((size[1], size[0]), dtype=np.uint8)

    # Create bright spot
    x, y = center
    for i in range(max(0, y - radius), min(size[1], y + radius + 1)):
        for j in range(max(0, x - radius), min(size[0], x + radius + 1)):
            # Calculate distance from center
            dist = np.sqrt((i - y) ** 2 + (j - x) ** 2)
            if dist <= radius:
                # Brightest at center, diminishing with distance
                val = int(brightness * (1 - dist / radius))
                image[i, j] = val

    return image


class TestBrightestPoint:
    """Tests for the find_brightest_point function."""

    def test_simple_bright_spot(self) -> None:
        """Test finding a simple bright spot in the center."""
        image = create_test_image(size=(100, 100), center=(50, 50))
        centroid = find_brightest_point(image)
        assert centroid is not None
        x, y = centroid
        # Allow small deviations due to discretization
        assert abs(x - 50) <= 1
        assert abs(y - 50) <= 1

    def test_bright_spot_corner(self) -> None:
        """Test finding a bright spot in the corner."""
        image = create_test_image(size=(100, 100), center=(10, 10))
        centroid = find_brightest_point(image)
        assert centroid is not None
        x, y = centroid
        assert abs(x - 10) <= 1
        assert abs(y - 10) <= 1

    def test_no_bright_spot(self) -> None:
        """Test image with no bright spot above threshold."""
        # Create a dim image
        image = create_test_image(size=(100, 100), brightness=50)
        # Set high threshold
        centroid = find_brightest_point(image, threshold=100)
        assert centroid is None

    def test_multiple_bright_spots(self) -> None:
        """Test image with multiple bright spots - should find the largest."""
        # Create first bright spot
        image = create_test_image(size=(100, 100), center=(30, 30), radius=10)
        # Create second, smaller bright spot
        second_image = create_test_image(size=(100, 100), center=(70, 70), radius=5)
        # Combine images (maximum value at each pixel)
        image = np.maximum(image, second_image)

        centroid = find_brightest_point(image)
        assert centroid is not None
        x, y = centroid
        # Should find the larger spot
        assert abs(x - 30) <= 2
        assert abs(y - 30) <= 2


class TestWeightedCenter:
    """Tests for the find_led_center_weighted function."""

    def test_simple_bright_spot(self) -> None:
        """Test finding a simple bright spot in the center."""
        image = create_test_image(size=(100, 100), center=(50, 50))
        centroid = find_led_center_weighted(image)
        assert centroid is not None
        x, y = centroid
        # Allow small deviations due to discretization
        assert abs(x - 50) <= 1
        assert abs(y - 50) <= 1

    def test_bright_spot_corner(self) -> None:
        """Test finding a bright spot in the corner."""
        image = create_test_image(size=(100, 100), center=(10, 10))
        centroid = find_led_center_weighted(image)
        assert centroid is not None
        x, y = centroid
        assert abs(x - 10) <= 1
        assert abs(y - 10) <= 1

    def test_no_bright_spot(self) -> None:
        """Test image with no bright spot."""
        # Create a completely black image
        image = np.zeros((100, 100), dtype=np.uint8)
        centroid = find_led_center_weighted(image)
        assert centroid is None

    def test_multiple_bright_spots(self) -> None:
        """Test weighted centroid with multiple bright spots."""
        # Create first bright spot
        image = create_test_image(
            size=(100, 100), center=(30, 30), radius=10, brightness=200
        )
        # Create second, brighter spot
        second_image = create_test_image(
            size=(100, 100), center=(70, 70), radius=10, brightness=255
        )
        # Combine images (maximum value at each pixel)
        image = np.maximum(image, second_image)

        centroid = find_led_center_weighted(image)
        assert centroid is not None
        x, y = centroid
        # Should be biased toward the brighter spot
        assert x > 50
