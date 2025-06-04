import subprocess
import sys
import logging

logger = logging.getLogger("arm-image-installer-resize")

def safe_run(cmd: list, capture_output=False, dry_run=False):
    if dry_run:
        logger.info(f"[DRY-RUN] Would run: {' '.join(cmd)}")
        return None

    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
        if capture_output:
            logger.debug(f"stdout: {result.stdout}")
            logger.debug(f"stderr: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        if e.stdout:
            logger.error(f"stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"stderr: {e.stderr}")
        sys.exit(f"ERROR: Command failed with exit code {e.returncode}")

def detect_filesystem_type(device: str, dry_run: bool = False) -> str:
    if dry_run:
        logger.info(f"[DRY-RUN] Would detect filesystem type on {device}")
        return "ext4"
    else:
        result = safe_run(['blkid', '-o', 'value', '-s', 'TYPE', device], capture_output=True)
        fs_type = result.stdout.strip()
        logger.info(f"Detected filesystem type on {device}: {fs_type}")
        return fs_type

def find_btrfs_mountpoint(device: str, dry_run: bool = False) -> str:
    if dry_run:
        logger.info(f"[DRY-RUN] Would detect btrfs mountpoint for {device}")
        return "/mnt"
    result = safe_run(['findmnt', '-n', '-o', 'TARGET', device], capture_output=True)
    mountpoint = result.stdout.strip()
    if not mountpoint:
        sys.exit(f"ERROR: Unable to locate btrfs mountpoint for {device}")
    logger.info(f"Detected btrfs mountpoint for {device}: {mountpoint}")
    return mountpoint

def resize_root_partition(device: str, dry_run: bool = False):
    fs_type = detect_filesystem_type(device, dry_run=dry_run)

    if fs_type == "ext4":
        safe_run(["e2fsck", "-f", "-y", device], dry_run=dry_run)
        safe_run(["resize2fs", device], dry_run=dry_run)
        logger.info(f"ext4 filesystem resize completed successfully on {device}")
    elif fs_type == "xfs":
        safe_run(["xfs_growfs", device], dry_run=dry_run)
        logger.info(f"xfs filesystem resize completed successfully on {device}")
    elif fs_type == "btrfs":
        mountpoint = find_btrfs_mountpoint(device, dry_run=dry_run)
        safe_run(["btrfs", "filesystem", "resize", "max", mountpoint], dry_run=dry_run)
        logger.info(f"btrfs filesystem resize completed successfully on {device}")
    else:
        sys.exit(f"ERROR: Unsupported filesystem type {fs_type}")

