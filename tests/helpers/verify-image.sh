#!/bin/bash
# Verify disk image structure and contents without booting
# Mounts the image and checks for expected customizations

set -e -o pipefail

# Verify bash version (need 3.0+ for [[ ]])
if [ -z "$BASH_VERSION" ] || [ "${BASH_VERSION%%.*}" -lt 3 ]; then
    echo "Error: This script requires bash 3.0 or later"
    exit 1
fi

IMAGE_FILE=""
VERIFY_SSH_KEY=""
VERIFY_RESIZE=0
VERIFY_NOROOT=0
VERIFY_WIFI=""

usage() {
    cat <<EOF
Usage: $0 [OPTIONS] <image-file>

Verify disk image structure and contents without booting.

Options:
    --verify-ssh-key FILE    Verify SSH public key was added to authorized_keys
    --verify-resize          Verify root partition was resized
    --verify-noroot          Verify root password was cleared
    --verify-wifi SSID       Verify Wi-Fi configuration exists
    -h, --help               Show this help

Examples:
    $0 test-server.img
    $0 --verify-ssh-key ~/.ssh/test.pub --verify-resize test-custom.img
EOF
    exit 1
}

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --verify-ssh-key)
            if [ -z "$2" ] || [ "${2:0:1}" = "-" ]; then
                echo "Error: --verify-ssh-key requires an argument"
                usage
            fi
            VERIFY_SSH_KEY="$2"
            shift 2
            ;;
        --verify-resize)
            VERIFY_RESIZE=1
            shift
            ;;
        --verify-noroot)
            VERIFY_NOROOT=1
            shift
            ;;
        --verify-wifi)
            if [ -z "$2" ] || [ "${2:0:1}" = "-" ]; then
                echo "Error: --verify-wifi requires an argument"
                usage
            fi
            VERIFY_WIFI="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Error: Unknown option: $1"
            usage
            ;;
        *)
            IMAGE_FILE="$1"
            shift
            ;;
    esac
done

if [ -z "$IMAGE_FILE" ]; then
    echo "Error: No image file specified"
    usage
fi

if [ ! -f "$IMAGE_FILE" ]; then
    echo "Error: Image file not found: $IMAGE_FILE"
    exit 1
fi

echo "= Verifying image: $IMAGE_FILE"

# Check for required tools
for tool in fdisk losetup file; do
    if ! command -v "$tool" &> /dev/null; then
        echo "Error: Required tool '$tool' not found"
        exit 1
    fi
done

# Verify we're running as root (needed for losetup/mount)
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Basic file checks
echo "= Checking basic image properties..."
FILE_TYPE=$(file "$IMAGE_FILE")
echo "= File type: $FILE_TYPE"

if ! echo "$FILE_TYPE" | grep -qE "DOS/MBR boot sector|block special"; then
    echo "Warning: Image doesn't appear to be a disk image"
fi

IMAGE_SIZE=$(stat -c "%s" "$IMAGE_FILE" 2>/dev/null || stat -f "%z" "$IMAGE_FILE" 2>/dev/null || echo "0")
echo "= Image size: $(numfmt --to=iec-i --suffix=B $IMAGE_SIZE 2>/dev/null || echo ${IMAGE_SIZE} bytes)"

if [ "$IMAGE_SIZE" -lt 1000000000 ]; then
    echo "Error: Image seems too small (${IMAGE_SIZE} bytes)"
    exit 1
fi

# Check partition table
echo "= Checking partition table..."
fdisk -l "$IMAGE_FILE" > /tmp/fdisk-output.txt 2>&1 || true

if ! grep -q "Disklabel type:" /tmp/fdisk-output.txt; then
    echo "Error: Could not read partition table"
    cat /tmp/fdisk-output.txt
    exit 1
fi

echo "= Partition table:"
cat /tmp/fdisk-output.txt

# Set up loop device
echo "= Setting up loop device..."
LOOP_DEVICE=$(losetup -f -P --show "$IMAGE_FILE" 2>&1)
LOSETUP_EXIT=$?

