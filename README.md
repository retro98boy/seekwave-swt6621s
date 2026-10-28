# SWT6621S Linux driver

Out-of-tree Linux Wi-Fi and Bluetooth drivers for SeekWave SWT6621S modules,
based on the vendor driver. This branch maintains KICKPI K3B integration.

**Only SDIO has been tested on hardware.** USB is unverified and may not work;
the supplied DKMS package disables USB.

## Requirements and validation

Requires **Linux 4.3 or newer**. Build and hardware validation results:

| Version | Compiles | Tested |
| --- | --- | --- |
| 6.1 (Rockchip BSP) | Yes | Yes |
| 7.2.8 | Yes | No |
| 7.3 | Yes | Yes |

These results cover the listed kernel families, not every patch release or
feature. Other boards and firmware combinations require separate validation.

Packaging targets Debian 11+ and Ubuntu 20.04+. The board needs a working SDIO
host, power sequencing and device tree, matching kernel headers, a compiler,
and suitable firmware/calibration files. For Armbian edge rockchip64, install
`linux-headers-edge-rockchip64`; use the matching header package for other
kernel families.

## Install and configure

Download the deb and `SHA256SUMS` from a published Release or an Actions
artifact, and place them in the same directory. Replace `VERSION` with the
downloaded package version:

```sh
sha256sum -c SHA256SUMS
sudo apt install ./swt6621s-dkms_VERSION_all.deb
dkms status
```

The deb carries DKMS sources and builds/installs the `.ko` modules locally.
It does not install firmware, device trees or loading configuration, or
explicitly load the modules. DKMS rebuilds modules for new kernels when
matching headers are available. After an upgrade, reboot or reload the modules
to replace an already loaded build.

### Firmware and module loading

Install matching firmware/calibration files separately. For files under
`/lib/firmware/seekwave/`, create
`/etc/modprobe.d/swt6621s-sdio-uart.conf`:

```conf
options skw_sdio_lite firmware_dir=seekwave
options swt6621s_wifi firmware_dir=seekwave
options skwbt firmware_dir=seekwave
softdep swt6621s_wifi pre: skw_sdio_lite
softdep skwbt pre: swt6621s_wifi
```

`firmware_dir` selects the firmware subdirectory; an empty value uses the
firmware root. The loader first tries a board-specific name using the first
device-tree root `compatible` string, then the generic name. For `kickpi,k3b`:

```text
/lib/firmware/seekwave/SWT6621S_IRAM_SDIO.kickpi,k3b.bin
/lib/firmware/seekwave/SWT6621S_IRAM_SDIO.bin
```

Fallback stays in the configured directory. Without a board ID, only the
generic name is tried. Actual filenames depend on the chip/service and appear
in the kernel log.

The `softdep` entries define the loading order:
`skw_sdio_lite` (transport/firmware boot) → `swt6621s_wifi` (Wi-Fi) → `skwbt`
(Bluetooth HCI). `modprobe` applies these rules and the configured options.
Each module has its own `firmware_dir` option.

### Enable loading at boot

On systemd systems, optionally create
`/etc/modules-load.d/swt6621s-sdio-uart.conf`:

```conf
skw_sdio_lite
swt6621s_wifi
skwbt
```

Keep the `modprobe.d` configuration above for options and ordering. Both files
are supplied by the administrator or distribution, not this package; avoid
duplicates if your system already provides them. See
[modprobe.d(5)](https://man7.org/linux/man-pages/man5/modprobe.d.5.html) and
[modules-load.d](https://www.freedesktop.org/software/systemd/man/latest/modules-load.d.html).

## Build from source

Install the build dependencies, also adding `dh-dkms` if your distribution
packages the DKMS debhelper addon separately:

```sh
sudo apt install git build-essential debhelper dkms
```

Commit or stash changes, then build from a clean checkout:

```sh
bash scripts/build-deb.sh
```

The package and `SHA256SUMS` are written to `dist/`. Pass an output directory
as the script's optional argument to use another location.

See [Debian packaging details](debian/README.Debian) for more information.

## Versions and releases

Package versions and manually created tags use
`YYYY.MM.DD.HHMMSS+gitCOMMIT`, without a `v` prefix. The timestamp is the source
commit's UTC committer time and `COMMIT` is its first 12 SHA characters.
Rebuilding the same commit keeps the same version.

After committing, pushing and testing the source, create a tag manually:

```sh
version=$(bash scripts/version.sh)
git tag -a "$version" -m "Release $version"
git push origin "refs/tags/$version"
```

To release another tested commit, pass it to `scripts/version.sh` and use the
same commit as the final argument to `git tag`.

The [workflow](.github/workflows/build-deb.yml) uploads build artifacts for
branch pushes, PRs and manual runs. Pushing a matching version tag also creates
a draft Release with the deb and checksums; publish it manually after review.
CI never creates or pushes tags. Tags must match the generated version.

## License

Generally GPL-2.0, with exceptions noted in individual files. See
[copyright and license details](debian/copyright).
