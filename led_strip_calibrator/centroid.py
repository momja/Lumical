"""
Functions for detecting LED centroids in images.

This module provides functionality to locate the center point of illuminated LEDs
in calibration images using brightness detection.
"""

from typing import Optional, Tuple

import cv2
import numpy as np


def find_brightest_point(
    image: np.ndarray, threshold: int = 200, min_area: int = 5
) -> Optional[Tuple[int, int]]:
    """
    Find the centroid of the brightest area in an image.

    Uses thresholding to isolate bright regions, then calculates the centroid
    of the largest contiguous bright area.

    Args:
        image: Input image (grayscale or color)
        threshold: Brightness threshold (0-255)
        min_area: Minimum area in pixels for a valid detection

    Returns:
        Tuple of (x, y) coordinates of the centroid, or None if no bright spot found
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Apply threshold to isolate bright regions
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # Find contours in the thresholded image
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # If no contours found, return None
    if not contours:
        return None

    # Find the largest contour
    largest_contour = max(contours, key=cv2.contourArea)

    # Check if the contour area meets the minimum size requirement
    if cv2.contourArea(largest_contour) < min_area:
        return None

    # Calculate centroid of the largest contour
    M = cv2.moments(largest_contour)

    # Avoid division by zero
    if M["m00"] == 0:
        return None

    centroid_x = int(M["m10"] / M["m00"])
    centroid_y = int(M["m01"] / M["m00"])

    return (centroid_x, centroid_y)


def find_led_center_weighted(
    image: np.ndarray, min_brightness: int = 100
) -> Optional[Tuple[int, int]]:
    """
    Find LED center using brightness-weighted centroid calculation.

    This method is more robust for diffuse LED illumination, as it considers
    the brightness of each pixel as a weight.

    Args:
        image: Input image (grayscale or color)
        min_brightness: Minimum brightness threshold (0-255) to consider pixels

    Returns:
        Tuple of (x, y) coordinates of the weighted centroid,
        or None if no bright spot found
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Find maximum brightness
    max_val = np.max(blurred)

    # If image is too dark, return None
    if max_val < 50:  # Minimum overall brightness
        return None

    # Create a mask to focus only on bright pixels
    # Use adaptive threshold based on image's maximum brightness
    adaptive_threshold = max(min_brightness, max_val // 2)
    mask = blurred > adaptive_threshold

    # If no pixels above threshold, return None
    if not np.any(mask):
        return None

    # Apply mask to the blurred image
    masked = blurred.copy()
    masked[~mask] = 0

    # Get total brightness of masked pixels
    total_brightness = np.sum(masked)

    # Avoid division by zero
    if total_brightness == 0:
        return None

    # Get image dimensions
    height, width = blurred.shape

    # Create coordinate grids
    y_coords, x_coords = np.mgrid[0:height, 0:width]

    # Calculate weighted centroid using only masked (bright) pixels
    weighted_x = np.sum(x_coords * masked) / total_brightness
    weighted_y = np.sum(y_coords * masked) / total_brightness

    return (int(weighted_x), int(weighted_y))