if [ $LOSETUP_EXIT -ne 0 ] || [ -z "$LOOP_DEVICE" ]; then
    echo "Warning: Failed to create loop device (losetup exit: $LOSETUP_EXIT)"
    echo "Error output: $LOOP_DEVICE"

    # If any verification flags were requested, we can't proceed without mounting
    if [ -n "$VERIFY_SSH_KEY" ] || [ $VERIFY_NOROOT -eq 1 ] || [ -n "$VERIFY_WIFI" ] || [ $VERIFY_RESIZE -eq 1 ]; then
        echo "Error: Cannot verify customizations without mounting the image"
        echo "This may happen in virtualized environments without loop device support"
        exit 1
    fi

    # For basic verification without mounting, just check what we can
    echo "= Running basic verification without mounting..."
    echo "= Verification Summary:"
    echo "  ✓ Image file is valid disk image"
    echo "  ✓ Partition table is readable"
    echo "  - Could not mount image to verify filesystem"
    echo "= Basic verification passed (limited)"
    exit 0
fi

echo "= Loop device: $LOOP_DEVICE"

cleanup() {
    echo "= Cleaning up..."
    if [ -n "$MOUNT_POINT" ] && mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        umount "$MOUNT_POINT" 2>/dev/null || true
    fi
    if [ -n "$BOOT_MOUNT" ] && mountpoint -q "$BOOT_MOUNT" 2>/dev/null; then
        umount "$BOOT_MOUNT" 2>/dev/null || true
    fi
    if [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ]; then
        rmdir "$MOUNT_POINT" 2>/dev/null || true
    fi
    if [ -n "$BOOT_MOUNT" ] && [ -d "$BOOT_MOUNT" ]; then
        rmdir "$BOOT_MOUNT" 2>/dev/null || true
    fi
    if [ -n "$LOOP_DEVICE" ]; then
        losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi
    rm -f /tmp/fdisk-output.txt
}

trap cleanup EXIT INT TERM

# Wait for partition devices to appear
sleep 2

# Find root partition (usually p3 or p2)
ROOT_PARTITION=""
for part in "${LOOP_DEVICE}p3" "${LOOP_DEVICE}p2"; do
    if [ -b "$part" ]; then
        ROOT_PARTITION="$part"
        break
    fi
done

if [ -z "$ROOT_PARTITION" ]; then
    echo "Error: Could not find root partition"
    ls -la "${LOOP_DEVICE}"* || true
    exit 1
fi

echo "= Root partition: $ROOT_PARTITION"

# Check partition size if --verify-resize is set
if [ $VERIFY_RESIZE -eq 1 ]; then
    echo "= Verifying partition was resized..."
    PART_SIZE=$(blockdev --getsize64 "$ROOT_PARTITION" 2>/dev/null || echo "0")
    PART_SIZE_GB=$((PART_SIZE / 1024 / 1024 / 1024))
    echo "= Root partition size: ${PART_SIZE_GB}GB ($(numfmt --to=iec-i --suffix=B $PART_SIZE 2>/dev/null || echo ${PART_SIZE} bytes))"

    # For a resized 20GB image, root partition should be at least 15GB
    if [ "$PART_SIZE_GB" -ge 15 ]; then
        echo "= ✓ Partition was resized (${PART_SIZE_GB}GB)"
    else
        echo "= ✗ Partition does not appear to be resized (only ${PART_SIZE_GB}GB)"
        exit 1
    fi
fi

# Mount the root partition
MOUNT_POINT=$(mktemp -d /tmp/verify-image-mount.XXXXXX)
echo "= Mounting root partition at $MOUNT_POINT..."

if ! mount -o ro "$ROOT_PARTITION" "$MOUNT_POINT"; then
    echo "Error: Failed to mount root partition"
    exit 1
fi

echo "= ✓ Root partition mounted successfully"

# Verify filesystem contents
echo "= Checking filesystem contents..."

