# NPDRM SELF -> ELF for free-license (HAN/"no RAP") PS3 executables, after
# RPCS3's unself.cpp. Usage: unself.py EBOOT.BIN out.elf
import sys, struct, zlib
from Crypto.Cipher import AES
from Crypto.Util import Counter
NP_KLIC_FREE = bytes.fromhex("72F990788F9CFF745725F08E4C128387")
NP_KLIC_KEY = bytes.fromhex("F2FBCA7A75B04EDC1390638CCDFDD1EE")
NPDRM_KEYS = {1: ("F9EDD0301F770FABBA8863D9897F0FEA6551B09431F61312654E28F43533EA6B", "A551CCB4A42C37A734A2B4F9657D5540")}
d = open(sys.argv[1], "rb").read()
magic, hver, flags, stype, meta, hsize, esize = struct.unpack(">IIHHIQQ", d[:0x20])
ext = struct.unpack(">10Q", d[0x20:0x70])
_, pid_off, ehdr_off, phdr_off, shdr_off, segext_off, ver_off, sup_off, sup_size, _ = ext
auth, vendor, ptype, sver = struct.unpack(">QIIQ", d[pid_off:pid_off + 0x18])
print("revision %x, type %d, program type %d" % (flags, stype, ptype))
# supplemental headers: find NPD (type 3)
license = None
o = sup_off
while o < sup_off + sup_size:
    t, sz, nxt = struct.unpack(">IIQ", d[o:o + 16])
    if t == 3:
        npd = d[o + 16:o + 16 + 0x80]
        license = struct.unpack(">I", npd[8:12])[0]
        print("NPD license %d, content %s" % (license, npd[16:0x40].rstrip(b"\0").decode()))
    if sz == 0: break
    o += sz
assert license == 3, "not a free-license SELF (needs a RAP)"
klic = AES.new(NP_KLIC_KEY, AES.MODE_ECB).decrypt(NP_KLIC_FREE)
mi = d[meta + 0x20:meta + 0x60]
mi = AES.new(klic, AES.MODE_CBC, iv=bytes(16)).decrypt(mi)
erk, riv = (bytes.fromhex(x) for x in NPDRM_KEYS[flags])
mi = AES.new(erk, AES.MODE_CBC, iv=riv).decrypt(mi)
key, kpad, iv, ivpad = mi[:16], mi[16:32], mi[32:48], mi[48:64]
assert kpad[0] == 0 and ivpad[0] == 0, "metadata info did not decrypt"
mh = d[meta + 0x60:hsize]
mh = AES.new(key, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(iv, "big"))).decrypt(mh)
_, _, nsec, nkeys, _, _, _ = struct.unpack(">QIIIIII", mh[:0x20])
secs = [struct.unpack(">QQ8I", mh[0x20 + i * 0x30:0x50 + i * 0x30]) for i in range(nsec)]
keys = mh[0x20 + nsec * 0x30:0x20 + nsec * 0x30 + nkeys * 16]
# ELF
eh = d[ehdr_off:ehdr_off + 0x40]
e_phoff, e_shoff = struct.unpack(">QQ", eh[0x20:0x30])
e_phentsize, e_phnum, e_shentsize, e_shnum = struct.unpack(">HHHH", eh[0x36:0x3E])
phs = [struct.unpack(">IIQQQQQQ", d[phdr_off + i * 56:phdr_off + (i + 1) * 56]) for i in range(e_phnum)]
size = max([e_phoff + e_phnum * 56] + [p[2] + p[6] for p in phs] + ([e_shoff + e_shnum * 64] if e_shnum else []))
out = bytearray(size)
out[0:0x40] = eh
out[e_phoff:e_phoff + e_phnum * 56] = d[phdr_off:phdr_off + e_phnum * 56]
for off, sz, typ, idx, hashed, sha, enc, kidx, ividx, comp in secs:
    blob = d[off:off + sz]
    if enc == 3:
        k = keys[kidx * 16:kidx * 16 + 16]; v = keys[ividx * 16:ividx * 16 + 16]
        blob = AES.new(k, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(v, "big"))).decrypt(blob)
    if typ != 2: continue
    if comp == 2: blob = zlib.decompress(blob)
    p_off = phs[idx][2]
    out[p_off:p_off + len(blob)] = blob
if e_shnum and shdr_off:
    out[e_shoff:e_shoff + e_shnum * 64] = d[shdr_off:shdr_off + e_shnum * 64]
open(sys.argv[2], "wb").write(out)
print("wrote %s, %d bytes, %d program headers" % (sys.argv[2], len(out), e_phnum))
