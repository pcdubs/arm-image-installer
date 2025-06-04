#!/usr/bin/env python3

import argparse
import os
import sys
import shutil
import tempfile
import logging
import pathlib
import subprocess
import lzma

from modules import partition, resize, config, uboot, boards

logger = logging.getLogger("arm-image-installer")
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.setLevel(logging.INFO)

def validate_image_format(image_path: str):
    if image_path.endswith('.xz') or image_path.endswith('.raw') or '.' not in pathlib.Path(image_path).name:
        return
    sys.exit("ERROR: Unsupported image format. Only .xz compressed or raw images are supported.")

def is_iot_image(image_path: str):
    return "IoT" in os.path.basename(image_path)

def stream_write_image(image_path: str, device: str, dry_run: bool = False):
    validate_image_format(image_path)
    if dry_run:
        logger.info(f"[DRY-RUN] Would write image {image_path} directly to {device}")
        return

    logger.info(f"Streaming image to {device}")
    if image_path.endswith('.xz'):
        opener = lzma.open
    else:
        opener = open

    with opener(image_path, 'rb') as f_in, open(device, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

    logger.info("Image writing completed successfully.")

def parse_args():
    parser = argparse.ArgumentParser(description="ARM Image Installer")

    required = parser.add_argument_group("Required arguments")
    required.add_argument('--image', help="Path to compressed disk image (.xz or raw only)")
    required.add_argument('--media', help="Target block device (e.g., /dev/sdX, /dev/mmcblkX, /dev/nvmeXnY)")
    required.add_argument('--target', help="Target board name or alias")

    config_group = parser.add_argument_group("Optional configuration")
    config_group.add_argument('--addkey', help="Path to SSH public key to inject for root user")
    config_group.add_argument('--norootpass', action='store_true', help="Remove root password for passwordless root login")
    config_group.add_argument('--relabel', action='store_true', help="Create .autorelabel for SELinux relabeling on first boot")
    config_group.add_argument('--resizefs', action='store_true', help="Resize root filesystem to fill device")
    config_group.add_argument('--wifi-ssid', help="Wi-Fi SSID to configure")
    config_group.add_argument('--wifi-pass', help="Wi-Fi password to configure")
    config_group.add_argument('--wifi-security', choices=['wpa-psk', 'sae'], default='wpa-psk',
                               help="Wi-Fi security type (wpa-psk or sae)")

    boot_group = parser.add_argument_group("Bootloader options")
    boot_group.add_argument('--addconsole', action='store_true', help="Add default serial console to kernel command line")
    boot_group.add_argument('--args', help="Additional kernel arguments to append to kernel command line")
    boot_group.add_argument('--showboot', action='store_true', help="Show boot messages (remove rhgb quiet)")
    boot_group.add_argument('--sysrq', action='store_true', help="Enable kernel sysrq (sysrq_always_enabled=1)")

    iot_group = parser.add_argument_group("IoT-specific options")
    iot_group.add_argument('--ign-url', help="Ignition configuration URL for Fedora IoT installs")

    misc_group = parser.add_argument_group("Other options")
    misc_group.add_argument('-y', '--assumeyes', action='store_true', help="Assume yes, skip confirmation prompt")
    misc_group.add_argument('--listboards', action='store_true', help="List all supported boards")
    misc_group.add_argument('--dry-run', action='store_true', help="Run without making any changes to media (safe test)")
    misc_group.add_argument('--debug', action='store_true', help="Enable verbose debug output")

    args = parser.parse_args()

    if not args.listboards:
        missing = []
        if not args.image:
            missing.append("--image")
        if not args.media:
            missing.append("--media")
        if not args.target:
            missing.append("--target")
        if missing:
            parser.error(f"the following arguments are required: {', '.join(missing)}")

    return args

def print_summary_and_confirm(args, iot_image, canonical_board):
    logger.info("====================================================")
    logger.info("ARM Image Installer Summary")
    logger.info(f"Image file        : {args.image}")
    logger.info(f"Target device     : {args.media}")
    logger.info(f"Target board      : {canonical_board}")
    logger.info(f"IoT image         : {'Yes' if iot_image else 'No'}")
    if args.addkey:
        logger.info(f"SSH key           : {args.addkey}")
    if args.norootpass:
        logger.info(f"Remove root pass  : Yes")
    if args.relabel:
        logger.info(f"SELinux relabel   : Yes")
    if args.resizefs:
        logger.info(f"Resize filesystem : Yes")
    if args.wifi_ssid:
        logger.info(f"Wi-Fi SSID        : {args.wifi_ssid}")
        logger.info(f"Wi-Fi Security    : {args.wifi_security}")
    if args.addconsole:
        logger.info(f"Add serial console: Yes")
    if args.args:
        logger.info(f"Extra kernel args : {args.args}")
    if args.showboot:
        logger.info(f"Show boot messages: Yes")
    if args.sysrq:
        logger.info("Enable sysrq      : Yes")
    if args.ign_url:
        logger.info(f"Ignition URL      : {args.ign_url}")
    logger.info(f"Dry run mode      : {'Yes' if args.dry_run else 'No'}")
    logger.info("====================================================")

    if not args.dry_run and not args.assumeyes:
        confirm = input(f"\n*** WARNING: ALL DATA ON {args.media} WILL BE DESTROYED. CONTINUE? (y/N): ").strip().lower()
        if confirm not in ('y', 'yes'):
            logger.info("Aborted by user.")
            sys.exit(1)

def main():
    args = parse_args()

    if args.listboards:
        boards.list_boards()
        sys.exit(0)

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled.")

    if os.geteuid() != 0:
        sys.exit("ERROR: This script must be run as root (sudo).")

    canonical_board = boards.resolve_board(args.target)
    boards.validate_board(args.target)

    iot_image = is_iot_image(args.image)

    print_summary_and_confirm(args, iot_image, canonical_board)

    partition.validate_media_device(args.media)
    stream_write_image(args.image, args.media, dry_run=args.dry_run)

    boot_part, root_part = partition.find_partitions(args.media)

    with tempfile.TemporaryDirectory() as tempdir:
        boot_mount = os.path.join(tempdir, "boot")
        root_mount = os.path.join(tempdir, "root")
        os.makedirs(boot_mount)
        os.makedirs(root_mount)

        if args.dry_run:
            logger.info("[DRY-RUN] Would mount partitions and apply configurations.")
        else:
            with partition.mounted_partition(boot_part, boot_mount, args.dry_run), \
                 partition.mounted_partition(root_part, root_mount, args.dry_run):
                config.apply_post_write_configs(root_mount, args, is_iot=iot_image, dry_run=args.dry_run)
                config.apply_bootloader_configs(boot_mount, args, is_iot=iot_image, dry_run=args.dry_run)
                uboot.install_uboot(canonical_board, args.media, root_mount, dry_run=args.dry_run)

        if args.resizefs:
            partition.grow_partition(args.media, dry_run=args.dry_run)
            resize.resize_root_partition(root_part, dry_run=args.dry_run)

    logger.info("Image installation completed successfully.")

if __name__ == "__main__":
    main()
