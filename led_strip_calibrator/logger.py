# logger.py
import logging
import os
from pathlib import Path


def setup_logger():
    # Create logs directory in user's home if it doesn't exist
    log_dir = Path(Path.home(), "logs", "seqfab")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Full path for the log file
    log_path = Path(log_dir, "seqfab.log")

    # Create a logger
    logger = logging.getLogger("seqfab")
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels of logs

    # Create a file handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)

    # Create an additional stream handler to log to stdout
    stdout_handler = logging.StreamHandler(stream=os.sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)

    # Create a formatting configuration
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    stdout_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

    return logger


# Global logger instance
logger = setup_logger()