# Check for basic directories
for dir in etc usr var; do
    if [ ! -d "$MOUNT_POINT/$dir" ]; then
        echo "Error: Missing expected directory: /$dir"
        exit 1
    fi
done
echo "= ✓ Basic filesystem structure looks correct"

# Verify SSH key was added
if [ -n "$VERIFY_SSH_KEY" ]; then
    echo "= Verifying SSH key was added..."

    if [ ! -f "$VERIFY_SSH_KEY" ]; then
        echo "Error: SSH public key not found: $VERIFY_SSH_KEY"
        exit 1
    fi

    AUTH_KEYS="$MOUNT_POINT/root/.ssh/authorized_keys"
    if [ ! -f "$AUTH_KEYS" ]; then
        echo "Error: authorized_keys file not found at $AUTH_KEYS"
        exit 1
    fi

    SSH_KEY_CONTENT=$(cat "$VERIFY_SSH_KEY")
    if grep -qF "$SSH_KEY_CONTENT" "$AUTH_KEYS"; then
        echo "= ✓ SSH key found in authorized_keys"
    else
        echo "= ✗ SSH key NOT found in authorized_keys"
        exit 1
    fi
fi

# Verify root password was cleared
if [ $VERIFY_NOROOT -eq 1 ]; then
    echo "= Verifying root password was cleared..."

    SHADOW_FILE="$MOUNT_POINT/etc/shadow"
    if [ ! -f "$SHADOW_FILE" ]; then
        echo "Error: shadow file not found at $SHADOW_FILE"
        exit 1
    fi

    ROOT_SHADOW=$(grep "^root:" "$SHADOW_FILE")
    # Empty/disabled password in shadow file is shown as * or ! or !!
    if echo "$ROOT_SHADOW" | grep -qE '^root:[*!]+:'; then
        echo "= ✓ Root password is empty/disabled"
    else
        echo "= ✗ Root password is NOT empty: $ROOT_SHADOW"
        exit 1
    fi
fi

# Verify Wi-Fi configuration
if [ -n "$VERIFY_WIFI" ]; then
    echo "= Verifying Wi-Fi configuration for SSID: $VERIFY_WIFI..."

    NM_CONNECTIONS="$MOUNT_POINT/etc/NetworkManager/system-connections"
    if [ ! -d "$NM_CONNECTIONS" ]; then
        echo "Error: NetworkManager connections directory not found"
        exit 1
    fi

    if grep -l "ssid=${VERIFY_WIFI}" "$NM_CONNECTIONS"/*.nmconnection 2>/dev/null | grep -q .; then
        echo "= ✓ Wi-Fi configuration found"
    else
        echo "= ✗ Wi-Fi configuration not found"
        echo "= Connections directory contents:"
        ls -la "$NM_CONNECTIONS" || true
        exit 1
    fi
fi

# Summary
VERIFICATIONS_RUN=0
echo ""
echo "= Verification Summary:"
echo "  ✓ Image file is valid disk image"
echo "  ✓ Partition table is readable"
echo "  ✓ Root filesystem is mountable"
echo "  ✓ Basic filesystem structure is correct"
VERIFICATIONS_RUN=4

[ $VERIFY_RESIZE -eq 1 ] && echo "  ✓ Partition was resized" && VERIFICATIONS_RUN=$((VERIFICATIONS_RUN + 1))
[ -n "$VERIFY_SSH_KEY" ] && echo "  ✓ SSH key was added" && VERIFICATIONS_RUN=$((VERIFICATIONS_RUN + 1))
[ $VERIFY_NOROOT -eq 1 ] && echo "  ✓ Root password cleared" && VERIFICATIONS_RUN=$((VERIFICATIONS_RUN + 1))
[ -n "$VERIFY_WIFI" ] && echo "  ✓ Wi-Fi configuration added" && VERIFICATIONS_RUN=$((VERIFICATIONS_RUN + 1))

echo "= Total verifications: $VERIFICATIONS_RUN"
echo ""
echo "= All verifications passed!"

exit 0
