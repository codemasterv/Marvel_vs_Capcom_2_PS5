# PS3 PKG extractor (retail, AES-128-CTR with the public PS3 package key).
import sys, os, struct
from Crypto.Cipher import AES
from Crypto.Util import Counter
PS3_KEY = bytes.fromhex("2E7B71D7C9C9A14EA3221F188828B8F8")
src, out = sys.argv[1], sys.argv[2]
f = open(src, "rb")
h = f.read(0xC0)
rev, typ = struct.unpack(">HH", h[4:8])
items = struct.unpack(">I", h[0x14:0x18])[0]
data_off, data_size = struct.unpack(">QQ", h[0x20:0x30])
cid = h[0x30:0x60].rstrip(b"\0").decode()
iv = int.from_bytes(h[0x70:0x80], "big")
print("rev %04x type %04x items %d data @%x size %x  %s" % (rev, typ, items, data_off, data_size, cid))
def read(off, size):
    blk = off // 16
    start = off - blk * 16
    f.seek(data_off + blk * 16)
    raw = f.read(start + size)
    c = AES.new(PS3_KEY, AES.MODE_CTR, counter=Counter.new(128, initial_value=(iv + blk) & ((1 << 128) - 1)))
    return c.decrypt(raw)[start:start + size]
table = read(0, items * 32)
os.makedirs(out, exist_ok=True)
for i in range(items):
    no, ns, do, ds, flags, _ = struct.unpack(">IIQQII", table[i*32:(i+1)*32])
    name = read(no, ns).decode("utf-8", "replace")
    kind = flags & 0xFF
    p = os.path.join(out, name)
    if kind == 4 or (flags & 0xFF) == 0x04:
        os.makedirs(p, exist_ok=True); continue
    os.makedirs(os.path.dirname(p) or out, exist_ok=True)
    with open(p, "wb") as o:
        pos = 0
        while pos < ds:
            n = min(1 << 24, ds - pos)
            o.write(read(do + pos, n)); pos += n
    if i < 12 or name.endswith((".BIN", ".SFO", ".self", ".sprx")):
        print("%08x %10d %s" % (flags, ds, name))
