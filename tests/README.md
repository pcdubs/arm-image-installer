# arm-image-installer Tests

Automated tests for arm-image-installer that download real Fedora ARM images, create custom disk images, and boot them in QEMU to verify functionality.

## Test Structure

```
tests/
├── helpers/
│   ├── download-images.sh     # Download images from Koji
│   ├── boot-test.sh           # Boot images in QEMU and verify
│   └── generate-ssh-key.sh    # Generate SSH keys for testing
├── plans/                  # TMT test plans
│   ├── basic.fmf          # Quick smoke test
│   ├── full.fmf           # Full customization test
│   └── iot.fmf            # IoT with ignition test
├── test-server-basic.sh          # Server image basic test
├── test-server-customized.sh     # Server image with all options
└── test-iot.sh                   # IoT image with ignition
```

## Requirements

### System Requirements
- Fedora (or RHEL/CentOS)
- aarch64 architecture (or x86_64 with QEMU)
- Bash 3.0 or later
- At least 30GB free disk space
- At least 4GB RAM
- Root/sudo access
- Network access to kojipkgs.fedoraproject.org for image downloads

### Package Requirements
```bash
dnf install -y \
    qemu-system-aarch64 \
    edk2-aarch64 \
    curl \
    nmap-ncat \
    openssh-clients \
    lvm2 \
    xz
```

## Running Tests Manually

### Quick Smoke Test
**Note**: Tests must be run with sudo/root as arm-image-installer requires root privileges.

```bash
sudo ./tests/test-server-basic.sh
```

### Full Server Customization Test
```bash
sudo ./tests/test-server-customized.sh
```

### IoT Test
```bash
sudo ./tests/test-iot.sh
```

## Running with TMT

### Basic Test
```bash
tmt run plan --name /tests/plans/basic
# Or by file path:
tmt run -vvv plan --name tests/plans/basic
```

### Full Test Suite
```bash
tmt run plan --name /tests/plans/full
```

### IoT Test
```bash
tmt run plan --name /tests/plans/iot
```

### All Tests
```bash
tmt run
```

### Run Tests by Tag
```bash
# Run only quick smoke tests
tmt run --filter 'tag:quick'

# Run all server-related tests
tmt run --filter 'tag:server'

# Run IoT tests
tmt run --filter 'tag:iot'

# Run full customization tests
tmt run --filter 'tag:full'
```

## Test Details

### test-server-basic.sh
- Downloads latest Server image from Koji (~5-8 GB download)
- Creates a basic custom image with minimal options
- Boots the image in QEMU to verify it works
- **Typical Runtime**: 20-30 minutes (10-15 min download, 10-15 min boot/test)

### test-server-customized.sh
- Downloads latest Server image from Koji (~5-8 GB download)
- Creates a 20GB custom image with:
  - `--resizefs` - Resize root partition
  - `--addkey` - Add SSH key
  - `--norootpass` - Empty root password
  - `--wifi-ssid/pass/security` - Wi-Fi configuration
  - `--target=rpi4` - Raspberry Pi 4 target
- Boots the image and verifies:
  - SSH login with key works
  - Root password is empty
  - Partition was resized
  - Wi-Fi config file exists
- **Typical Runtime**: 30-45 minutes (10-15 min download, 5-10 min dd, 15-20 min boot/test)

### test-iot.sh
- Downloads latest IoT image from Koji (~4-6 GB download)
- Creates an ignition configuration file
- Creates a custom IoT image with ignition
- Boots the image in QEMU (longer timeout for ignition processing)
- Verifies ignition ran successfully
- **Note**: IoT images use the 'core' user instead of 'root'
- **Typical Runtime**: 30-45 minutes (8-12 min download, 20-30 min boot/ignition/test)

## Environment Variables

### CACHE_DIR
Directory for cached downloaded images (default: `/var/tmp/arm-image-installer-test-cache`)

```bash
CACHE_DIR=/path/to/cache ./test-server-basic.sh
```

### TEST_OUTPUT_DIR
Directory for test outputs and custom images (default: `/var/tmp/arm-image-installer-tests`)

```bash
TEST_OUTPUT_DIR=/path/to/output ./test-server-basic.sh
```

### FEDORA_VERSION
Fedora version to test (default: `43`)

```bash
FEDORA_VERSION=44 ./test-server-basic.sh
```

**Note**: These environment variables can also be set in TMT plans. See `tests/plans/*.fmf` files for examples.

## CI Integration

Tests are automatically run via Packit on pull requests. The `.packit.yaml` configuration includes:

```yaml
jobs:
  - job: tests
    trigger: pull_request
    targets:
      - fedora-stable
      - fedora-development
    tf_extra_params:
      environments:
        - arch: aarch64
```

Tests run on actual aarch64 hardware in Fedora's Testing Farm.

## Caching

Downloaded images are cached in `CACHE_DIR` to speed up repeated test runs. The cache persists between runs, so subsequent tests only need to download images once.

To clear the cache:
```bash
sudo rm -rf /var/tmp/arm-image-installer-test-cache
```

## Troubleshooting

### Test fails with "QEMU process died"
The QEMU boot log will be shown in the error output. The log file is created with a unique temporary name and automatically cleaned up.

### Download fails
Check network connectivity to `kojipkgs.fedoraproject.org`. You may need to adjust firewall rules.

### Out of disk space
Tests require significant disk space:
- Basic test: ~6-8 GB (downloaded image + output)
- Full customization test: ~26-28 GB (downloaded image + 20GB output image)
- IoT test: ~6-8 GB (downloaded image + output)

Use `df -h` to check available space and clean up old test outputs in `TEST_OUTPUT_DIR`:
```bash
sudo rm -rf /var/tmp/arm-image-installer-tests
```

### SSH timeout
Increase the boot timeout with `--timeout` parameter in boot-test.sh (default is 300 seconds).

### Test partially completed
If a test fails partway through, you may have leftover files:
- Downloaded images in `$CACHE_DIR` (safe to keep for reuse)
- Output images in `$TEST_OUTPUT_DIR` (can be removed to free space)
- Temporary SSH keys in `$TEST_OUTPUT_DIR/test_rsa*`

To clean up and retry:
```bash
# Keep downloaded images, remove test outputs
sudo rm -rf /var/tmp/arm-image-installer-tests

# Or clean everything including cached downloads
sudo rm -rf /var/tmp/arm-image-installer-tests /var/tmp/arm-image-installer-test-cache
```

## Contributing

When adding new tests:
1. Create a test script in `tests/`
2. Make it executable: `chmod +x tests/test-name.sh`
3. Add a TMT plan in `tests/plans/name.fmf`
4. Document the test in this README
5. Test locally before submitting PR
