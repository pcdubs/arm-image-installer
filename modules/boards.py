import os
import logging

logger = logging.getLogger("arm-image-installer-boards")

# Path to supported boards file (keep relative to repo root)
SUPPORTED_BOARDS_FILE = os.path.join(os.path.dirname(__file__), "..", "SUPPORTED-BOARDS")

# Alias mapping (can be extended easily)
BOARD_ALIASES = {
    "rpi4": "RaspberryPi4-64",
    "pi4": "RaspberryPi4-64",
    "rpi3": "RaspberryPi3-64",
    "pi3": "RaspberryPi3-64",
    "x13s": "Thinkpad-X13s",
}

def load_supported_boards():
    boards = set()
    if not os.path.exists(SUPPORTED_BOARDS_FILE):
        logger.warning(f"SUPPORTED-BOARDS file not found at {SUPPORTED_BOARDS_FILE}. No board validation applied.")
        return boards

    with open(SUPPORTED_BOARDS_FILE, "r") as f:
        for line in f:
            clean_line = line.strip()
            if clean_line and not clean_line.endswith("Devices:"):
                boards.update(clean_line.split())
    return boards

def resolve_board(target):
    return BOARD_ALIASES.get(target, target)

def validate_board(target):
    canonical = resolve_board(target)
    boards = load_supported_boards()
    if boards and canonical not in boards:
        logger.error(f"Unsupported board: '{target}' (resolved as '{canonical}')")
        logger.error("Run with --listboards to see supported boards.")
        raise SystemExit(1)

def list_boards():
    if not os.path.exists(SUPPORTED_BOARDS_FILE):
        print("No boards found (SUPPORTED-BOARDS file missing).")
        return

    print("Supported Boards:")
    with open(SUPPORTED_BOARDS_FILE, "r") as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line:
                continue
            if clean_line.endswith("Devices:"):
                print(f"\n  {clean_line}")
            else:
                for board in clean_line.split():
                    print(f"    {board}")
