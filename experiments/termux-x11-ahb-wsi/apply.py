from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/vulkan/wsi/wsi_common_x11.c';s=p.read_text();assert 'loopy_ahb' not in s
s=s.replace('#include <fcntl.h>','#include <fcntl.h>\n#ifdef __ANDROID__\n#include <android/hardware_buffer.h>\n#include <sys/socket.h>\n#include <poll.h>\n#include <dlfcn.h>\n#include <pthread.h>\n#include <sys/ioctl.h>\n#include <linux/dma-buf.h>\n#include <sys/stat.h>\n#include <sys/mman.h>\n#endif')
s=s.replace('struct x11_image {\n','struct x11_image {\n   void *loopy_ahb;\n')
needle='static VkResult\nx11_image_init('
s=s.replace(needle,Path(__file__).with_name('ahb_wsi.inc').read_text()+'\n'+needle)
needle='''   result = wsi_create_image(&chain->base, &chain->base.image_info,
                             &image->base);'''
assert s.count(needle)==1
s=s.replace(needle,'''#ifdef __ANDROID__
   if (getenv("LOOPY_X11_AHB") && !strcmp(getenv("LOOPY_X11_AHB"), "1"))
      result = loopy_create_ahb_image(chain, image);
   else
#endif
'''+needle)
needle='   if (image->base.drm_modifier != DRM_FORMAT_MOD_INVALID) {'
assert s.count(needle)==1
s=s.replace(needle,'''#ifdef __ANDROID__
   if (image->loopy_ahb) {
      int sockets[2];
      if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets)) goto fail_image;
      cookie = xcb_dri3_pixmap_from_buffers_checked(chain->conn, image->pixmap,
                  chain->window, 1, pCreateInfo->imageExtent.width, pCreateInfo->imageExtent.height,
                  image->base.row_pitches[0], 0, 0, 0, 0, 0, 0, 0, chain->depth, bpp, 1255, &sockets[1]);
      xcb_flush(chain->conn);
      struct pollfd waiter = {.fd = sockets[0], .events = POLLIN};
      uint8_t request;
      int ready;
      do { ready = poll(&waiter, 1, 3000); } while (ready < 0 && errno == EINTR);
      if (ready <= 0 || !(waiter.revents & POLLIN) || read(sockets[0], &request, 1) != 1 ||
          request != 1 || AHardwareBuffer_sendHandleToUnixSocket(image->loopy_ahb, sockets[0])) {
         close(sockets[0]); goto fail_pixmap;
      }
      close(sockets[0]);
   } else
#endif
'''+needle)
needle='   wsi_destroy_image(&chain->base, &image->base);'
s=s.replace(needle,needle+'''
#ifdef __ANDROID__
   if (image->loopy_ahb) {
      AHardwareBuffer_release(image->loopy_ahb);
      image->loopy_ahb = NULL;
   }
#endif''')
p.write_text(s)

root=Path(sys.argv[1])/'src/vulkan/wsi'
p=root/'wsi_common.h';s=p.read_text();s=s.replace('WSI_CB(GetMemoryFdKHR);','WSI_CB(GetMemoryFdKHR);\n   WSI_CB(GetMemoryFdPropertiesKHR);');p.write_text(s)
p=root/'wsi_common.c';s=p.read_text();s=s.replace('if (!wsi->sw)\n      WSI_GET_CB(GetMemoryFdKHR);', 'if (!wsi->sw) {\n      WSI_GET_CB(GetMemoryFdKHR);\n      WSI_GET_CB(GetMemoryFdPropertiesKHR);\n   }');p.write_text(s)

# The VA research source disabled this extension for FFmpeg's unsupported
# OPAQUE_FD timeline path. Native Zink needs the implemented binary SYNC_FD
# entry points for dma-buf implicit fences. This build is native Weston only.
p=Path(sys.argv[1])/'src/freedreno/vulkan/tu_device.cc'
s=p.read_text().replace('.KHR_external_semaphore_fd = !is_kgsl(device->instance)', '.KHR_external_semaphore_fd = true')
p.write_text(s)
# Termux uses Linux-style fd synchronization with Android's Bionic libc.
p=Path(sys.argv[1])/'src/util/detect_os.h'
s=p.read_text().replace('#if defined(__ANDROID__)', '#if defined(ANDROID)')
p.write_text(s)
p=Path(sys.argv[1])/'src/util/os_file.c'
s=p.read_text().replace('#include "detect_os.h"', '#include "detect_os.h"\n#if DETECT_OS_LINUX\n#include <sys/epoll.h>\n#endif')
p.write_text(s)
for name in ('src/vulkan/meson.build','src/vulkan/wsi/meson.build'):
 p=Path(sys.argv[1])/name
 s=p.read_text().replace('if system_has_kms_drm and not with_platform_android', "if system_has_kms_drm and not with_platform_android and host_machine.system() != 'android'")
 p.write_text(s)
