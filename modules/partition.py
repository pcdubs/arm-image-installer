import os
import psutil
import subprocess
import sys
import logging
from contextlib import contextmanager

logger = logging.getLogger("arm-image-installer-partition")

SAFE_DEVICE_PREFIXES = ("/dev/sd", "/dev/mmcblk", "/dev/nvme")

def validate_media_device(device: str):
    if not any(device.startswith(prefix) for prefix in SAFE_DEVICE_PREFIXES):
        sys.exit(f"ERROR: The specified media device {device} does not appear to be a valid removable device.")

    if not os.path.exists(device):
        sys.exit(f"ERROR: Target device {device} does not exist.")

    partitions = [p.device for p in psutil.disk_partitions(all=True)]
    for p in partitions:
        if p.startswith(device):
            sys.exit(f"ERROR: {device} appears to be mounted or in use: {p}")

def find_partitions(media: str):
    result = subprocess.run(['lsblk', '-ln', '-o', 'NAME,PARTLABEL', media], capture_output=True, text=True, check=True)
    boot_part = None
    root_part = None

    for line in result.stdout.strip().splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        part_name = parts[0]
        label = parts[1] if len(parts) > 1 else ""
        full_device = f"/dev/{part_name}"
        if "boot" in label.lower():
            boot_part = full_device
        elif "root" in label.lower():
            root_part = full_device

    # Fedora assumption fallback
    if not boot_part or not root_part:
        boot_part = f"{media}2"
        root_part = f"{media}3"

    return boot_part, root_part

def grow_partition(device: str, dry_run: bool = False):
    """
    Resize partition 3 to fill device (Fedora layout assumption).
    """
    logger.info(f"Resizing partition 3 on {device} to fill device")

    cmd = ["parted", "--script", device, "resizepart", "3", "100%"]

    if dry_run:
        logger.info(f"[DRY-RUN] Would run: {' '.join(cmd)}")
        return

    try:
        subprocess.run(cmd, check=True)
        logger.info("Partition 3 successfully resized to fill device")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to resize partition 3: {e}")
        raise

@contextmanager
def mounted_partition(device: str, mount_point: str, dry_run: bool):
    if dry_run:
        logger.info(f"[DRY-RUN] Would mount {device} to {mount_point}")
        yield
        logger.info(f"[DRY-RUN] Would unmount {mount_point}")
    else:
        subprocess.run(["mount", device, mount_point], check=True)
        try:
            yield
        finally:
            subprocess.run(["umount", mount_point], check=True)
