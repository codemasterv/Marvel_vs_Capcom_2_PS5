#!/usr/bin/env bash
# MvC2 recomp - link the PS5 title and package its folder.
#
#   link-mvc2.sh BUILD_DIR PS5_VULKAN_DIR SDK GLSLANG_LIB_DIR
#
# The recipe is PS5_VulkanTemplate's tools/link-title.sh (MIT, Mihawk): the
# objects are linked with PS5_Vulkan's RADV archive through its link recipe
# (tools/radv-link.sh), turned into a fake SELF by its native tool, and put in
# dist/PPSA30068/ with sce_sys/ and libc.prx.
set -euo pipefail
work=$(realpath "$1") vulkan=$(realpath "$2") sdk=$(realpath "$3") glslang=$(realpath "$4")
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
archive=$vulkan/.deps/native/radv-release/lib/libvulkan_radeon.ps5.a
export PS5_CLANG=${PS5_CLANG:-$(command -v clang-18 || command -v clang)}
tool=$vulkan/build/host/ps5-native-tool
native=$vulkan/tooling/native
param=$here/sce_sys/param.json
out=$work/ps5link
mkdir -p "$out/obj" "$out/stubs"
cc() { PS5_PAYLOAD_SDK="$sdk" sh "$vulkan/tooling/prospero-clang18" "$@"; }

mapfile -t objects < <(find "$work/CMakeFiles/MyGameRecomp.dir" -name '*.o' | sort)
runtime=$work/ps3recomp_sdk/libps3recomp_runtime.a
echo "==> ${#objects[@]} objects + runtime"

cc -std=c++20 -O2 -fno-exceptions -fno-rtti -c "$native/app_crt.cpp" -o "$out/obj/app_crt.o"
stub() {
    local library=$1 source=$2
    cc -std=c11 -O2 -fPIC -c "$vulkan/$source" -o "$out/obj/${library}_stub.o"
    "$sdk/bin/prospero-lld" --shared -soname "${library}.prx" -o "$out/stubs/${library}.so" "$out/obj/${library}_stub.o"
}
stub libSceAgc vendor/ps5/sdk/stubs/agc_canary_link_stub.c
stub libSceAgcDriver vendor/ps5/sdk/stubs/agc_driver_canary_link_stub.c

# shellcheck source=/dev/null
source "$vulkan/tools/radv-link.sh"
radv_link_recipe "$vulkan" "$sdk" "$archive" || exit 2
if grep -q " T ps5_localeconv$" <<<"$("$sdk/bin/llvm-nm" --defined-only "$sdk/target/lib/libps5platform.a" 2>/dev/null)" &&
        [[ " ${radv_link_flags[*]} " != *" --defsym=localeconv=ps5_localeconv "* ]]; then
    printf '{\n    local:\n        localeconv;\n};\n' > "$out/localeconv-local.map"
    radv_link_flags+=(--defsym=localeconv=ps5_localeconv --version-script "$out/localeconv-local.map")
fi
# --no-dynamic-linker keeps Mesa's unresolved weak entry points out of .dynsym
# (they resolve to null at link time, as in PS5_Vulkan's own build.sh); the
# converter would otherwise look for them among the SDK's exports.
"$sdk/bin/prospero-lld" "${radv_linker_script[@]}" --eh-frame-hdr --no-dynamic-linker --wrap=printf --wrap=fprintf "${radv_link_flags[@]}" \
    --version-script "$native/app-symbols.map" --exclude-libs=ALL \
    -e _start -o "$out/llvm-pie.elf" \
    "$out/obj/app_crt.o" "${objects[@]}" \
    --whole-archive "$runtime" --no-whole-archive \
    "$glslang/libglslang-default-resource-limits.a" "$glslang/libSPIRV.a" "$glslang/libglslang.a" \
    "$glslang/libMachineIndependent.a" "$glslang/libGenericCodeGen.a" "$glslang/libOSDependent.a" \
    "$out/stubs/libSceAgc.so" "$out/stubs/libSceAgcDriver.so" \
    "${radv_link_inputs[@]}" \
    --as-needed "$sdk"/target/lib/*.so

null_imports=$(comm -23 \
    <("$sdk/bin/llvm-nm" -D --undefined-only "$out/llvm-pie.elf" | awk '$1 == "U" { sub(/@.*/, "", $2); print $2 }' | sort -u) \
    <(for library in "$sdk"/target/lib/*.so "$out/stubs/libSceAgc.so" "$out/stubs/libSceAgcDriver.so"; do
        case ${library##*/} in libkernel_sys.so | libScePosixForWebKit.so) continue ;; esac
        "$sdk/bin/llvm-nm" -D --defined-only "$library" 2>/dev/null | awk '{ print $NF }'
    done | sort -u))
if [[ -n $null_imports ]]; then
    echo "link-mvc2.sh: imports no loaded module exports (null at run time): ${null_imports//$'\n'/ }" >&2
    exit 1
fi
"$tool" link --in "$out/llvm-pie.elf" --out "$out/eboot.elf" \
    --stub-dir "$sdk/target/lib" --stub "$out/stubs/libSceAgc.so" \
    --stub "$out/stubs/libSceAgcDriver.so" --module-sdk 0x02000009 \
    --companion-sdk 0x08050001 --file-name eboot.elf

title_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["titleId"])' "$param")
app=$work/dist/$title_id
rm -rf "$app"; mkdir -p "$app/sce_sys" "$app/sce_module"
"$tool" self --sign --in "$out/eboot.elf" --out "$app/eboot.bin" --magic 0x1D3D154F
"$tool" self --inspect --file "$app/eboot.bin" > /dev/null
cp "$param" "$app/sce_sys/param.json"
for asset in icon0.png pic0.dds pic1.dds pic1.png snd0.at9 keystone license.dat license.info; do
    [[ -f $here/sce_sys/$asset ]] && cp "$here/sce_sys/$asset" "$app/sce_sys/$asset"
done
(cd "$vulkan/runtime" && sha256sum --check --strict --quiet libc.prx.sha256)
cp "$vulkan/runtime/libc.prx" "$app/sce_module/libc.prx"
printf '==> %s: %s (eboot.bin %s bytes)\n' "$title_id" "$app" "$(stat -c %s "$app/eboot.bin")"
