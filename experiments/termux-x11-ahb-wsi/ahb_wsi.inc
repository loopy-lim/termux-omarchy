/* Y900 opt-in prototype: retain a real AHB and import its linear data fd.
 * No opaque-fd reinterpretation, no CPU pixel copies, no removed fences.
 * The gralloc layout check deliberately limits this to the tested device. */
#ifdef __ANDROID__
static int loopy_sync(int fd, uint64_t flags) {
   struct dma_buf_sync sync = {.flags = flags};
   int rc;
   do { rc = ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync); } while (rc && (errno == EINTR || errno == EAGAIN));
   return rc;
}
struct loopy_native_handle { int version, num_fds, num_ints; int data[]; };
static struct {
   int (*allocate)(const AHardwareBuffer_Desc *, AHardwareBuffer **);
   void (*describe)(const AHardwareBuffer *, AHardwareBuffer_Desc *);
   const void *(*handle)(const AHardwareBuffer *);
   void (*release)(AHardwareBuffer *);
   int (*lock)(AHardwareBuffer *, uint64_t, int32_t, const ARect *, void **);
   int (*unlock)(AHardwareBuffer *, int32_t *);
   int (*send)(const AHardwareBuffer *, int);
   bool ready;
} loopy_ahb_api;
static pthread_once_t loopy_ahb_once = PTHREAD_ONCE_INIT;
static void loopy_load_ahb(void) {
   void *lib = dlopen("/system/lib64/libnativewindow.so", RTLD_NOW | RTLD_LOCAL);
   if (!lib) return;
#define AHB_LOAD(field, name) *(void **)(&loopy_ahb_api.field) = dlsym(lib, name)
   AHB_LOAD(allocate, "AHardwareBuffer_allocate");
   AHB_LOAD(describe, "AHardwareBuffer_describe");
   AHB_LOAD(handle, "AHardwareBuffer_getNativeHandle");
   AHB_LOAD(release, "AHardwareBuffer_release");
   AHB_LOAD(lock, "AHardwareBuffer_lock");
   AHB_LOAD(unlock, "AHardwareBuffer_unlock");
   AHB_LOAD(send, "AHardwareBuffer_sendHandleToUnixSocket");
#undef AHB_LOAD
   loopy_ahb_api.ready = loopy_ahb_api.allocate && loopy_ahb_api.describe && loopy_ahb_api.handle &&
      loopy_ahb_api.release && loopy_ahb_api.lock && loopy_ahb_api.unlock && loopy_ahb_api.send;
}
#define AHardwareBuffer_allocate loopy_ahb_api.allocate
#define AHardwareBuffer_describe loopy_ahb_api.describe
#define AHardwareBuffer_getNativeHandle loopy_ahb_api.handle
#define AHardwareBuffer_release loopy_ahb_api.release
#define AHardwareBuffer_lock loopy_ahb_api.lock
#define AHardwareBuffer_unlock loopy_ahb_api.unlock
#define AHardwareBuffer_sendHandleToUnixSocket loopy_ahb_api.send
struct loopy_ahb_info {
   struct wsi_image_info base;
   int fd;
   uint64_t size;
   uint32_t stride;
};

static VkResult
loopy_ahb_memory(const struct wsi_swapchain *chain,
                 const struct wsi_image_info *base, struct wsi_image *image)
{
   const struct loopy_ahb_info *info = (const void *)base;
   const struct wsi_device *wsi = chain->wsi;
   VkMemoryRequirements req;
   wsi->GetImageMemoryRequirements(chain->device, image->image, &req);
   if (req.size > info->size) return VK_ERROR_INVALID_EXTERNAL_HANDLE;
   VkMemoryFdPropertiesKHR props = {.sType = VK_STRUCTURE_TYPE_MEMORY_FD_PROPERTIES_KHR};
   if (!wsi->GetMemoryFdPropertiesKHR ||
       wsi->GetMemoryFdPropertiesKHR(chain->device, VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT,
                                     info->fd, &props) != VK_SUCCESS || !(req.memoryTypeBits & props.memoryTypeBits))
      return VK_ERROR_INVALID_EXTERNAL_HANDLE;
   int fd = os_dupfd_cloexec(info->fd);
   if (fd < 0) return VK_ERROR_OUT_OF_HOST_MEMORY;
   struct wsi_memory_allocate_info wi = {
      .sType = VK_STRUCTURE_TYPE_WSI_MEMORY_ALLOCATE_INFO_MESA,
      .implicit_sync = !base->explicit_sync && !chain->dma_buf_semaphore,
      .dma_buf_sync_file = chain->dma_buf_semaphore,
   };
   VkImportMemoryFdInfoKHR imp = {
      .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR, .pNext = &wi,
      .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT, .fd = fd,
   };
   VkMemoryDedicatedAllocateInfo dedicated = {
      .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,
      .pNext = &imp, .image = image->image,
   };
   VkMemoryAllocateInfo ai = {
      .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &dedicated,
      .allocationSize = info->size,
      .memoryTypeIndex = wsi_select_device_memory_type(wsi, req.memoryTypeBits & props.memoryTypeBits),
   };
   VkResult result = wsi->AllocateMemory(chain->device, &ai, &chain->alloc, &image->memory);
   if (result != VK_SUCCESS) { close(fd); return result; }
   image->dma_buf_fd = os_dupfd_cloexec(info->fd);
   if (image->dma_buf_fd < 0) return VK_ERROR_OUT_OF_HOST_MEMORY;
   image->drm_modifier = DRM_FORMAT_MOD_LINEAR;
   image->num_planes = 1;
   image->sizes[0] = info->size;
   image->row_pitches[0] = info->stride * 4;
   image->offsets[0] = 0;
   return VK_SUCCESS;
}

