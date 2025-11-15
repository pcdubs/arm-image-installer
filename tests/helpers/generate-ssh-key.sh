#!/bin/bash
# Generate SSH key for testing if it doesn't exist

set -e -o pipefail

# Check if ssh-keygen is available
if ! command -v ssh-keygen &>/dev/null; then
    echo "Error: ssh-keygen not found"
    echo "Please install: dnf install openssh-clients"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: $0 <key-path>"
    echo ""
    echo "Generate an SSH key pair for testing if it doesn't already exist."
    echo "Creates <key-path> (private key) and <key-path>.pub (public key)"
    exit 1
fi

SSH_KEY="$1"

# Validate key directory exists and is writable
SSH_KEY_DIR=$(dirname "$SSH_KEY")
if [ ! -d "$SSH_KEY_DIR" ]; then
    echo "Error: Directory does not exist: $SSH_KEY_DIR"
    exit 1
fi

if [ ! -w "$SSH_KEY_DIR" ]; then
    echo "Error: Directory is not writable: $SSH_KEY_DIR"
    exit 1
fi

if [ ! -f "$SSH_KEY" ]; then
    # Check if public key exists without private key (incomplete state)
    if [ -f "${SSH_KEY}.pub" ]; then
        echo "Warning: Found orphaned public key without private key"
        echo "= Removing orphaned public key and regenerating pair..."
        rm -f "${SSH_KEY}.pub"
    fi

    echo "= Generating test SSH key: ${SSH_KEY}..."
    ssh-keygen -t rsa -b 2048 -f "$SSH_KEY" -N "" -C "test@arm-image-installer"

    # Verify key was created
    if [ ! -f "$SSH_KEY" ] || [ ! -f "${SSH_KEY}.pub" ]; then
        echo "Error: SSH key generation failed"
        exit 1
    fi
else
    echo "= Using existing SSH key: ${SSH_KEY}"

    # Verify public key also exists
    if [ ! -f "${SSH_KEY}.pub" ]; then
        echo "Error: Private key exists but public key is missing: ${SSH_KEY}.pub"
        echo "Please remove $SSH_KEY and regenerate the keypair"
        exit 1
    fi
fi

# Return the key path
echo "$SSH_KEY"
