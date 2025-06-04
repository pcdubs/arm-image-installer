import os
import subprocess
import pathlib
import logging
import sys

logger = logging.getLogger("arm-image-installer-uboot")

# Aliases for convenience
BOARD_ALIASES = {
    "rpi4": "RaspberryPi4-64",
    "pi4": "RaspberryPi4-64",
    "rpi3": "RaspberryPi3-64",
    "pi3": "RaspberryPi3-64",
    "x13s": "Thinkpad-X13s",
}

# Unified U-Boot table (per-board boot offsets & filenames)
BOARD_UBOOT_MAP = {
    # Allwinner (A64 etc.)
    "pine64_plus": { "filename": "u-boot-sunxi-with-spl.bin", "seek": 8 },
    "nanopi_a64":  { "filename": "u-boot-sunxi-with-spl.bin", "seek": 8 },
    "bananapi_m64": { "filename": "u-boot-sunxi-with-spl.bin", "seek": 8 },
    "sopine_baseboard": { "filename": "u-boot-sunxi-with-spl.bin", "seek": 8 },

    # Rockchip (rk3399 family, seek=64)
    "rockpro64-rk3399": { "filename": "idbloader.img", "seek": 64 },
    "nanopi-r4s-rk3399": { "filename": "idbloader.img", "seek": 64 },
    "rock-pi-4-rk3399": { "filename": "idbloader.img", "seek": 64 },

    # TI AM625 (seek=64 example)
    "beagleplay": { "filename": "tiboot3.bin", "seek": 64 },

    # Raspberry Pi: no u-boot handling required (bootloader embedded in image)
    "RaspberryPi4-64": None,
    "RaspberryPi3-64": None,

    # QCom (x13s etc): no u-boot handling required
    "Thinkpad-X13s": None,
}

UBOOT_DIR_HOST = pathlib.Path("/usr/share/uboot")

def install_uboot(target, media, root_mount, dry_run=False):
    normalized = BOARD_ALIASES.get(target, target)

    uboot_entry = BOARD_UBOOT_MAP.get(normalized)
    if uboot_entry is None:
        logger.info(f"No U-Boot installation required for board {normalized}. Skipping.")
        return

    filename = uboot_entry["filename"]
    seek = uboot_entry["seek"]

    # Preferred: extract u-boot file directly from image root
    image_uboot_path = pathlib.Path(root_mount) / "usr/share/uboot" / normalized / filename
    host_uboot_path = UBOOT_DIR_HOST / normalized / filename

    if image_uboot_path.exists():
        uboot_bin = image_uboot_path
        logger.info(f"Found U-Boot inside image at {uboot_bin}")
    elif host_uboot_path.exists():
        uboot_bin = host_uboot_path
        logger.info(f"Found U-Boot on host at {uboot_bin}")
    else:
        logger.error(f"Required U-Boot binary '{filename}' not found for board {normalized}.")
        logger.error("Try: sudo dnf install uboot-images-armv8")
        sys.exit(1)

    logger.info(f"Writing U-Boot {filename} to {media} at offset seek={seek}")

    if dry_run:
        logger.info(f"[DRY-RUN] Would execute: dd if={uboot_bin} of={media} bs=1024 seek={seek}")
        return

    try:
        subprocess.run([
            "dd",
            f"if={uboot_bin}",
            f"of={media}",
            "bs=1024",
            f"seek={seek}",
            "conv=fsync"
        ], check=True)
        logger.info("U-Boot written successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to write U-Boot with dd: {e}")
        sys.exit(1)

def get_default_console(target: str, image_path: str) -> str:
    normalized = BOARD_ALIASES.get(target, target)

    if normalized == "RaspberryPi4-64":
        if "IoT" in image_path or "Server" in image_path:
            return "ttyS0,115200"
        else:
            return "ttyS1,115200"

    return "ttyAMA0,115200"

