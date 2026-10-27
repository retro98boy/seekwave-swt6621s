/******************************************************************************
 *
 * Copyright(c) 2020-2030  Seekwave Corporation.
 *
 *****************************************************************************/
#ifndef __BOOT_CONFIG_H__
#define __BOOT_CONFIG_H__
#include <linux/types.h>
#include <linux/version.h>
#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 3, 0)
#error "SeekWave requires Linux >= 4.3 for strscpy() and the GPIO descriptor API"
#endif
#include <linux/gpio/consumer.h>
#include <linux/delay.h>

//#define CONFIG_SKW_FREE_FIRMWARE_MEM_SUPPORT 1
#if defined(CONFIG_SKW_FREE_FIRMWARE_MEM_SUPPORT)
#define CONFIG_SEEKWAVE_FIRMWARE_LOAD
#endif
//#define SKW_NV_CONFIG_NAME_ALONE /*duouble antenna config SKW_NV_CONFIG_NAME_ALONE*/
//#define CONFIG_SEEKWAVE_FIRMWARE_LOAD /*support the skw self request firmware api*/
/*cus used the seekwave firmware load api need open the macro and the redefined the firmware path*/
#define SWT6621S_USB_IRAM_NAME "SWT6621S_IRAM_USB.bin"
#define SWT6621S_USB_DRAM_NAME "SWT6621S_DRAM_USB.bin"
#define SWT6621S_USB_NV_NAME "SWT6621S_NV_USB.bin"
#define SWT6621S_SDIO_IRAM_NAME "SWT6621S_IRAM_SDIO.bin"
#define SWT6621S_SDIO_DRAM_NAME "SWT6621S_DRAM_SDIO.bin"
#define SWT6621S_SDIO_NV_NAME "SWT6621S_NV_SDIO.bin"

#if defined(CONFIG_SEEKWAVE_FIRMWARE_LOAD)
#define SKW_SPEC_FW_PATH "/data/"
#define SWT6621S_USB_IRAM_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_USB_IRAM_NAME)
#define SWT6621S_USB_DRAM_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_USB_DRAM_NAME)
#define SWT6621S_USB_NV_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_USB_NV_NAME)

#define SWT6621S_SDIO_IRAM_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_SDIO_IRAM_NAME)
#define SWT6621S_SDIO_DRAM_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_SDIO_DRAM_NAME)
#define SWT6621S_SDIO_NV_FW_PATH (SKW_SPEC_FW_PATH SWT6621S_SDIO_NV_NAME)
#else
#define SKW_IRAM_FILE_PATH "SWT6621S_IRAM_SDIO.bin"
#define SKW_DRAM_FILE_PATH "SWT6621S_DRAM_SDIO.bin"
#endif
#define CONFIG_SEEKWAVE_PLD_RELEASE 1 /*release skw bsp version cls the log and open the recovery*/
//#define SKW_SUPPORT_MMC_NONREMOVABLE //support the host mmc card is not removable but sdcard is removable default
//#define CONFIG_SKW_HOST_PLATFORM_AMLOGIC 1 /*supprot the aml  power on api*/
//#define CONFIG_SKW_HOST_PLATFORM_FULLHAN /*support the fullhan power on api*/
//#define CONFIG_SKW_HOST_PLATFORM_ROCKCHIP


#ifdef SKW_NV_CONFIG_NAME_ALONE
#define  SEEKWAVE_NV_NAME  "SWT6621S_NV_SDIO_ALONE.bin" /*duouble antenna config SKW_NV_CONFIG_NAME_ALONE*/
#elif defined(SKW_NV_CONFIG_NAME_SHARE)
//#elifdef SKW_NV_CONFIG_NAME_SHARE /*duouble antenna config SKW_NV_CONFIG_NAME_ALONE*/
#define  SEEKWAVE_NV_NAME  "SWT6621S_NV_SDIO_SHARE.bin"
#else
#define  SEEKWAVE_NV_NAME  "SEEKWAVE_NV_SWT6621S.bin"
#endif


