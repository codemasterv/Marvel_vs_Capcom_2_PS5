#!/usr/bin/env python3
"""wrap_ps3elf.py EBOOT.elf EBOOT.ps3 -- put the 16-byte "PS3RECOMP-ELF" header
in front of the PS3 program, so a PS5 package builder does not take it for a PS5
ELF to sign. The runtime's ppu_load_elf strips it again."""
import sys
data = open(sys.argv[1], 'rb').read()
if data[:16] == b'PS3RECOMP-ELF\0\0\0':
    data = data[16:]
assert data[:4] == b'\x7fELF', 'not an ELF'
open(sys.argv[2], 'wb').write(b'PS3RECOMP-ELF\0\0\0' + data)
