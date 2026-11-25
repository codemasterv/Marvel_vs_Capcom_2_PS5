#!/usr/bin/env python3
"""png2bc7dds.py -- an image to a BC7 (DXGI 98, BC7_UNORM) DDS with the DX10
header, one mip level: what the PS5 packager's pic0/pic1 converter reads.

Every 4x4 block is BC7 mode 6 (one RGBA line, 7-bit endpoints + p-bit, 4-bit
indices), endpoints from the block's principal axis. Opaque images only.

    png2bc7dds.py in.png out.dds [WIDTHxHEIGHT]
    png2bc7dds.py --check out.dds out.png      (decode it back to a PNG)
"""
import struct
import sys

import numpy as np
from PIL import Image

W4 = np.array([0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64], np.int32)


def encode(rgb):
    # Mode 6 shares the p-bit between RGB and A, so alpha forces p = 1: the
    # endpoints are quantized with p fixed to 1 and A at 127|1 = 255.
    h, w, _ = rgb.shape
    bh, bw = h // 4, w // 4
    px = rgb.reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float64)
    n = px.shape[0]
    mean = px.mean(1, keepdims=True)
    d = px - mean
    cov = np.einsum('nki,nkj->nij', d, d)
    axis = np.tile(np.array([0.577, 0.577, 0.577]), (n, 1))
    for _ in range(8):
        axis = np.einsum('nij,nj->ni', cov, axis)
        norm = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = np.where(norm > 1e-9, axis / np.maximum(norm, 1e-12), np.array([0.577, 0.577, 0.577]))
    t = np.einsum('nki,ni->nk', d, axis)
    e0 = np.clip(mean[:, 0] + t.min(1)[:, None] * axis, 0, 255)
    e1 = np.clip(mean[:, 0] + t.max(1)[:, None] * axis, 0, 255)
    q0 = np.clip(np.round((e0 - 1) / 2.0), 0, 127).astype(np.int32)
    q1 = np.clip(np.round((e1 - 1) / 2.0), 0, 127).astype(np.int32)
    v0 = (q0 << 1) | 1
    v1 = (q1 << 1) | 1
    pal = ((64 - W4)[None, :, None] * v0[:, None, :] + W4[None, :, None] * v1[:, None, :] + 32) >> 6
    dist = ((px[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(3)
    idx = dist.argmin(2).astype(np.int64)
    sw = idx[:, 0] >= 8
    q0, q1 = np.where(sw[:, None], q1, q0), np.where(sw[:, None], q0, q1)
    idx = np.where(sw[:, None], 15 - idx, idx)

    # Pack all blocks at once into two 64-bit halves.
    fields = [(np.full(n, 1 << 6, np.uint64), 7)]
    for c in range(3):
        fields.append((q0[:, c].astype(np.uint64), 7))
        fields.append((q1[:, c].astype(np.uint64), 7))
    fields += [(np.full(n, 127, np.uint64), 7), (np.full(n, 127, np.uint64), 7),
               (np.ones(n, np.uint64), 1), (np.ones(n, np.uint64), 1)]
    for i in range(16):
        fields.append((idx[:, i].astype(np.uint64), 3 if i == 0 else 4))
    lo = np.zeros(n, np.uint64)
    hi = np.zeros(n, np.uint64)
    pos = 0
    for val, nb in fields:
        if pos + nb <= 64:
            lo |= val << np.uint64(pos)
        elif pos >= 64:
            hi |= val << np.uint64(pos - 64)
        else:
            k = 64 - pos
            lo |= (val & np.uint64((1 << k) - 1)) << np.uint64(pos)
            hi |= val >> np.uint64(k)
        pos += nb
    assert pos == 128
    out = np.empty((n, 2), '<u8')
    out[:, 0] = lo
    out[:, 1] = hi
    return out.tobytes()


def dds_header(w, h, data_len):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000   # CAPS HEIGHT WIDTH PIXELFORMAT MIPMAPCOUNT LINEARSIZE
    hdr = struct.pack('<4s7I44x', b'DDS ', 124, flags, h, w, data_len, 0, 1)
    hdr += struct.pack('<2I4s5I', 32, 0x4, b'DX10', 0, 0, 0, 0, 0)   # pixel format: FOURCC DX10
    hdr += struct.pack('<5I', 0x1000, 0, 0, 0, 0)                     # caps: TEXTURE
    hdr += struct.pack('<5I', 98, 3, 0, 1, 0)                         # BC7_UNORM, TEXTURE2D, arraySize 1
    assert len(hdr) == 4 + 124 + 20
    return hdr


def decode(path):
    raw = open(path, 'rb').read()
    h, w = struct.unpack_from('<2I', raw, 12)
    assert raw[84:88] == b'DX10' and struct.unpack_from('<I', raw, 128)[0] == 98
    blocks = np.frombuffer(raw[148:], '<u8').reshape(-1, 2)
    img = np.zeros((h, w, 3), np.uint8)
    bw = w // 4
    for b, (lo, hi) in enumerate(blocks):
        v = int(lo) | (int(hi) << 64)
        assert v & 0x7F == 0x40, 'not mode 6'
        pos = 7
        e = []
        for _ in range(8):
            e.append((v >> pos) & 0x7F); pos += 7
        p0 = (v >> pos) & 1; p1 = (v >> (pos + 1)) & 1; pos += 2
        c0 = np.array([(e[0] << 1) | p0, (e[2] << 1) | p0, (e[4] << 1) | p0])
        c1 = np.array([(e[1] << 1) | p1, (e[3] << 1) | p1, (e[5] << 1) | p1])
        ix = []
        for i in range(16):
            nb = 3 if i == 0 else 4
            ix.append((v >> pos) & ((1 << nb) - 1)); pos += nb
        wv = W4[np.array(ix)]
        col = ((64 - wv)[:, None] * c0 + wv[:, None] * c1 + 32) >> 6
        by, bx = divmod(b, bw)
        img[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4] = col.reshape(4, 4, 3)
    return Image.fromarray(img)


def main():
    if sys.argv[1] == '--check':
        decode(sys.argv[2]).save(sys.argv[3])
        return
    im = Image.open(sys.argv[1]).convert('RGB')
    if len(sys.argv) > 3:
        tw, th = (int(x) for x in sys.argv[3].lower().split('x'))
        im = im.resize((tw, th), Image.LANCZOS)
    w, h = im.size
    assert w % 4 == 0 and h % 4 == 0, 'width and height must be multiples of 4'
    data = encode(np.asarray(im))
    with open(sys.argv[2], 'wb') as f:
        f.write(dds_header(w, h, len(data)))
        f.write(data)


if __name__ == '__main__':
    main()
