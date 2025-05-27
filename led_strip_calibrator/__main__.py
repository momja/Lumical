"""
Main entry point for the LED strip calibrator.

This module provides a command-line interface to the calibration process.
The process command expects images to be named in the format 'led_X.jpg'
where X is the LED index (0, 1, 2, etc.).
"""
import argparse
import sys
from pathlib import Path

from led_strip_calibrator.interactive import main as interactive_main
from led_strip_calibrator.process import main as process_main


def main() -> None:
    """Execute the calibration process from command line arguments."""
    parser = argparse.ArgumentParser(description="LED Strip Calibration Tool")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Process command
    process_parser = subparsers.add_parser(
        "process", help="Process calibration images (named led_0.jpg, led_1.jpg, etc.)"
    )
    process_parser.add_argument(
        "image_dir",
        help="Directory containing LED calibration images (named led_0.jpg, led_1.jpg, etc.)"
    )
    process_parser.add_argument(
        "--output", "-o",
        default="led_calibration.json",
        help="Output JSON file path"
    )
    process_parser.add_argument(
        "--method", "-m",
        choices=["threshold", "weighted"],
        default="weighted",
        help="Centroid detection method"
    )
    process_parser.add_argument(
        "--visualize", "-v",
        action="store_true",
        help="Create overlay visualizations on original images"
    )
    process_parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=200,
        help="Brightness threshold (0-255) for the threshold method (default: 200)"
    )

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Start interactive drawing web interface"
    )
    interactive_parser.add_argument(
        "--calibration", "-c",
        default="led_calibration.json",
        help="Path to LED calibration JSON file"
    )
    interactive_parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind server to"
    )
    interactive_parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port to bind server to"
    )

    # Verify command
    verify_parser = subparsers.add_parser(
        "verify", help="Verify the calibration file"
    )
    verify_parser.add_argument(
        "calibration_file",
        help="Calibration CSV file to verify"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "process":
        if not Path(args.image_dir).exists():
            print(f"Error: Image directory '{args.image_dir}' does not exist")
            sys.exit(1)

        process_main(args.image_dir, args.output, args.method, args.visualize, args.threshold)

    elif args.command == "interactive":
        if not Path(args.calibration).exists():
            print(f"Error: Calibration file '{args.calibration}' does not exist")
            print("Run 'uv run -m led_strip_calibrator process <image_dir>' first to generate calibration data")
            sys.exit(1)

        interactive_main(args.calibration, args.host, args.port)

    elif args.command == "verify":
        # Placeholder for verify command
        print(f"Verifying calibration file: {args.calibration_file}")
        print("Verification functionality not yet implemented")


if __name__ == "__main__":
    main()
