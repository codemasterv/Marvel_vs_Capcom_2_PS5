/* spu_workloads.c -- Marvel vs. Capcom 2 (NPUB30068 v1.01) SPURS job images.
 * The two job binaries live in the EBOOT's data (EA 0x546500, 42368 bytes and
 * EA 0x550B00, 736 bytes), are DMA'd to LS 0 and entered at 0. Lifted with
 * spu_lifter --auto-functions from a minimal ELF wrap (base 0, entry 0) and
 * registered by the FNV-1a-64 fingerprint of the raw image, which is what
 * spu_workload_dispatch_job computes over sizeBinary bytes. */
#include "spu_workload.h"

extern void spu_begin_image(int image_id);
extern void mvc2_job_main_spu_func_00000000(spu_context*);
extern void mvc2_job_main_spu_recomp_register(void);
extern void mvc2_job_small_spu_func_00000000(spu_context*);
extern void mvc2_job_small_spu_recomp_register(void);

void mvc2_spu_register_all(void)
{
    spu_begin_image(1); mvc2_job_main_spu_recomp_register();
    spu_workload_register_img(0xF06AFECD930AD1F0ULL, mvc2_job_main_spu_func_00000000, 1, "job_main");
    spu_begin_image(2); mvc2_job_small_spu_recomp_register();
    spu_workload_register_img(0xDFFE2307E12F8D4DULL, mvc2_job_small_spu_func_00000000, 2, "job_small");
    spu_begin_image(0);
}

__attribute__((constructor)) static void mvc2_spu_register_all_ctor(void)
{
    mvc2_spu_register_all();
}
