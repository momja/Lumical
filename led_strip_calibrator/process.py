"""
Main processing module for LED strip calibration.

This module handles processing a sequence of images to extract LED positions
and generate a calibration file.
"""
import csv
import io
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from led_strip_calibrator.centroid import find_brightest_point, find_led_center_weighted


def load_images(image_dir: str) -> Dict[int, np.ndarray]:
    """
    Load all calibration images from a directory.

    Expects image filenames to be in format: led_XX.jpg where XX is the LED number.

    Args:
        image_dir: Directory containing calibration images

    Returns:
        Dictionary mapping LED index to image array
    """
    images = {}
    image_path = Path(image_dir)

    # Find all image files
    for file_path in sorted(image_path.glob("led_*.jpg")):
        # Extract LED number from filename
        try:
            led_num = int(file_path.stem.split('_')[1])
            images[led_num] = cv2.imread(str(file_path))
            print(f"Loaded image for LED {led_num}")
        except (ValueError, IndexError) as e:
            print(f"Error parsing filename {file_path.name}: {e}")

    return images


def process_images(
    images: Dict[int, np.ndarray],
    method: str = "weighted",
    threshold: int = 200
) -> List[Tuple[int, Optional[Tuple[int, int]]]]:
    """
    Process all images to find LED centroids.

    Args:
        images: Dictionary mapping LED index to image array
        method: Detection method ('threshold' or 'weighted')
        threshold: Brightness threshold (0-255) for the threshold method

    Returns:
        List of tuples (led_index, (x, y)) where (x, y) is the centroid or None if not found
    """
    results = []

    for led_index, image in sorted(images.items()):
        print(f"Processing LED {led_index} with method: {method}")
        if method == "threshold":
            print(f"  Using threshold method with value: {threshold}")
            centroid = find_brightest_point(image, threshold=threshold)
        else:  # weighted
            print(f"  Using weighted method with minimum brightness: {threshold}")
            # Use the same threshold value for both methods, but with different meanings
            # For weighted method, it's the minimum brightness to consider
            centroid = find_led_center_weighted(image, min_brightness=threshold)

        results.append((led_index, centroid))

        if centroid:
            print(f"LED {led_index}: Found at position {centroid}")
        else:
            print(f"LED {led_index}: Not detected")

    return results


def save_calibration(
    results: List[Tuple[int, Optional[Tuple[int, int]]]], dimensions: Tuple[int, int], output_file: str
) -> None:
    """
    Save calibration results to a JSON file with CSV data and image dimensions.

    Args:
        results: List of tuples (led_index, (x, y))
        output_file: Path to output JSON file
    """

    # Create a string buffer for CSV data
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['led_index', 'x', 'y'])

    # Calculate image dimensions from the data
    for led_index, centroid in results:
        if centroid:
            writer.writerow([led_index, centroid[0], centroid[1]])
        else:
            writer.writerow([led_index, '', ''])

    # Get the CSV as a string
    csv_string = csv_buffer.getvalue()

    # Create JSON structure
    calibration_data = {
        "coords": csv_string,
        "height": dimensions[0],
        "width": dimensions[1]
    }

    # Write the JSON to the file
    with open(output_file, 'w') as f:
        json.dump(calibration_data, f, indent=2)


