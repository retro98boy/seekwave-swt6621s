GPIO configuration
==================

The platform driver uses GPIO descriptors exclusively. Linux 3.17 or newer
is required for the GPIO consumer interfaces used here (including the flags
argument to devm_gpiod_get_optional()). Older kernels fail at compile time.
This is an interface minimum, not a claim that every other driver subsystem
has been tested on every kernel since 3.17.

Configure optional GPIOs on the SeekWave boot device using:

* host-wake-gpios: CP-to-host wake input; logical 1 means CP is active.
* chip-wake-gpios: host-to-CP wake output, initially asserted (logical 1).
  Logical 0 permits sleep; wake pulses deassert then reassert this signal.
* chip-en-gpios: chip enable output, initially asserted (logical 1).
  Logical 0 disables the chip; a reset cycle disables then enables it.

Non-DT platforms can provide GPIO lookup tables with the connection IDs
host-wake, chip-wake and chip-en. Integer GPIO overrides are not supported.
The unsupported properties gpio_host_wake, gpio_chip_wake and gpio_chip_en
cause probe to fail with an explicit error.

An absent property means that the driver does not own that signal. In
particular, do not also claim a GPIO owned by MMC power sequencing or rfkill.
Provider probe deferral and malformed GPIO specifications are propagated.

All GPIO accesses use logical values. Describe each signal's actual polarity
with GPIO_ACTIVE_HIGH or GPIO_ACTIVE_LOW. Logical 1 means asserted: physical
high for GPIO_ACTIVE_HIGH, physical low for GPIO_ACTIVE_LOW. Logical 0 means
deasserted and maps to the opposite physical level. Wake interrupts trigger
on assertion (rising for active-high, falling for active-low). Diagnostic
GPIO state displays and test_debug output modes also use logical values.

chip-en-gpios describes enable, not reset. skw_chip_enable_set(on) uses 1
to enable and 0 to disable the chip.
Do not label an active-high enable signal GPIO_ACTIVE_LOW just because
pulling it low resets the chip. A dedicated active-low reset signal would
instead use logical 1 to assert reset and logical 0 to release it; no separate
reset-gpios property is implemented by this driver.

Use GPIO_ACTIVE_LOW when the signal is asserted low, including any
board-level inversion; otherwise use GPIO_ACTIVE_HIGH.
GPIO controllers requiring sleeping access are rejected because the driver
uses the signals in interrupt/atomic context. Acquired descriptors are
device-managed and released on probe failure or device removal.

The boot platform device and its transport must be unloaded together.
Separate sysfs bind/unbind controls for the boot device are intentionally
disabled: the transport retains GPIO references while it is running.
After a first SDIO firmware boot failure, the transport is quiesced before
the GPIOs are released. Reload the transport module to retry; the stopped
transport must not be reused by a later boot probe.
Direct SDIO device removal also permanently quiesces this transport instance.
Reload the transport module before rebinding; ordinary firmware recovery
without device removal does not close admission.

SDIO teardown closes admission for transmit, receive, wake and service
operations, drains existing callers and stops the RX thread before releasing
IRQs or GPIO references. Blocking reads check shutdown at intervals of at
most 100 ms rather than waiting indefinitely. Child devices are unregistered
before their port buffers are freed. Boot failure and device removal serialize
this cleanup through the same teardown lock.

The boot UART wake callback returns -EOPNOTSUPP when either wake signal is
absent, propagates GPIO read errors, and uses a bounded wait for assertion.
