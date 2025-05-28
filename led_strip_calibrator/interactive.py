"""
Interactive drawing interface for LED strip control.

This module provides a web-based canvas interface for drawing and mapping
pixel colors to LED positions using calibration data.
"""

from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

from led_strip_calibrator.led_calibration_data import LEDCalibrationData

# Flask web application
app = Flask(__name__)

# Global variables for the application state
calibration_data: Optional[LEDCalibrationData] = None


@app.route("/")
def index():
    """Serve the main drawing interface."""
    return render_template("drawing.html")


@app.route("/led_positions")
def get_led_positions():
    """Return normalized LED positions for visualization."""
    if not calibration_data:
        return jsonify({"error": "Calibration data not loaded"}), 400

    return jsonify(
        {
            "positions": calibration_data.normalized_positions,
            "count": len(calibration_data.normalized_positions),
        }
    )


@app.route("/add_led", methods=["POST"])
def add_led():
    """Add a new LED position to the calibration."""
    global calibration_data

    if not calibration_data:
        return jsonify({"error": "Calibration data not initialized"}), 400

    request_data = request.json
    led_index = request_data.get("led_index")
    x = request_data.get("x")
    y = request_data.get("y")

    if led_index is None or x is None or y is None:
        return jsonify({"error": "Missing required parameters: led_index, x, y"}), 400

    try:
        # Use the add_led method to handle coordinate conversion
        raw_x, raw_y = calibration_data.add_led(led_index, x, y)

        print(f"Added LED {led_index} at normalized position ({x:.3f}, {y:.3f})")

        return jsonify({"success": True, "led_index": led_index, "x": x, "y": y})

    except Exception as e:
        return jsonify({"error": f"Failed to add LED: {str(e)}"}), 500


def create_app() -> Flask:
    """Create and configure the Flask application."""
    global calibration_data
    calibration_data = LEDCalibrationData()
    return app


def main(
    calibration_file: str = "led_calibration.json",
    host: str = "localhost",
    port: int = 5000,
):
    """Run the interactive LED drawing server."""
    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Set Flask template folder
    app.template_folder = str(templates_dir)

    # Initialize the application
    create_app()

    print("Starting LED interactive drawing server...")
    print(f"Open your browser to: http://{host}:{port}")

    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LED Interactive Drawing Interface")
    parser.add_argument(
        "--calibration",
        "-c",
        default="led_calibration.json",
        help="Path to LED calibration JSON file",
    )
    parser.add_argument("--host", default="localhost", help="Host to bind server to")
    parser.add_argument(
        "--port", "-p", type=int, default=5000, help="Port to bind server to"
    )

    args = parser.parse_args()
    main(args.calibration, args.host, args.port)