//#define  SKW_IRAM_FILE_PATH  "/vendor/firmware/SWT6621S_IRAM_USB.bin"
//#define  SKW_DRAM_FILE_PATH  "/vendor/firmware/SWT6621S_DRAM_USB.bin"

#define SKW_DUMP_BUFFER_SIZE     (1500*1024)
#define POWERON_DELAY_TIME  200
#define  SKW_BT_ANTENNA_CFG   0

#define CONFIG_NO_SERVICE_PD 0 // default ps mode cp not poweroff

/*****default when host power ,need reset card to enum usb or resacn sdio******/
//#define CONFIG_SKW_HOST_POWEROFF_NOT_RESET_CARD


/***********************************************************
**CONFIG_SKW_HOST_SUPPORT_ADMA 1 : use ADMA	0 : use SDMA
**
***********************************************************/
#define CONFIG_SKW_HOST_SUPPORT_ADMA

#if defined(CONFIG_SKW_HOST_SUPPORT_ADMA)
#define TX_DMA_TYPE		TX_ADMA
#define  SKW_DMA_TYPE_CFG   ADMA
#else
#define TX_DMA_TYPE		TX_SDMA
#define  SKW_DMA_TYPE_CFG   SDMA
#endif

//#define  USB_POWEROFF_IN_LOWPOWER  1
#define SKW_MMC_HOST_SD_INDEX  1 //default sd index is 1 if not 1 pls set to 0 or 2

#if defined(CONFIG_SKW_HOST_PLATFORM_FULLHAN)
#define SKW_MMC_HOST_SD_INDEX  1 //default sd index is 1 if not 1 pls set to 0 or 2
extern void fh_sdio_card_scan(int sd_id); //fullhan sdio card scan
#endif
#if defined(CONFIG_SKW_HOST_PLATFORM_AMLOGIC)
extern void extern_wifi_set_enable(int is_on);
extern void set_usb_wifi_power(int is_power);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ALLWINER)
extern void sunxi_mmc_rescan_card(unsigned ids);
extern void sunxi_wlan_set_power(int on);
extern int sunxi_wlan_get_bus_index(void);
extern int sunxi_wlan_get_oob_irq(int *, int *);
extern int get_custom_mac_address(int fmt, char *name, char *addr);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ROCKCHIP)
extern int rockchip_wifi_power(int on);
extern int rockchip_wifi_set_carddetect(int val);
#else
extern int skw_chip_enable_set(int on);
static inline int skw_chip_power_ops(int on)
{
	return skw_chip_enable_set(on);
}
#endif

static inline void skw_chip_set_power(int on)
{
#if defined(CONFIG_SKW_HOST_PLATFORM_AMLOGIC)
	extern_wifi_set_enable(on);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ALLWINER)
	sunxi_wlan_set_power(on);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ROCKCHIP)
	rockchip_wifi_power(on);
#else
	skw_chip_power_ops(on);
#endif

}
static inline void skw_chip_power_reset(void)
{
#if defined(CONFIG_SKW_HOST_PLATFORM_AMLOGIC)
	printk("amlogic skw chip power reset !!\n");
	extern_wifi_set_enable(0);
	msleep(POWERON_DELAY_TIME);
	extern_wifi_set_enable(1);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ALLWINER)
	printk("allwinner skw chip power reset !!\n");
	sunxi_wlan_set_power(0);
	msleep(POWERON_DELAY_TIME);
	sunxi_wlan_set_power(1);
#elif defined(CONFIG_SKW_HOST_PLATFORM_ROCKCHIP)
	printk("rockchip skw chip power reset !!\n");
	rockchip_wifi_power(0);
	msleep(POWERON_DELAY_TIME);
	rockchip_wifi_power(1);
#else
	printk("self skw chip power reset !!\n");
	skw_chip_power_ops(0);
	msleep(POWERON_DELAY_TIME);
	skw_chip_power_ops(1);
#endif
}
#endif /* __BOOT_CONFIG_H__ */
