"""
Interactive drawing interface for LED strip control.

This module provides a web-based canvas interface for drawing and mapping
pixel colors to LED positions using calibration data.
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from flask import Flask, jsonify, render_template, request


class LEDCalibrationData:
    """Handle LED calibration data loading and normalization."""
    
    def __init__(self, calibration_file: str):
        """Initialize with calibration data from CSV file."""
        self.led_positions: Dict[int, Tuple[float, float]] = {}
        self.image_width: int = 0
        self.image_height: int = 0
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


class PixelToLEDMapper:
    """Map canvas pixel coordinates to nearest LEDs using KNN."""
    
    def __init__(self, calibration_data: LEDCalibrationData, k: int = 3, max_radius: float = 1.0):
        """Initialize KNN mapper with calibration data."""
        self.calibration_data = calibration_data
        self.k = k
        self.max_radius = max_radius
        self.setup_mapping()
    
    def setup_mapping(self) -> None:
        """Setup LED mapping with position data."""
        # Extract normalized positions as coordinate arrays
        self.led_indices = list(self.calibration_data.normalized_positions.keys())
        positions = list(self.calibration_data.normalized_positions.values())
        
        if not positions:
            raise ValueError("No LED positions available for mapping")
            
        self.led_coordinates = np.array(positions)
        
        print(f"Mapper initialized with {len(positions)} LEDs, k={self.k}, max_radius={self.max_radius}")
    
    def update_parameters(self, k: int = None, max_radius: float = None) -> None:
        """Update mapping parameters without reinitializing the entire mapper."""
        if k is not None:
            self.k = k
        if max_radius is not None:
            self.max_radius = max_radius
        print(f"Mapper parameters updated: k={self.k}, max_radius={self.max_radius}")
    
    def map_pixel_to_leds(
        self, x: float, y: float, k: int = None, max_radius: float = None
    ) -> List[Tuple[int, float]]:
        """
        Map a normalized pixel coordinate to nearest LEDs using distance calculation.
        
        Args:
            x: Normalized x coordinate (0-1)
            y: Normalized y coordinate (0-1)
            k: Override number of nearest neighbors (optional)
            max_radius: Override maximum distance threshold (optional)
            
        Returns:
            List of (led_index, distance) tuples sorted by distance, filtered by max_radius
        """
        # Use provided parameters or fall back to instance defaults
        effective_k = k if k is not None else self.k
        effective_max_radius = max_radius if max_radius is not None else self.max_radius
        
        pixel_coord = np.array([x, y])
        
        # Calculate Euclidean distances to all LEDs
        distances = []
        for i, led_coord in enumerate(self.led_coordinates):
            distance = np.sqrt(np.sum((pixel_coord - led_coord) ** 2))
            
            # Only include LEDs within the max radius
            if distance <= effective_max_radius:
                distances.append((self.led_indices[i], distance))
        
        # Sort by distance and return top k
        distances.sort(key=lambda x: x[1])
        return distances[:min(effective_k, len(distances))]


class LEDColorController:
    """Determine LED colors based on drawing data."""
    
    def __init__(self, mapper: PixelToLEDMapper):
        """Initialize with pixel-to-LED mapper."""
        self.mapper = mapper
        self.led_colors: Dict[int, Tuple[int, int, int]] = {}
    
    def update_colors_from_drawing(
        self, drawing_data: List[Dict], k: int = None, max_radius: float = None
    ) -> Dict[int, Tuple[int, int, int]]:
        """
        Update LED colors based on canvas drawing data.
        
        Args:
            drawing_data: List of drawing points with x, y, and color
            k: Override number of nearest neighbors (optional)
            max_radius: Override maximum distance threshold (optional)
            
        Returns:
            Dictionary mapping LED index to RGB color
        """
        # Reset LED colors
        self.led_colors = {}
        # Store color and weight pairs for each LED
        led_color_accumulator: Dict[int, List[Tuple[Tuple[int, int, int], float]]] = {}
        
        for point in drawing_data:
            x, y = point['x'], point['y']
            r, g, b = point['r'], point['g'], point['b']
            
            # Find nearest LEDs for this pixel using provided parameters
            nearest_leds = self.mapper.map_pixel_to_leds(x, y, k=k, max_radius=max_radius)
            
            # Collect colors and weights for proper weighted averaging
            for led_index, distance in nearest_leds:
                # Use inverse distance weighting (avoid division by zero)
                weight = 1.0 / (distance + 0.001)
                
                if led_index not in led_color_accumulator:
                    led_color_accumulator[led_index] = []
                
                # Store the original color and its weight
                led_color_accumulator[led_index].append(((r, g, b), weight))
        
        # Calculate proper weighted average for each LED
        for led_index, color_weight_pairs in led_color_accumulator.items():
            if color_weight_pairs:
                total_weight = sum(weight for _, weight in color_weight_pairs)
                
                if total_weight > 0:
                    # Calculate weighted average
                    weighted_r = sum(color[0] * weight for color, weight in color_weight_pairs)
                    weighted_g = sum(color[1] * weight for color, weight in color_weight_pairs)
                    weighted_b = sum(color[2] * weight for color, weight in color_weight_pairs)
                    
                    # Normalize by total weight to get proper average
                    avg_r = int(weighted_r / total_weight)
                    avg_g = int(weighted_g / total_weight)
                    avg_b = int(weighted_b / total_weight)
                    
                    # Clamp to valid RGB range
                    avg_r = max(0, min(255, avg_r))
                    avg_g = max(0, min(255, avg_g))
                    avg_b = max(0, min(255, avg_b))
                    
                    self.led_colors[led_index] = (avg_r, avg_g, avg_b)
        
        return self.led_colors


# Flask web application
app = Flask(__name__)

# Global variables for the application state
calibration_data: Optional[LEDCalibrationData] = None
mapper: Optional[PixelToLEDMapper] = None
color_controller: Optional[LEDColorController] = None


@app.route('/')
def index():
    """Serve the main drawing interface."""
    return render_template('drawing.html')


@app.route('/led_positions')
def get_led_positions():
    """Return normalized LED positions for visualization."""
    if not calibration_data:
        return jsonify({'error': 'Calibration data not loaded'}), 400
    
    return jsonify({
        'positions': calibration_data.normalized_positions,
        'count': len(calibration_data.normalized_positions)
    })


@app.route('/update_colors', methods=['POST'])
def update_colors():
    """Update LED colors based on canvas drawing data."""
    if not color_controller:
        return jsonify({'error': 'Color controller not initialized'}), 400
    
    request_data = request.json
    drawing_data = request_data.get('drawing_data', [])
    k = request_data.get('k')
    max_radius = request_data.get('max_radius')
    
    if not drawing_data:
        return jsonify({'led_colors': {}})
    
    led_colors = color_controller.update_colors_from_drawing(drawing_data, k=k, max_radius=max_radius)
    
    # Convert to format suitable for JSON
    colors_json = {
        str(led_index): {'r': r, 'g': g, 'b': b}
        for led_index, (r, g, b) in led_colors.items()
    }
    
    return jsonify({'led_colors': colors_json})


@app.route('/add_led', methods=['POST'])
def add_led():
    """Add a new LED position to the calibration."""
    global calibration_data, mapper, color_controller
    
    if not calibration_data:
        return jsonify({'error': 'Calibration data not initialized'}), 400
    
    request_data = request.json
    led_index = request_data.get('led_index')
    x = request_data.get('x')
    y = request_data.get('y')
    
    if led_index is None or x is None or y is None:
        return jsonify({'error': 'Missing required parameters: led_index, x, y'}), 400
    
    try:
        # Add to normalized positions
        calibration_data.normalized_positions[led_index] = (x, y)
        
        # Convert back to original coordinates for raw positions
        raw_x = x * calibration_data.image_width
        raw_y = y * calibration_data.image_height
        calibration_data.led_positions[led_index] = (raw_x, raw_y)
        
        # Update the mapper with new LED positions
        mapper.setup_mapping()
        
        print(f"Added LED {led_index} at normalized position ({x:.3f}, {y:.3f})")
        
        return jsonify({'success': True, 'led_index': led_index, 'x': x, 'y': y})
        
    except Exception as e:
        return jsonify({'error': f'Failed to add LED: {str(e)}'}), 500


@app.route('/export_calibration')
def export_calibration():
    """Export current LED positions as calibration data."""
    if not calibration_data:
        return jsonify({'error': 'Calibration data not initialized'}), 400
    
    # Convert current positions to CSV format
    csv_data = []
    csv_data.append(['led_index', 'x', 'y'])
    
    for led_index in sorted(calibration_data.led_positions.keys()):
        x, y = calibration_data.led_positions[led_index]
        csv_data.append([led_index, int(x), int(y)])
    
    return jsonify({
        'csv_data': csv_data,
        'led_count': len(calibration_data.led_positions)
    })


def create_app(calibration_file: str = "led_calibration.csv") -> Flask:
    """Create and configure the Flask application."""
    global calibration_data, mapper, color_controller
    
    # Initialize calibration data
    calibration_data = LEDCalibrationData(calibration_file)
    
    # Initialize mapper
    mapper = PixelToLEDMapper(calibration_data, k=3)
    
    # Initialize color controller
    color_controller = LEDColorController(mapper)
    
    return app


def main(calibration_file: str = "led_calibration.csv", host: str = "localhost", port: int = 5000):
    """Run the interactive LED drawing server."""
    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Set Flask template folder
    app.template_folder = str(templates_dir)
    
    # Initialize the application
    create_app(calibration_file)
    
    print("Starting LED interactive drawing server...")
    print(f"Open your browser to: http://{host}:{port}")
    
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LED Interactive Drawing Interface")
    parser.add_argument(
        "--calibration", "-c",
        default="led_calibration.csv",
        help="Path to LED calibration CSV file"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind server to"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port to bind server to"
    )
    
    args = parser.parse_args()
    main(args.calibration, args.host, args.port)