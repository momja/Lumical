"""
Interactive drawing interface for LED strip control with canvas isolation.

This module provides a web-based canvas interface for drawing and mapping
pixel colors to LED positions using calibration data. Each canvas instance
is uniquely identified and isolated from others.

Canvas Isolation System:
    - Canvas Type: 'drawing' (dashboard) or 'sign' (display interface)
    - Canvas ID: Sequential numeric identifier (1, 2, 3, etc.)

URL Structure:
    - / → Drawing dashboard with canvas ID 1 (default)
    - /?canvas_id=<id> → Drawing dashboard with full LED controls (multi-user)
    - /sign → Sign display interface with canvas ID 1 (default)
    - /sign?canvas_id=<id> → Sign display interface (multi-user)

Multi-User Behavior:
    - Base URLs (/ and /sign) use canvas ID 1 by default
    - Multiple users can collaborate on the same canvas ID
    - Direct access to specific IDs (e.g., /?canvas_id=5, /sign?canvas_id=3) works directly
    - Each canvas ID maintains its own isolated state

Data Isolation:
    - Each canvas type + ID has separate canvas data and LED positions
    - WebSocket rooms ensure real-time updates only reach same canvas clients
    - No cross-contamination between different canvas instances

Examples:
    - Multiple users on /?canvas_id=1 collaborate on the same drawing canvas
    - /?canvas_id=1 and /?canvas_id=2 are separate drawing canvases with different data
    - /sign?canvas_id=1 and /sign?canvas_id=2 are separate sign canvases
    - /?canvas_id=1 and /sign?canvas_id=1 are completely isolated from each other
"""

import atexit
import base64
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room

from led_strip_calibrator.led_calibration_data import LEDCalibrationData
from led_strip_calibrator.logger import logger

# Flask web application
app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_PERMANENT"] = False  # Sessions expire when the browser is closed

# Create SocketIO instance
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow all origins for testing

# Global variables for the application state
calibration_data: Optional[LEDCalibrationData] = None

# Thread-safe queue for handling multi-threaded server requests
# This allows us to synchronize the user experience across all clients
deltaMessageQueue = queue.Queue(
    maxsize=100
)  # Limit queue size to prevent memory issues

# Canvas data isolation system
# Each canvas type (drawing/sign) and ID combination has its own isolated state
# Format: canvas_states[canvas_type][canvas_id] = {canvas_data, led_data}
canvas_states = {
    "drawing": {},  # Drawing dashboard canvases: /?canvas_id=1, /?canvas_id=2, etc.
    "sign": {},  # Sign display canvases: /sign?canvas_id=1, /sign?canvas_id=2, etc.
}
canvas_states_lock = threading.Lock()

# Legacy global state (deprecated - use canvas_states instead)
master_canvas = None
master_canvas_lock = threading.Lock()

# Thread control
worker_thread = None
shutdown_flag = None


def initialize_canvas_state(canvas_type: str, canvas_id: int):
    """Initialize canvas state for a new canvas ID if it doesn't exist.

    Args:
        canvas_type: Either 'drawing' or 'sign'
        canvas_id: Unique identifier for this canvas instance
    """
    with canvas_states_lock:
        if canvas_id not in canvas_states[canvas_type]:
            canvas_states[canvas_type][canvas_id] = {
                "canvas_data": None,  # OpenCV image data
                "led_positions": {},  # LED position data for this canvas
                "created_at": time.time(),
            }
            logger.info(f"Initialized new {canvas_type} canvas with ID {canvas_id}")


@app.route("/")
def drawing_canvas():
    """Serve the drawing interface for a specific canvas ID.

    Multiple users can access the same canvas ID for collaborative editing.

    Args:
        canvas_id: Unique identifier from query parameter (defaults to 1)

    Examples:
        / - Drawing canvas with ID 1 (default)
        /?canvas_id=2 - Drawing canvas with ID 2 (isolated from ID 1)
    """
    # Get canvas_id from query parameter, default to 1
    canvas_id = request.args.get("canvas_id", 1, type=int)

    # Initialize client session if needed
    if "client_id" not in session:
        session["client_id"] = str(uuid.uuid4())

    # Set canvas context for this session
    session["canvas_type"] = "drawing"
    session["canvas_id"] = canvas_id

    # Initialize canvas state if this is a new canvas
    initialize_canvas_state("drawing", canvas_id)

    return render_template("drawing.html")


