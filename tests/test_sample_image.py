"""
Tests for processing the sample image.
"""

import os
from pathlib import Path

import cv2
import numpy as np

from led_strip_calibrator.centroid import find_brightest_point, find_led_center_weighted


def test_find_brightest_point_sample():
    """Test finding the brightest point in the sample image."""
    # Get the path to the sample image
    test_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    sample_path = test_dir / "sample.jpg"

    # Load the image
    image = cv2.imread(str(sample_path))
    assert image is not None, f"Failed to load sample image from {sample_path}"

    # Find the brightest point
    centroid = find_brightest_point(image)

    # We expect to find a centroid
    assert centroid is not None

    x, y = centroid

    # Print the detected coordinates for debugging
    print(f"Detected brightest point at: ({x}, {y})")

    # Create a visualization for debugging
    output_image = image.copy()
    cv2.circle(output_image, (x, y), 10, (0, 255, 0), 2)
    output_path = test_dir / "sample_detection.jpg"
    cv2.imwrite(str(output_path), output_image)
    print(f"Visualization saved to {output_path}")


def test_weighted_centroid_sample():
    """Test finding the weighted centroid in the sample image."""
    # Get the path to the sample image
    test_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    sample_path = test_dir / "sample.jpg"

    # Load the image
    image = cv2.imread(str(sample_path))
    assert image is not None, f"Failed to load sample image from {sample_path}"

    # Find the weighted centroid
    centroid = find_led_center_weighted(image)

    # We expect to find a centroid
    assert centroid is not None

    x, y = centroid

    # Print the detected coordinates for debugging
    print(f"Detected weighted centroid at: ({x}, {y})")

    # Create a visualization for debugging
    output_image = image.copy()
    cv2.circle(output_image, (x, y), 10, (0, 0, 255), 2)
    output_path = test_dir / "sample_weighted_detection.jpg"
    cv2.imwrite(str(output_path), output_image)
    print(f"Visualization saved to {output_path}")


def test_compare_methods_sample():
    """Compare both centroid detection methods on the sample image."""
    # Get the path to the sample image
    test_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    sample_path = test_dir / "sample.jpg"

    # Load the image
    image = cv2.imread(str(sample_path))
    assert image is not None, f"Failed to load sample image from {sample_path}"

    # Find centroids using both methods
    brightest = find_brightest_point(image)
    weighted = find_led_center_weighted(image)

    assert brightest is not None
    assert weighted is not None

    # Calculate distance between the two methods
    bx, by = brightest
    wx, wy = weighted
    distance = np.sqrt((bx - wx) ** 2 + (by - wy) ** 2)

    print(f"Brightest point: ({bx}, {by})")
    print(f"Weighted centroid: ({wx}, {wy})")
    print(f"Distance between methods: {distance:.2f} pixels")

    # Create a visualization showing both detections
    output_image = image.copy()
    cv2.circle(output_image, (bx, by), 10, (0, 255, 0), 2)  # Green for brightest
    cv2.circle(output_image, (wx, wy), 10, (0, 0, 255), 2)  # Red for weighted
    cv2.putText(
        output_image,
        "Brightest",
        (bx + 15, by),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
    )
    cv2.putText(
        output_image,
        "Weighted",
        (wx + 15, wy),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255),
        2,
    )

    output_path = test_dir / "sample_comparison.jpg"
    cv2.imwrite(str(output_path), output_image)
    print(f"Comparison visualization saved to {output_path}")
