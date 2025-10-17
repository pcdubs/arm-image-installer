#!/bin/bash
# Download latest Fedora ARM images from Koji for testing

set -e -o pipefail

CACHE_DIR="${CACHE_DIR:-/var/tmp/arm-image-installer-test-cache}"
FEDORA_VERSION="${FEDORA_VERSION:-43}"

# Compose URLs
SERVER_COMPOSE_URL="https://kojipkgs.fedoraproject.org/compose/branched/latest-Fedora-${FEDORA_VERSION}"
IOT_COMPOSE_URL="https://kojipkgs.fedoraproject.org/compose/iot/latest-Fedora-IoT-${FEDORA_VERSION}"

# Create cache directory
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
    echo "Error: Could not create cache directory: $CACHE_DIR"
    exit 1
fi

download_image() {
    local compose_url="$1"
    local image_type="$2"  # "Server" or "IoT"

    echo "= Downloading latest Fedora ${FEDORA_VERSION} ${image_type} image..."

    # Fetch the compose metadata to find the image filename
    local compose_id=$(curl -s "${compose_url}/COMPOSE_ID")
    local curl_exit=$?
    if [ $curl_exit -ne 0 ] || [ -z "$compose_id" ]; then
        echo "Error: Could not fetch COMPOSE_ID from ${compose_url}"
        echo "The compose may not exist or network is unavailable (curl exit: $curl_exit)"
        return 1
    fi
    echo "= Compose ID: ${compose_id}"

    # Construct image path based on type
    if [ "$image_type" = "Server" ]; then
        local image_dir="${compose_url}/compose/Server/aarch64/images"
    elif [ "$image_type" = "IoT" ]; then
        local image_dir="${compose_url}/compose/IoT/aarch64/images"
    else
        echo "Error: Unknown image type: $image_type"
        return 1
    fi

    # List files and find the image
    echo "= Fetching file list from ${image_dir}..."

    # Fetch directory listing
    local dir_listing=$(curl -s "${image_dir}/")

    # Basic validation that we got HTML (not an error page)
    if ! echo "$dir_listing" | grep -qE '<html|<HTML|href='; then
        echo "Error: Directory listing doesn't appear to be valid HTML"
        echo "URL may be incorrect or server returned an error"
        return 1
    fi

    # Parse HTML to find image files - look for <a href="...raw.xz">
    # Use grep -F for literal string matching to avoid regex issues
    local image_file=$(echo "$dir_listing" | \
        grep -o 'href="[^"]*raw\.xz"' | \
        sed 's/href="//;s/"$//' | \
        grep -F "Fedora-${image_type}" | \
        grep "aarch64.*raw\.xz$" | \
        head -1)

    if [ -z "$image_file" ]; then
        echo "Error: Could not find ${image_type} image in ${image_dir}"
        echo "= Available files:"
        curl -s "${image_dir}/" | grep -o 'href="[^"]*"' | sed 's/href="//;s/"$//' | head -10
        return 1
    fi

    local image_url="${image_dir}/${image_file}"
    local cache_file="${CACHE_DIR}/${image_file}"

    # Check if already cached
    if [ -f "$cache_file" ]; then
        echo "= Image already cached: ${cache_file}"
        echo "$cache_file"
        return 0
    fi

    # Download the image
    echo "= Downloading ${image_file}..."
    echo "= URL: ${image_url}"

    # Check available disk space (need at least 10GB free)
    local available_space=$(df -k "$CACHE_DIR" | tail -1 | awk '{print $4}')
    local required_space=$((10 * 1024 * 1024))  # 10GB in KB

    # Validate available_space is a number
    if ! [[ "$available_space" =~ ^[0-9]+$ ]]; then
        echo "Warning: Could not determine available disk space"
    elif [ "$available_space" -lt "$required_space" ]; then
        echo "Warning: Low disk space in $CACHE_DIR"
        echo "Available: $(numfmt --to=iec-i --suffix=B $((available_space * 1024)) 2>/dev/null || echo ${available_space}KB)"
        echo "Recommended: 10GB+ for image downloads"
    fi

    # Download with progress and capture exit code
    curl -L --progress-bar -o "${cache_file}.tmp" "${image_url}"
    local curl_exit=$?

    # Verify download completed
    if [ $curl_exit -eq 0 ]; then
        mv "${cache_file}.tmp" "$cache_file"

        # Verify file is readable
        if [ ! -r "$cache_file" ]; then
            echo "Error: Downloaded file is not readable: $cache_file"
            rm -f "$cache_file"
            return 1
        fi

        echo "= Download complete: ${cache_file}"
        echo "$cache_file"
    else
        echo "Error: Download failed (curl exit code: $curl_exit)"
        rm -f "${cache_file}.tmp"
        return 1
    fi
}

# Parse command line arguments
IMAGE_TYPE="$1"

case "$IMAGE_TYPE" in
    server|Server|SERVER)
        download_image "$SERVER_COMPOSE_URL" "Server"
        ;;
    iot|IoT|IOT)
        download_image "$IOT_COMPOSE_URL" "IoT"
        ;;
    all|ALL)
        # Disable set -e temporarily to allow both downloads to be attempted
        set +e
        local SERVER_IMAGE=$(download_image "$SERVER_COMPOSE_URL" "Server")
        local SERVER_EXIT=$?
        local IOT_IMAGE=$(download_image "$IOT_COMPOSE_URL" "IoT")
        local IOT_EXIT=$?
        set -e

        # Report results
        if [ $SERVER_EXIT -eq 0 ]; then
            echo "SERVER_IMAGE=${SERVER_IMAGE}"
        else
            echo "SERVER_IMAGE=FAILED"
        fi

        if [ $IOT_EXIT -eq 0 ]; then
            echo "IOT_IMAGE=${IOT_IMAGE}"
        else
            echo "IOT_IMAGE=FAILED"
        fi

        # Exit with error if both failed
        if [ $SERVER_EXIT -ne 0 ] && [ $IOT_EXIT -ne 0 ]; then
            echo "Error: Both downloads failed"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {server|iot|all}"
        echo ""
        echo "Download latest Fedora ARM images for testing"
        echo ""
        echo "Options:"
        echo "  server - Download Server image only"
        echo "  iot    - Download IoT image only"
        echo "  all    - Download both images"
        echo ""
        echo "Environment variables:"
        echo "  CACHE_DIR       - Directory for cached images (default: /var/tmp/arm-image-installer-test-cache)"
        echo "  FEDORA_VERSION  - Fedora version to download (default: 43)"
        exit 1
        ;;
esac
