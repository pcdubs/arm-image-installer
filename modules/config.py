import os
import shutil
import logging
from modules import uboot

logger = logging.getLogger("arm-image-installer-config")

def apply_post_write_configs(root_mount, args, is_iot=False, dry_run=False):
    logger.info("Applying post-write configuration...")

    # Correct IoT SSH injection path logic
    if is_iot:
        ssh_dir = os.path.join(root_mount, "var/home/root/.ssh")
    else:
        ssh_dir = os.path.join(root_mount, "root/.ssh")
    authorized_keys = os.path.join(ssh_dir, "authorized_keys")

    if args.addkey:
        if dry_run:
            logger.info(f"[DRY-RUN] Would inject SSH key into {authorized_keys}")
            logger.debug(f"[DRY-RUN] SSH key contents: {open(args.addkey).read().strip()}")
        else:
            os.makedirs(os.path.dirname(ssh_dir), exist_ok=True)
            os.makedirs(ssh_dir, exist_ok=True)
            with open(authorized_keys, "a") as auth_file:
                auth_file.write("# Added by arm-image-installer\n")
                with open(args.addkey, "r") as keyfile:
                    key_content = keyfile.read().strip()
                    auth_file.write(key_content + "\n")
            os.chmod(authorized_keys, 0o600)
            logger.info(f"SSH public key injected into {authorized_keys}")
            logger.info("SSH key added to root account.")
            logger.debug(f"SSH key contents: {key_content}")

    if args.norootpass:
        shadow_file = os.path.join(root_mount, "etc/shadow")
        if dry_run:
            logger.info(f"[DRY-RUN] Would remove root password in {shadow_file}")
        else:
            with open(shadow_file, "r+") as f:
                lines = f.readlines()
                f.seek(0)
                for line in lines:
                    if line.startswith("root:"):
                        f.write("root::" + ":".join(line.split(":")[2:]))
                    else:
                        f.write(line)
                f.truncate()
            logger.info("Root password removed successfully.")

    if args.relabel:
        relabel_path = os.path.join(root_mount, ".autorelabel")
        if dry_run:
            logger.info(f"[DRY-RUN] Would create SELinux autorelabel marker at {relabel_path}")
        else:
            open(relabel_path, "a").close()
            logger.info("SELinux relabel marker created successfully.")

    logger.info("Configuration complete.")


def apply_bootloader_configs(boot_mount, args, is_iot=False, dry_run=False):
    logger.info("Applying bootloader configuration...")

    loader_dir = os.path.join(boot_mount, "loader/entries")
    if dry_run:
        logger.info(f"[DRY-RUN] Would modify bootloader entries in {loader_dir}")
    else:
        if os.path.exists(loader_dir):
            for entry in os.listdir(loader_dir):
                entry_file = os.path.join(loader_dir, entry)
                with open(entry_file, "r+") as f:
                    lines = f.readlines()
                    f.seek(0)
                    for line in lines:
                        if line.startswith("options"):
                            line = line.strip()
                            if args.showboot:
                                line = line.replace(" rhgb", "").replace(" quiet", "")
                            if args.addconsole and "console=" not in line:
                                console_str = uboot.get_default_console(args.target, args.image)
                                line += f" console={console_str}"
                            if args.args:
                                line += f" {args.args}"
                            if args.sysrq:
                                line += " sysrq_always_enabled=1"
                            line += "\n"
                        f.write(line)
                    f.truncate()
            logger.info("Bootloader kernel arguments updated successfully.")
        else:
            logger.warning(f"Bootloader entries directory {loader_dir} not found. Skipping kernel argument injection.")

    if args.ign_url:
        if is_iot:
            ign_file = os.path.join(boot_mount, "ignition.firstboot")
            if dry_run:
                logger.info(f"[DRY-RUN] Would modify {ign_file} to inject ignition URL")
            else:
                if os.path.exists(ign_file):
                    with open(ign_file, "r+") as f:
                        content = f.read()
                        content = content.replace(
                            "true",
                            f"true ignition.firstboot=1 ignition.config.url={args.ign_url}"
                        )
                        f.seek(0)
                        f.write(content)
                        f.truncate()
                    logger.info(f"Ignition URL successfully injected into {ign_file}.")
                else:
                    logger.warning(f"Ignition firstboot file {ign_file} not found. Skipping ignition injection.")
        else:
            logger.warning("Ignition URL provided but image is not IoT. Ignition injection skipped.")

    # Wi-Fi credentials
    if args.wifi_ssid:
        nm_file = os.path.join(boot_mount, "wifi-credentials.nmconnection")
        if dry_run:
            logger.info(f"[DRY-RUN] Would create Wi-Fi configuration at {nm_file}")
        else:
            with open(nm_file, "w") as f:
                f.write("[connection]\n")
                f.write("id=WiFi connection\n")
                f.write("type=wifi\n")
                f.write("interface-name=wlan0\n\n")
                f.write("[wifi]\n")
                f.write(f"ssid={args.wifi_ssid}\n\n")
                if args.wifi_pass:
                    f.write("[wifi-security]\n")
                    f.write(f"key-mgmt={args.wifi_security}\n")
                    f.write(f"psk={args.wifi_pass}\n\n")
                f.write("[ipv4]\nmethod=auto\n\n")
                f.write("[ipv6]\nmethod=auto\n")
            os.chmod(nm_file, 0o600)
            logger.info(f"Wi-Fi credentials written to {nm_file}")