static VkResult
loopy_create_ahb_image(struct x11_swapchain *chain, struct x11_image *image)
{
   pthread_once(&loopy_ahb_once, loopy_load_ahb);
   if (!loopy_ahb_api.ready) return VK_ERROR_EXTENSION_NOT_PRESENT;
   const struct wsi_image_info *orig = &chain->base.image_info;
   const VkImageCreateInfo *ci = &orig->create;
   /* No silent layout guess for multi-plane, array or blit swapchains. */
   if (chain->base.wsi->sw || !chain->has_dri3_modifiers || orig->finish_create ||
       (ci->flags & VK_IMAGE_CREATE_PROTECTED_BIT) || orig->img_compr_ctrl.sType ||
       ci->arrayLayers != 1 || ci->mipLevels != 1 || ci->samples != VK_SAMPLE_COUNT_1_BIT ||
       (ci->format != VK_FORMAT_B8G8R8A8_UNORM && ci->format != VK_FORMAT_R8G8B8A8_UNORM &&
        ci->format != VK_FORMAT_B8G8R8A8_SRGB && ci->format != VK_FORMAT_R8G8B8A8_SRGB))
      return VK_ERROR_FORMAT_NOT_SUPPORTED;
   AHardwareBuffer_Desc d = {
      .width = ci->extent.width, .height = ci->extent.height, .layers = 1,
      .format = (ci->format == VK_FORMAT_B8G8R8A8_UNORM || ci->format == VK_FORMAT_B8G8R8A8_SRGB) ? 5 : 1,
      .usage = AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN | AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN |
               AHARDWAREBUFFER_USAGE_GPU_SAMPLED_IMAGE | AHARDWAREBUFFER_USAGE_GPU_FRAMEBUFFER,
   };
   AHardwareBuffer *ahb = NULL;
   if (AHardwareBuffer_allocate(&d, &ahb) != 0) return VK_ERROR_OUT_OF_DEVICE_MEMORY;
   AHardwareBuffer_describe(ahb, &d);
   const struct loopy_native_handle *h = AHardwareBuffer_getNativeHandle(ahb);
   struct stat st;
   if (!h || h->num_fds < 1 || d.stride < d.width || d.stride > UINT32_MAX / 4 ||
       fstat(h->data[0], &st) || st.st_size <= 0 || st.st_size > UINT32_MAX ||
       (uint64_t)d.stride * d.height * 4 > (uint64_t)st.st_size) {
      AHardwareBuffer_release(ahb); return VK_ERROR_INVALID_EXTERNAL_HANDLE;
   }
   /* Gralloc CPU usage alone is not a cross-device modifier contract.
    * Verify the exact linear offset/pitch before GPU import. */
   void *locked = NULL;
   if (AHardwareBuffer_lock(ahb, AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN, -1, NULL, &locked)) {
      AHardwareBuffer_release(ahb); return VK_ERROR_INVALID_EXTERNAL_HANDLE;
   }
   uint64_t last = (uint64_t)(d.height - 1) * d.stride + d.width - 1;
   ((uint32_t *)locked)[0] = 0x12345678;
   ((uint32_t *)locked)[last] = 0x87654321;
   int unlock = AHardwareBuffer_unlock(ahb, NULL);
   uint32_t *mapped = mmap(NULL, st.st_size, PROT_READ, MAP_SHARED, h->data[0], 0);
   bool linear = false;
   if (!unlock && mapped != MAP_FAILED && !loopy_sync(h->data[0], DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ)) {
      linear = mapped[0] == 0x12345678 && mapped[last] == 0x87654321;
      if (loopy_sync(h->data[0], DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ)) linear = false;
   }
   if (mapped != MAP_FAILED) munmap(mapped, st.st_size);
   if (!linear) { AHardwareBuffer_release(ahb); return VK_ERROR_INVALID_EXTERNAL_HANDLE; }
   struct loopy_ahb_info info = {.base = *orig, .fd = h->data[0], .size = st.st_size, .stride = d.stride};
   VkSubresourceLayout layout = {.offset = 0, .rowPitch = (uint64_t)d.stride * 4};
   VkImageDrmFormatModifierExplicitCreateInfoEXT mod = {
      .sType = VK_STRUCTURE_TYPE_IMAGE_DRM_FORMAT_MODIFIER_EXPLICIT_CREATE_INFO_EXT,
      .drmFormatModifier = DRM_FORMAT_MOD_LINEAR, .drmFormatModifierPlaneCount = 1,
      .pPlaneLayouts = &layout,
   };
   info.base.create.tiling = VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT;
   info.base.create.pNext = &mod;
   info.base.ext_mem.pNext = NULL;
   info.base.ext_mem.handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT;
   info.base.wsi.pNext = NULL;
   info.base.usage2.pNext = NULL;
   __vk_append_struct(&info.base.create, &info.base.ext_mem);
   __vk_append_struct(&info.base.create, &info.base.wsi);
   __vk_append_struct(&info.base.create, &info.base.usage2);
   if (ci->flags & VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT) {
      info.base.format_list.pNext = NULL;
      __vk_append_struct(&info.base.create, &info.base.format_list);
   }
   info.base.create_mem = loopy_ahb_memory;
   VkResult result = wsi_create_image(&chain->base, &info.base, &image->base);
   if (result != VK_SUCCESS) { AHardwareBuffer_release(ahb); return result; }
   image->loopy_ahb = ahb;
   fprintf(stderr, "[LOOPY-AHB-WSI] imported %ux%u stride=%u bytes=%lld\n", d.width, d.height, d.stride, (long long)st.st_size);
   return VK_SUCCESS;
}
#endif