@app.route("/sign")
def sign_canvas():
    """Serve the sign interface for a specific canvas ID.

    Multiple users can access the same canvas ID for collaborative editing.

    Args:
        canvas_id: Unique identifier for this sign canvas instance (from query parameter)

    Examples:
        /sign?canvas_id=1 - Sign canvas with ID 1 (default)
        /sign?canvas_id=2 - Sign canvas with ID 2 (isolated from ID 1)
    """
    # Get canvas_id from query parameter, default to 1
    canvas_id = request.args.get("canvas_id", 1, type=int)

    # Initialize client session if needed
    if "client_id" not in session:
        session["client_id"] = str(uuid.uuid4())

    # Set canvas context for this session
    session["canvas_type"] = "sign"
    session["canvas_id"] = canvas_id

    # Initialize canvas state if this is a new canvas
    initialize_canvas_state("sign", canvas_id)

    return render_template("sign.html")


@app.route("/get_full_canvas")
def get_full_canvas():
    """Return the current full canvas state for the client's specific canvas.

    Uses the canvas_type and canvas_id from the client's session to return
    the correct isolated canvas state.
    """
    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if not canvas_type or not canvas_id:
        return jsonify(
            {"success": False, "message": "No canvas context in session"}
        ), 400

    with canvas_states_lock:
        # Get canvas state for this specific canvas
        if (
            canvas_type not in canvas_states
            or canvas_id not in canvas_states[canvas_type]
        ):
            return jsonify({"success": False, "message": "Canvas state not found"}), 404

        canvas_data = canvas_states[canvas_type][canvas_id]["canvas_data"]

        if canvas_data is None:
            return jsonify(
                {"success": False, "message": "No canvas data available"}
            ), 404

        # Convert the canvas to a data URL
        _, buffer = cv2.imencode(".png", canvas_data)
        img_str = base64.b64encode(buffer).decode("utf-8")
        data_url = f"data:image/png;base64,{img_str}"

        return jsonify(
            {"success": True, "fullStateImage": data_url, "timestamp": time.time()}
        )


@app.route("/led_positions")
def get_led_positions():
    """Return normalized LED positions for the client's specific canvas.

    Each canvas (drawing/sign + ID) has its own isolated LED position data.
    Falls back to global calibration_data if no canvas-specific data exists.
    """
    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if canvas_type and canvas_id:
        # Try to get canvas-specific LED positions
        with canvas_states_lock:
            if canvas_type in canvas_states and canvas_id in canvas_states[canvas_type]:
                led_positions = canvas_states[canvas_type][canvas_id]["led_positions"]
                if led_positions:
                    return jsonify(
                        {
                            "positions": led_positions,
                            "count": len(led_positions),
                            "canvas_type": canvas_type,
                            "canvas_id": canvas_id,
                        }
                    )

    # Fall back to global calibration data
    if not calibration_data:
        return jsonify({"error": "No LED position data available"}), 400

    return jsonify(
        {
            "positions": calibration_data.normalized_positions,
            "count": len(calibration_data.normalized_positions),
            "canvas_type": canvas_type or "unknown",
            "canvas_id": canvas_id or "unknown",
        }
    )


