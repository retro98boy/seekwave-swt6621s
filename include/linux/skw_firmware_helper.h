/* SPDX-License-Identifier: GPL-2.0 */
#ifndef __SKW_FIRMWARE_HELPER_H__
#define __SKW_FIRMWARE_HELPER_H__

#include <linux/device.h>
#include <linux/firmware.h>
#include <linux/kernel.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/version.h>

/*
 * Read the first string from the Device Tree root "compatible" property
 * into @board_id.  If no DT or no compatible, @board_id stays empty.
 */
static inline void skw_firmware_board_id_init(char *board_id, size_t size)
{
	struct device_node *root;
	const char *compat;
	int len;

	if (!board_id || size == 0 || board_id[0])
		return;

	root = of_find_node_by_path("/");
	if (!root)
		return;

	compat = of_get_property(root, "compatible", &len);
	if (compat && len > 0) {
		strncpy(board_id, compat, size - 1);
		board_id[size - 1] = '\0';
		pr_info("skw firmware: board_id from DT compatible: %s\n", board_id);
	}
	of_node_put(root);
}

/*
 * Low-level firmware request.  On kernels >= 3.13 @direct selects
 * request_firmware_direct(); otherwise it falls back to request_firmware().
 */
static inline int skw_firmware_request_one(const struct firmware **fw,
					   const char *name,
					   struct device *dev,
					   int direct)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(3, 13, 0)
	if (direct)
		return request_firmware_direct(fw, name, dev);
#endif
	return request_firmware(fw, name, dev);
}

/*
 * Request a firmware file with optional subdirectory and board-specific
 * fallback.  If @firmware_dir is set, look under that subdirectory.  If
 * @board_id is set, first try name.<board_id>.ext, then name.ext.
 */
static inline int skw_firmware_request_with_fallback(const struct firmware **fw,
					     const char *name,
					     struct device *dev,
					     const char *firmware_dir,
					     char *board_id,
					     size_t board_id_size,
					     int direct)
{
	int ret;
	char *full_name = NULL;
	char *board_name = NULL;
	const char *dot;
	size_t base_len;
	size_t total_len;

	if (!name || !*name)
		return -EINVAL;

	skw_firmware_board_id_init(board_id, board_id_size);

	if (firmware_dir && *firmware_dir) {
		total_len = strlen(firmware_dir) + 1 + strlen(name) + 1;
		full_name = kmalloc(total_len, GFP_KERNEL);
		if (!full_name)
			return -ENOMEM;
		scnprintf(full_name, total_len, "%s/%s", firmware_dir, name);
	} else {
		full_name = kstrdup(name, GFP_KERNEL);
		if (!full_name)
			return -ENOMEM;
	}

	if (board_id && board_id[0]) {
		dot = strrchr(name, '.');
		if (dot) {
			base_len = dot - name;
			total_len = strlen(full_name) + 1 + strlen(board_id) + 1;
			board_name = kmalloc(total_len, GFP_KERNEL);
			if (board_name) {
				if (firmware_dir && *firmware_dir)
					scnprintf(board_name, total_len,
						  "%s/%.*s.%s%s",
						  firmware_dir,
						  (int)base_len, name,
						  board_id, dot);
				else
					scnprintf(board_name, total_len,
						  "%.*s.%s%s",
						  (int)base_len, name,
						  board_id, dot);
			}
		}
	}

	if (board_name) {
		pr_info("skw firmware: request board firmware %s\n", board_name);
		ret = skw_firmware_request_one(fw, board_name, dev, direct);
		if (!ret) {
			pr_info("skw firmware: loaded board firmware %s\n", board_name);
			kfree(full_name);
			kfree(board_name);
			return 0;
		}
		pr_info("skw firmware: board firmware %s not found, fallback to %s\n",
			board_name, full_name);
	}

	pr_info("skw firmware: request %s\n", full_name);
	ret = skw_firmware_request_one(fw, full_name, dev, direct);

	kfree(full_name);
	kfree(board_name);
	return ret;
}

#endif /* __SKW_FIRMWARE_HELPER_H__ */