def visualize_results(
    results: List[Tuple[int, Optional[Tuple[int, int]]]],
    image_shape: Tuple[int, int],
    output_file: str,
    overlay_images: Optional[Dict[int, np.ndarray]] = None
) -> None:
    """
    Create a visualization of all LED positions.

    Args:
        results: List of tuples (led_index, (x, y))
        image_shape: (height, width) of the original images
        output_file: Path to output visualization image
        overlay_images: Optional dictionary of LED index to original image for overlay
    """
    # Create a blank image for default visualization
    height, width = image_shape
    visualization = np.zeros((height, width, 3), dtype=np.uint8)

    # Create blended composite if overlay images are provided
    if overlay_images:
        # Create directory for individual overlays
        overlay_dir = os.path.join(os.path.dirname(output_file), "overlays")
        os.makedirs(overlay_dir, exist_ok=True)

        # Create a blended composite of all images (using maximum value at each pixel)
        composite = np.zeros((height, width, 3), dtype=np.uint8)
        for led_index, image in overlay_images.items():
            # Extract only the bright parts of each image
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Threshold to find bright areas
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

            # Create mask
            mask = cv2.merge([thresh, thresh, thresh])

            # Apply mask to the original image
            masked = cv2.bitwise_and(image, mask)

            # Update composite using maximum value
            composite = np.maximum(composite, masked)

        # Create a darker version of the composite as background
        background = composite.copy()
        background = cv2.addWeighted(background, 0.3, np.zeros_like(background), 0, 0)

        # Save individual overlays and draw on composite
        for led_index, centroid in results:
            if centroid:
                x, y = centroid

                # Create individual overlay
                if led_index in overlay_images:
                    # Get original image
                    orig_img = overlay_images[led_index].copy()

                    # Draw the centroid on the original image
                    cv2.circle(orig_img, (x, y), 10, (0, 255, 0), 2)
                    cv2.putText(
                        orig_img,
                        f"LED {led_index}: ({x}, {y})",
                        (x + 15, y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                    # Save the overlay
                    overlay_path = os.path.join(overlay_dir, f"led_{led_index}_overlay.jpg")
                    cv2.imwrite(overlay_path, orig_img)
                    print(f"Overlay for LED {led_index} saved to {overlay_path}")

                # Draw centroids on the composite
                # Use color scale from blue to red based on LED index
                color_scale = int(255 * (led_index / max(1, len(results))))
                color = (color_scale, 255 - color_scale, 255)  # Cyan to magenta color gradient

                # Draw a circle at the LED position
                cv2.circle(composite, (x, y), 5, color, -1)

                # Add the LED index as text
                cv2.putText(
                    composite,
                    str(led_index),
                    (x + 8, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

        # Save the composite visualization
        composite_path = os.path.splitext(output_file)[0] + "_composite.jpg"
        cv2.imwrite(composite_path, composite)
        print(f"Composite visualization saved to {composite_path}")

        # Use composite as the main visualization
        visualization = composite

    # If no overlay images are provided, create a simple visualization
    else:
        # Draw points for each detected LED
        for led_index, centroid in results:
            if centroid:
                x, y = centroid

                # Draw a circle at the LED position
                cv2.circle(visualization, (x, y), 3, (0, 255, 0), -1)

                # Add the LED index as text
                cv2.putText(
                    visualization,
                    str(led_index),
                    (x + 5, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

    # Save the visualization
    cv2.imwrite(output_file, visualization)
    print(f"Visualization saved to {output_file}")


def main(
    image_dir: str,
    output_file: str = "led_calibration.json",
    method: str = "weighted",
    visualize: bool = False,
    threshold: int = 200
) -> None:
    """
    Main function to run the LED strip calibration process.

    Args:
        image_dir: Directory containing calibration images
        output_file: Path to output JSON file
        method: Detection method ('threshold' or 'weighted')
        visualize: Whether to create overlay visualizations on original images
        threshold: Brightness threshold (0-255) for the threshold method
    """
    # Load all images
    images = load_images(image_dir)

    if not images:
        print("No images found. Check image directory and naming format.")
        return

    # Debug information
    print(f"\nUsing method: {method}")
    print(f"Threshold value: {threshold}\n")

    # Process images to find LED positions
    results = process_images(images, method, threshold)

    # Assume all images have identical dimensions
    dimensions = images[0].shape

    # Save calibration data
    save_calibration(results, dimensions, output_file)

    # Create visualization
    first_image = next(iter(images.values()))
    visualization_path = os.path.splitext(output_file)[0] + "_visualization.png"

    # Pass original images if visualization is requested
    overlay_images = images if visualize else None

    visualize_results(
        results,
        (first_image.shape[0], first_image.shape[1]),
        visualization_path,
        overlay_images
    )

    if visualize:
        print("Overlay visualizations created in the 'overlays' directory")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LED Strip Calibration Tool")
    parser.add_argument(
        "image_dir",
        help="Directory containing LED calibration images"
    )
    parser.add_argument(
        "--output", "-o",
        default="led_calibration.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--method", "-m",
        choices=["threshold", "weighted"],
        default="weighted",
        help="Centroid detection method"
    )

    args = parser.parse_args()
    main(args.image_dir, args.output, args.method)