@app.route("/add_led", methods=["POST"])
def add_led():
    """Add a new LED position to the client's specific canvas.

    LEDs are stored per-canvas to maintain isolation between different
    drawing and sign instances.
    """
    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if not canvas_type or not canvas_id:
        return jsonify({"error": "No canvas context in session"}), 400

    request_data = request.json
    led_index = request_data.get("led_index")
    x = request_data.get("x")
    y = request_data.get("y")

    if led_index is None or x is None or y is None:
        return jsonify({"error": "Missing required parameters: led_index, x, y"}), 400

    try:
        # Store LED position in canvas-specific state
        with canvas_states_lock:
            if (
                canvas_type not in canvas_states
                or canvas_id not in canvas_states[canvas_type]
            ):
                initialize_canvas_state(canvas_type, canvas_id)

            canvas_states[canvas_type][canvas_id]["led_positions"][led_index] = [x, y]

        logger.info(
            f"Added LED {led_index} at ({x:.3f}, {y:.3f}) to {canvas_type} canvas {canvas_id}"
        )

        return jsonify(
            {
                "success": True,
                "led_index": led_index,
                "x": x,
                "y": y,
                "canvas_type": canvas_type,
                "canvas_id": canvas_id,
            }
        )

    except Exception as e:
        logger.error(f"Failed to add LED: {str(e)}")
        return jsonify({"error": f"Failed to add LED: {str(e)}"}), 500


def compute_led_colors(image):
    """Compute LED colors from the given image."""
    global calibration_data

    if not calibration_data:
        return {}

    # Apply Gaussian blur for smoother color sampling
    blurred = cv2.GaussianBlur(image, (15, 15), 0)

    # Get image dimensions
    height, width = blurred.shape[:2]

    # Sample colors for each LED position
    led_colors = {}

    for led_index, (
        norm_x,
        norm_y,
    ) in calibration_data.normalized_positions.items():
        # Convert normalized coordinates to pixel coordinates
        pixel_x = int(norm_x * width)
        pixel_y = int(norm_y * height)

        # Clamp coordinates to image bounds
        pixel_x = max(0, min(pixel_x, width - 1))
        pixel_y = max(0, min(pixel_y, height - 1))

        # Sample color at LED position (OpenCV uses BGR format)
        bgr_color = blurred[pixel_y, pixel_x]

        # Convert BGR to RGB and format as hex
        rgb_color = (int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0]))
        hex_color = f"#{rgb_color[0]:02x}{rgb_color[1]:02x}{rgb_color[2]:02x}"

        led_colors[led_index] = {
            "color": hex_color,
            "rgb": rgb_color,
            "position": {"x": norm_x, "y": norm_y},
        }

    return led_colors


