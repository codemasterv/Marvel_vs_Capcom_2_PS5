# Marvel vs. Capcom 2 — PS5 (ps3recomp static recomp)

Title ID **PPSA30068**. A homebrew title for a jailbroken PS5 (fake-signed eboot,
same loader requirements as the PS5_VulkanTemplate titles).

## Files on the console

Everything is in the title's own folder. The package holds the program; the
game data comes from your own PS3 packages and goes in `mvc2/` beside it:

```
PPSA30068/
  eboot.bin, sce_sys/, sce_module/        the title (replaced by each build)
  mvc2/                                   your data (kept across builds)
    EBOOT.ps3               decrypted v1.01 EBOOT, wrapped: tools/wrap_ps3elf.py EBOOT.elf EBOOT.ps3
                            (a .pkg builder signs anything that starts \x7FELF; the wrapper header stops that.
                            A plain EBOOT.elf still works for a folder install.)
    game/NPUB30068/         the update package's folder (tools/pkg_extract.py)
    gamedata/               saves and trophies (created)
    env.txt                 optional, KEY=VALUE per line ('#' comments)
    log.txt                 written every run
```

The title looks for `mvc2/EBOOT.ps3` (or `EBOOT.elf`) in its own folder first and falls back to
`/data/mvc2` (the layout of the first builds). A new build only replaces
`eboot.bin`, `sce_sys/` and `sce_module/`; copy those over and leave `mvc2/`.

Installed as a .pkg the title's folder is read-only: the data is still read from
`mvc2/` inside it, and saves, trophies, `log.txt` and temp files go to
`/data/mvc2/` instead. An `env.txt` there overrides one shipped in the package.

## Controls

DualSense as a DualShock 3: OPTIONS = START, touch pad click = SELECT, the rest
one to one. Up to 4 players, one per signed-in user, in join order.

## env.txt knobs

| key | default | effect |
| --- | --- | --- |
| `PS3RECOMP_VK_GUEST_PROGRAMS` | `1` | the game's own shaders (0 = fixed-function fallback) |
| `PS3RECOMP_PS5_REFRESH` | `60` | display mode refresh to pick (e.g. `120`) |
| `PS3_VFS_ROOT` | the data folder | where `/dev_hdd0/game/...` resolves |
| `PS3RECOMP_PS5_LOG_ALL` | `0` | 1 = log every line (each message otherwise logs 16 times, then stops) |
| `PS3RECOMP_VK_FPS` | `1` | frame-rate lines in the log |
| `VK_DRAW_BATCH` | `1` | draws batched per GPU submission (0 = one submit per draw, very slow) |
| `RSX_ENGINE_SURFACE_EXACT` | `1` | render targets reused only at their own size (0 = old behaviour, sprites resize) |

Any other ps3recomp environment switch works the same way.

## Building

```
# deps: PS5_VulkanTemplate (bootstrap: payload SDK fork), PS5_Vulkan (RADV release
# archive + native tool), glslang 15.1.0 cross-built with prospero.cmake
SDK=~/ps5ws/PS5_VulkanTemplate/.deps/native/ps5-payload-sdk
cmake -S port -B port-ps5-build -G Ninja -DPORT_PPU_OPT=-O2 \
  -DCMAKE_TOOLCHAIN_FILE=$SDK/toolchain/prospero.cmake \
  -DPS3RECOMP_DIR=$PWD/ps3recomp -DRECOMP_DIR=$PWD/recompiled \
  -DCMAKE_BUILD_TYPE= -DPS3RECOMP_RSX_VULKAN=ON \
  -DPS3RECOMP_VULKAN_INCLUDE_DIR=~/ps5ws/PS5_Vulkan/.deps/native/radv-release/include \
  -Dglslang_DIR=~/ps5ws/deps/glslang-ps5-install/lib/cmake/glslang
ninja -C port-ps5-build -k 0          # compiles everything; the payload-style link fails, that's expected
bash port/ps5/link-mvc2.sh port-ps5-build ~/ps5ws/PS5_Vulkan $SDK ~/ps5ws/deps/glslang-ps5-install/lib
# -> port-ps5-build/dist/PPSA30068/
```

The ps3recomp changes are on its `ps5` branch (patch in `patches/ps3recomp-ps5.patch`).
