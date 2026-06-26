skw_extra_symbols := $(src)/drivers/seekwaveplatform_lite/Module.symvers
skw_extra_flags := -I$(src)/include/linux/platform_data

skw_extra_flags += -DCONFIG_SEEKWAVE_BSP_DRIVERS
skw_extra_flags += -DCONFIG_SWT6621S_LOG_DEBUG

export skw_extra_flags
export skw_extra_symbols

export CONFIG_SWT6621S_NOT_WAKEUP_HOST=y
export CONFIG_SEEKWAVE_BSP_DRIVERS=y
export CONFIG_SKW_SDIOHAL=m
export CONFIG_SKW_BSP_UCOM=m
export CONFIG_SKW_BSP_BOOT=m
export CONFIG_WLAN_VENDOR_SWT6621S=m

obj-m += drivers/