def process_delta(client_id, file):
    """Process a pixel delta image and broadcast it to other clients"""
    global master_canvas

    try:
        # Read the delta image
        file_bytes = np.frombuffer(file.read(), np.uint8)
        delta_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if delta_image is None:
            logger.error("Failed to decode delta image")
            return None

        # Initialize or update the master canvas
        with master_canvas_lock:
            if (
                master_canvas is None
                or master_canvas.shape[:2] != delta_image.shape[:2]
            ):
                # Initialize with black background if not exists or size changed
                master_canvas = np.zeros(delta_image.shape, dtype=np.uint8)

            # Apply the delta to the master canvas (overlay the changes)
            # Only copy non-black pixels from delta to master
            non_black_mask = np.any(
                delta_image > 10, axis=2
            )  # Threshold to consider as drawn
            master_canvas[non_black_mask] = delta_image[non_black_mask]

            # Make a copy of the current master canvas state
            current_state = master_canvas.copy()

        # Convert both the delta and the full state to data URLs
        _, delta_buffer = cv2.imencode(".png", delta_image)
        delta_str = base64.b64encode(delta_buffer).decode("utf-8")
        delta_url = f"data:image/png;base64,{delta_str}"

        _, full_buffer = cv2.imencode(".png", current_state)
        full_str = base64.b64encode(full_buffer).decode("utf-8")
        full_url = f"data:image/png;base64,{full_str}"

        # Return data to be emitted via WebSocket
        return {
            "success": True,
            "deltaImage": delta_url,
            "fullStateImage": full_url,
            "client_id": client_id,
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error(f"Failed to process delta image: {str(e)}")
        return None


def render(client_id, file, update_type="full"):
    """Process either a full canvas update or a delta update"""

    if update_type == "delta":
        return process_delta(client_id, file)
    elif update_type == "clear":
        # Clear the master canvas
        global master_canvas
        with master_canvas_lock:
            if master_canvas is not None:
                # Create an empty canvas of the same size
                master_canvas = np.zeros(master_canvas.shape, dtype=np.uint8)

                # Convert the empty canvas to a data URL
                _, buffer = cv2.imencode(".png", master_canvas)
                img_str = base64.b64encode(buffer).decode("utf-8")
                data_url = f"data:image/png;base64,{img_str}"

                return {
                    "success": True,
                    "clear": True,
                    "fullStateImage": data_url,
                    "client_id": client_id,
                    "timestamp": time.time(),
                }
            else:
                logger.warning("Attempted to clear non-existent master canvas")
                return None

    # For full canvas updates, process for LED colors
    try:
        # Read the uploaded image
        file_bytes = np.frombuffer(file.read(), np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if image is None:
            logger.error("Failed to decode image")
            return None

        # Compute LED colors from the image
        led_colors = compute_led_colors(image)

        # Return data to be emitted via WebSocket
        return {
            "success": True,
            "led_colors": led_colors,
            "total_leds": len(led_colors),
            "client_id": client_id,
        }

    except Exception as e:
        logger.error(f"Failed to process image: {str(e)}")
        return None


def process_updates_worker():
    """
    Worker thread function that processes messages from deltaMessageQueue

    This runs in a separate thread to avoid blocking Flask request handlers.
    It continually pulls items from the queue and processes them in order,
    ensuring all clients see updates in the same sequence.
    """
    logger.info("Worker thread started")

    # Create application context for this thread
    with app.app_context():
        while not shutdown_flag.is_set():
            try:
                # Get item from queue with timeout
                client_id, file, update_type = deltaMessageQueue.get(timeout=1.0)
                try:
                    # Process the message based on update type
                    result = render(client_id, file, update_type)

                    # Emit update to all clients if processing was successful
                    if result:
                        socketio.emit("update", result)
                        logger.info(
                            f"Processed and emitted {update_type} update from client {client_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to process {update_type} update from client {client_id}"
                        )
                except Exception as e:
                    logger.error(f"Error processing update: {str(e)}")
                finally:
                    # Mark task as done regardless of success/failure
                    deltaMessageQueue.task_done()
            except queue.Empty:
                # Queue is empty, just continue
                continue
            except Exception as e:
                logger.error(f"Unexpected error in worker thread: {str(e)}")
                time.sleep(1)  # Prevent CPU spinning if there's a persistent error


def start_worker_thread():
    """Start the worker thread for processing updates"""
    global worker_thread, shutdown_flag

    if worker_thread is None or not worker_thread.is_alive():
        shutdown_flag = threading.Event()
        worker_thread = threading.Thread(target=process_updates_worker)
        worker_thread.daemon = (
            True  # Allow the thread to be terminated when the main process exits
        )
        worker_thread.start()
        logger.info("Started update processing worker thread")


def stop_worker_thread():
    """Stop the worker thread gracefully"""
    global worker_thread, shutdown_flag

    if shutdown_flag and worker_thread and worker_thread.is_alive():
        logger.info("Stopping worker thread...")
        shutdown_flag.set()
        worker_thread.join(timeout=5)
        logger.info("Worker thread stopped")


def create_app() -> Flask:
    """Create and configure the Flask application."""
    global calibration_data, master_canvas
    calibration_data = LEDCalibrationData("led_calibration.json")

    # Initialize an empty master canvas
    master_canvas = None

    # Start the worker thread for processing updates
    # Note: This is now primarily used for HTTP-based updates, as WebSocket updates
    # are processed directly in their respective event handlers
    start_worker_thread()

    # Register cleanup function
    atexit.register(stop_worker_thread)

    return app


# Socket.IO event handlers
@socketio.on("connect")
def handle_connect():
    """Handle client connection and send canvas-specific initial state.

    Each client gets the canvas state for their specific canvas type and ID.
    """
    logger.info(f"Client connected: {request.sid}")

    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if not canvas_type or not canvas_id:
        logger.warning(f"Client {request.sid} connected without canvas context")
        return

    logger.info(f"Client {request.sid} connected to {canvas_type} canvas {canvas_id}")

    # Join the client to a room for their specific canvas
    room_name = f"{canvas_type}_{canvas_id}"
    join_room(room_name)
    logger.info(f"Client {request.sid} joined room {room_name}")

    # Send canvas-specific initial state
    with canvas_states_lock:
        if (
            canvas_type in canvas_states
            and canvas_id in canvas_states[canvas_type]
            and canvas_states[canvas_type][canvas_id]["canvas_data"] is not None
        ):
            canvas_data = canvas_states[canvas_type][canvas_id]["canvas_data"]

            # Convert the canvas to a data URL
            _, buffer = cv2.imencode(".png", canvas_data)
            img_str = base64.b64encode(buffer).decode("utf-8")
            data_url = f"data:image/png;base64,{img_str}"

            # Compute LED colors from the current canvas state
            led_colors = compute_led_colors(canvas_data)

            # Send the initial state to just this client
            emit(
                "init_canvas",
                {
                    "success": True,
                    "fullStateImage": data_url,
                    "led_colors": led_colors,
                    "total_leds": len(led_colors),
                    "timestamp": time.time(),
                    "canvas_type": canvas_type,
                    "canvas_id": canvas_id,
                },
            )
        else:
            # No existing canvas data - send initial LED colors from empty canvas
            logger.info(
                f"No existing canvas data for {canvas_type} canvas {canvas_id}, sending default LED colors"
            )

            # Create a default empty canvas (black) for LED computation
            default_canvas = np.zeros((600, 800, 3), dtype=np.uint8)  # Black canvas

            # Compute LED colors from the empty canvas
            led_colors = compute_led_colors(default_canvas)

            # Send initial LED colors even with no canvas state
            emit(
                "init_canvas",
                {
                    "success": True,
                    "led_colors": led_colors,
                    "total_leds": len(led_colors),
                    "timestamp": time.time(),
                    "canvas_type": canvas_type,
                    "canvas_id": canvas_id,
                    "message": "New canvas initialized",
                },
            )


@socketio.on("disconnect")
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")


# Event when client sends an update via WebSocket
@socketio.on("client_delta")
def handle_client_delta(data):
    client_id = data.get("client_id")
    delta_image_base64 = data.get("delta_image")
    timestamp = data.get("timestamp", time.time())

    logger.info(f"Received delta from client {client_id} via WebSocket")

    if not delta_image_base64:
        logger.error(
            f"No delta image data in WebSocket message from client {client_id}"
        )
        return

    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if not canvas_type or not canvas_id:
        logger.error(f"No canvas context for client {client_id}")
        return

    try:
        # Decode the base64 image
        img_bytes = base64.b64decode(delta_image_base64)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        delta_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if delta_image is None:
            logger.error(f"Failed to decode delta image from client {client_id}")
            return

        # Process the delta and update the canvas-specific state
        with canvas_states_lock:
            # Initialize canvas state if it doesn't exist
            if (
                canvas_type not in canvas_states
                or canvas_id not in canvas_states[canvas_type]
            ):
                initialize_canvas_state(canvas_type, canvas_id)

            canvas_data = canvas_states[canvas_type][canvas_id]["canvas_data"]

            if canvas_data is None or canvas_data.shape[:2] != delta_image.shape[:2]:
                # Initialize with black background if not exists or size changed
                canvas_data = np.zeros(delta_image.shape, dtype=np.uint8)

            # Apply the delta to the canvas (overlay the changes)
            # Only copy non-black pixels from delta to canvas
            non_black_mask = np.any(
                delta_image > 10, axis=2
            )  # Threshold to consider as drawn
            canvas_data[non_black_mask] = delta_image[non_black_mask]

            # Update the canvas state
            canvas_states[canvas_type][canvas_id]["canvas_data"] = canvas_data

            # Make a copy of the current canvas state
            current_state = canvas_data.copy()

        # Convert both the delta and the full state to data URLs
        _, delta_buffer = cv2.imencode(".png", delta_image)
        delta_str = base64.b64encode(delta_buffer).decode("utf-8")
        delta_url = f"data:image/png;base64,{delta_str}"

        _, full_buffer = cv2.imencode(".png", current_state)
        full_str = base64.b64encode(full_buffer).decode("utf-8")
        full_url = f"data:image/png;base64,{full_str}"

        # Compute LED colors from the current canvas state
        led_colors = compute_led_colors(current_state)

        # Create a room name for this specific canvas
        room_name = f"{canvas_type}_{canvas_id}"

        # Emit the update to clients on the same canvas only
        emit(
            "update",
            {
                "success": True,
                "deltaImage": delta_url,
                "fullStateImage": full_url,
                "led_colors": led_colors,
                "total_leds": len(led_colors),
                "clientId": client_id,  # Changed to match frontend
                "timestamp": timestamp,
                "canvas_type": canvas_type,
                "canvas_id": canvas_id,
            },
            room=room_name,
        )

        # Send confirmation back to the sender
        emit("delta_received", {"success": True, "timestamp": time.time()})

    except Exception as e:
        logger.error(f"Error processing WebSocket delta: {str(e)}")
        emit(
            "delta_received",
            {"success": False, "error": str(e), "timestamp": time.time()},
        )


@socketio.on("clear_canvas")
def handle_clear_canvas(data):
    client_id = data.get("client_id")
    logger.info(f"Received clear canvas command from client {client_id}")

    # Get canvas context from session
    canvas_type = session.get("canvas_type")
    canvas_id = session.get("canvas_id")

    if not canvas_type or not canvas_id:
        logger.error(f"No canvas context for client {client_id}")
        return

    try:
        data_url = None

        # Clear the canvas-specific state
        with canvas_states_lock:
            # Initialize canvas state if it doesn't exist
            if (
                canvas_type not in canvas_states
                or canvas_id not in canvas_states[canvas_type]
            ):
                initialize_canvas_state(canvas_type, canvas_id)

            canvas_data = canvas_states[canvas_type][canvas_id]["canvas_data"]

            if canvas_data is not None:
                # Create an empty canvas of the same size
                empty_canvas = np.zeros(canvas_data.shape, dtype=np.uint8)
                canvas_states[canvas_type][canvas_id]["canvas_data"] = empty_canvas

                # Convert the empty canvas to a data URL
                _, buffer = cv2.imencode(".png", empty_canvas)
                img_str = base64.b64encode(buffer).decode("utf-8")
                data_url = f"data:image/png;base64,{img_str}"

        # Create a room name for this specific canvas
        room_name = f"{canvas_type}_{canvas_id}"

        if data_url:
            # Emit the clear command to all clients on the same canvas
            emit(
                "update",
                {
                    "success": True,
                    "clear": True,
                    "fullStateImage": data_url,
                    "clientId": client_id,  # Changed to match frontend
                    "timestamp": time.time(),
                    "canvas_type": canvas_type,
                    "canvas_id": canvas_id,
                },
                room=room_name,
            )

        # Send confirmation back to the sender
        emit("clear_received", {"success": True, "timestamp": time.time()})

    except Exception as e:
        logger.error(f"Error processing clear canvas command: {str(e)}")
        emit(
            "clear_received",
            {"success": False, "error": str(e), "timestamp": time.time()},
        )


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
    print("Using WebSockets for real-time communication")

    # run app with websockets
    try:
        # Use engineio_logger=True for debugging WebSocket communications if needed
        socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
    finally:
        # Ensure worker thread is stopped on shutdown
        stop_worker_thread()


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
