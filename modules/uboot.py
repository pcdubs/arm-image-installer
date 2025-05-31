import os
import subprocess
import pathlib
import logging

logger = logging.getLogger("arm-image-installer-uboot")

BOARD_ALIASES = {
    "rpi4": "RaspberryPi4-64",
    "pi4": "RaspberryPi4-64",
    "rpi3": "RaspberryPi3-64",
    "pi3": "RaspberryPi3-64",
    "x13s": "Thinkpad-X13s",
}

BOARDS_DIR = pathlib.Path("boards.d")

def install_uboot(target, root_mount, dry_run=False):
    normalized = BOARD_ALIASES.get(target, target)
    board_script = BOARDS_DIR / normalized

    if not board_script.exists():
        return

    if dry_run:
        logger.info(f"[DRY-RUN] Would execute U-Boot board script: {board_script}")
        return

    try:
        subprocess.run(["bash", str(board_script), root_mount], check=True)
        logger.info(f"U-Boot installation script executed for board: {normalized}")
    except subprocess.CalledProcessError as e:
        logger.error(f"U-Boot script failed for board {normalized}: {e}")
        raise

def get_default_console(target: str, image_path: str) -> str:
    """
    Returns the default serial console for the given board based on image type.
    """
    normalized = BOARD_ALIASES.get(target, target)

    if normalized == "RaspberryPi4-64":
        if "IoT" in image_path or "Server" in image_path:
            return "ttyS0,115200"
        else:
            return "ttyS1,115200"

    # Default fallback console
    return "ttyAMA0,115200"
