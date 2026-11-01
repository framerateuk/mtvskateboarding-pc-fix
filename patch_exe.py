#!/usr/bin/env python3
"""Patch MTV Sports: Skateboarding's Direct3D exe (the disc's Program\\mtv.exe, 602,112 bytes, MD5
80a10c5b34519e5fac1e4d27ac6ded14, linked 31 Aug 2000, MSVC, file version 1.0.0.1; Darkblack / THQ) into a copy.

  patch_exe.py <mtv.exe> <out.exe>   write the patched exe (refuses, writes nothing, on any unexpected byte)
  (build.py calls patch(bytes) directly)
  patch_exe.py --check-caves         re-assemble caves.s with clang and compare with CAVE below

New code (caves.s, assembled bytes in CAVE) goes into a section the patch adds: ".rdeck", VA 0x6bb000, 0x1000 bytes
at file offset 0x93000 (the end of the file, after .reloc), readable / writable / executable; its variables from
0x6bbc00. The section table had room for a seventh entry (it ended at 0x2d8, the first section starts at 0x1000);
SizeOfImage 0x2bb000 -> 0x2bc000. The exe has no checksum and loads at its 0x400000 base; the header now also says
"relocations stripped", so no loader ever moves it.

There is no CD check to patch: the exe never looks for the disc (its only GetDriveTypeA is the C runtime's
_getdcwd; the "cdaudio" MCI strings are dead code, the exe does not even import winmm). The disc's protection is
in its layout (docs/TECHNICAL.md, "The disc"), not in the exe.

  rdeck       the section (above) with the code of caves.s.
  nodialog    the start-up dialog ("MTV Sports Skateboarding": display device, display mode, triple buffer, vsync,
              full screen, low-detail textures, OK / Exit / Test Mode, a version box and THQ / MTV web links;
              0x452410, run from WinMain 0x450f00). It is no longer created: CreateDialogParamA (0x4524a2) is
              "xor eax, eax" (no window; the calls that follow on its handle fail harmlessly), its message loop
              (WaitMessage, 0x452523) is jumped over ("jmp 0x452578", as if OK had been pressed), and the display
              mode the code then reads from the dialog's list (0x4525ae, "mov [0x5383e0], eax") comes from
              pickmode: 1024x768 16-bit from the game's own mode list (filled from DirectDraw by 0x42cf60 just
              before), else 640x480 16-bit (the dialog's default). The device list's selection reads 0 = the first
              DirectDraw device (the primary display), as the dialog's default. The dialog's other settings keep
              their defaults (0x452419): vsync on, full screen, no triple buffer, full-detail textures.
  noreg       the same settings were kept in the registry (HKLM\\Software\\Darkblack\\MTVSkateboarding: DDVSync,
              DDFullscreen, DDTripleBuffer, DDSmallTextures): the read (call 0x451790 at 0x452439, which also created
              the key) is gone, and the write after "OK" (RegOpenKeyExA at 0x4526d0) now fails ("add esp, 0x14;
              push 2; pop eax" = ERROR_FILE_NOT_FOUND), so it writes nothing. No other registry use exists (the
              Test Mode path's own write, 0x4527e2, is not reachable).
  pad         player one's controls default to the keyboard (its input slot 0x556740, docs/TECHNICAL.md "Pad"); the input
              update (0x450700, every frame) fills that slot with "call 0x40c280" (0x450727): now "call kbdpad",
              which adds the XInput pad to it as the keyboard would press it (SideWinder button numbers, left stick
              / D-pad = the arrow keys). The joystick poll's GetDeviceState (0x45143a, "call [ecx + 0x24]; test
              eax, eax") is now "call joygds": for the first DirectInput joystick, the reading written from XInput in
              the same numbering (a pad chosen on the Game Controls screen; Proton's DirectInput would give an Xbox
              pad's buttons in another order and its triggers on one shared axis).
  nocursor    the window class (RegisterClassA "GenericClass", 0x45100b) had LoadCursorA(0, IDC_ARROW) as its
              cursor (0x450fde: "push 0x7f00; push ebx; mov [esp + 0x34], eax; call [LoadCursorA]", the mov
              storing the class icon): now "mov [esp + 0x2c], eax; xor eax, eax" (the icon stored at the same place,
              no class cursor). The display-mode scan's hourglass and arrow (0x42cf75, 0x42d291: "call
              [LoadCursorA]" before SetCursor) are "add esp, 8; xor eax, eax" (SetCursor(NULL)). The game itself
              calls ShowCursor(FALSE) when its display is up (0x4412a0).

Not patched (docs/TECHNICAL.md): the frame timing (the main loop 0x448040 measures each frame in
milliseconds from QueryPerformanceCounter and moves the game by that much; its wait for the millisecond counter to
change, 0x44817d, is at most one millisecond: dgVoodoo's vsync / FPSLimit hold 60 frames a second); the display
check (0x451b50: the desktop must be at least 640x480 at 16 bits; Proton's is 1280x800x32); the video-memory check
(0x42cd88, unsigned; dgVoodoo reports 256 MB); KICKFLIP.SAV (saves, high scores, settings) is a file in the game's
folder; the Indeo 3 movies are rewritten by make_raw_avi.py, not by an exe patch.
"""
import hashlib, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE, MD5 = 602112, "80a10c5b34519e5fac1e4d27ac6ded14"
DELTA = 0x400000                       # .text (VA 0x401000, file offset 0x1000): file offset = VA - 0x400000
def T(va):
    assert 0x401000 <= va < 0x459f42, hex(va)
    return va - DELTA

def rel32(src, dst, op):               # e8 / e9 at src (5 bytes) -> dst
    return bytes([op]) + (dst - (src + 5)).to_bytes(4, "little", signed=True)

SECT_VA, SECT_RVA, SECT_OFF, SECT_SIZE = 0x6bb000, 0x2bb000, 0x93000, 0x1000
CAVE_VA = SECT_VA
CAVE = bytes.fromhex(
    "ff742404e87712d5ff60e86302000085c07465be40675500e8aa0000008b0d24bc6b00a324bc6b0009461cf7d121c109"
    "4e3ce8450000008b0d28bc6b00a328bc6b0085c0740e833e007509890639c87403894620e83c0000008b0d2cbc6b00a3"
    "2cbc6b0085c07410837e0400750a89460439c8740389462461c20400f60508bc6b00047538f60508bc6b00087533a10c"
    "bc6b00eb17f60508bc6b0002751ff60508bc6b0001751aa110bc6b003d80c1ffff7c0a3d803e00007f0731c0c383c8ff"
    "c3b801000000c3538b1508bc6b0031db31c00fb70c4560b36b0085ca74030fabc34083f80a72eb833d1cbc6b00407e03"
    "83cb40833d20bc6b00407e0681cb8000000089d85bc3ff74240cff74240cff74240cff5124608b7c24248b74242c3b3d"
    "e0805a007516e84701000085c0740de80e000000c744241c000000006185c0c20c005789f7b94400000031c0f3ab5fa1"
    "0cbc6b00e891000000f60508bc6b0004740231c0f60508bc6b00087405b8ffff00008906a110bc6b00f7d8e86a000000"
    "f60508bc6b0001740231c0f60508bc6b00027405b8ffff0000894604b80080000089460889460c894610894614894618"
    "89461c83c8ff89462489462889462c8b1508bc6b0083e20f8b049574b36b00894620e8f0feffff31c90fa3c87305c644"
    "0e30804183f90a72f0c389c19931d029d03da91e00007f06b800800000c389c80500800000790231c03dffff00007e05"
    "b8ffff0000c3535152bb00040000ba00030000e81e0000007913bb80020000bae0010000e80d000000790231c0a3e083"
    "53005a595bc356bed073530031c03b05cc7353007315391e750b3956047506837e080274094083c610ebe383c8ff5e85"
    "c0c360833d04bc6b0000753cc70504bc6b0001000000bed0b36b00bb0300000056ff1588b4690085c0741768b4b36b00"
    "50ff1578b4690085c07407a300bc6b00eb0683c6104b75d8833d00bc6b0000747531db6840bc6b0053ff1500bc6b0085"
    "c074084383fb0472eaeb5b0fb70544bc6b00a308bc6b000fb60546bc6b00a31cbc6b000fb60547bc6b00a320bc6b000f"
    "bf0548bc6b00a30cbc6b000fbf054abc6b00a310bc6b000fbf054cbc6b00a314bc6b000fbf054ebc6b00a318bc6b0061"
    "b801000000c331c0a308bc6b00a30cbc6b00a310bc6b00a314bc6b00a318bc6b00a31cbc6b00a320bc6b006131c0c390"
    "0010002000000040008000000001000220001000ffffffff0000000050460000ffffffff786900000c7b0000e4570000"
    "786900002823000094110000bc34000028230000ffffffff0000000050460000ffffffff58496e707574476574537461"
    "746500662e0f1f8400000000000f1f0078696e707574315f342e646c6c00669078696e707574315f332e646c6c006690"
    "78696e707574395f315f302e646c6c00")
SYM = {"kbdpad": 0x000, "joygds": 0x106, "pickmode": 0x216}   # labels of caves.s
def C(name): return CAVE_VA + SYM[name]

def build():
    """(va, old bytes, new bytes) for every patch site."""
    e = []
    # nodialog: no dialog window, its message loop skipped, the display mode from pickmode
    e.append((0x4524a2, bytes.fromhex("ff1508b56900"), bytes.fromhex("83c41431c090")))   # pop its 5 arguments
    e.append((0x452523, bytes.fromhex("ff150cb56900"), bytes.fromhex("eb5390909090")))   # jmp 0x452578
    e.append((0x4525ae, bytes.fromhex("a3e0835300"), rel32(0x4525ae, C("pickmode"), 0xe8)))
    # noreg: no registry read; the write's RegOpenKeyExA fails
    e.append((0x452439, rel32(0x452439, 0x451790, 0xe8), b"\x90" * 5))
    e.append((0x4526d0, bytes.fromhex("ff1544b36900"), bytes.fromhex("83c4146a0258")))
    # pad: the keyboard slot's fill -> kbdpad; the joystick's GetDeviceState -> joygds
    e.append((0x450727, rel32(0x450727, 0x40c280, 0xe8), rel32(0x450727, C("kbdpad"), 0xe8)))
    e.append((0x45143a, bytes.fromhex("ff512485c0"), rel32(0x45143a, C("joygds"), 0xe8)))
    # nocursor: no class cursor (the class icon still stored); SetCursor(NULL) in the mode scan
    e.append((0x450fde, bytes.fromhex("68007f00005389442434ff15f4b46900"),
              bytes.fromhex("8944242c31c0") + b"\x90" * 10))
    for va in (0x42cf75, 0x42d291):
        e.append((va, bytes.fromhex("ff15f4b46900"), bytes.fromhex("83c40831c090")))
    return e

def add_section(data):
    lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    nsec = struct.unpack_from("<H", data, lfanew + 6)[0]
    optsize = struct.unpack_from("<H", data, lfanew + 20)[0]
    sh = lfanew + 24 + optsize + 40 * nsec
    if nsec != 6 or sh != 0x2d8 or any(data[sh:sh + 40]) or len(data) != SECT_OFF:
        sys.exit("unexpected PE header; nothing written")
    struct.pack_into("<8sIIIIIIHHI", data, sh, b".rdeck", SECT_SIZE, SECT_RVA, SECT_SIZE, SECT_OFF, 0, 0, 0, 0,
                     0xE0000060)       # code | initialised data | execute | read | write
    struct.pack_into("<H", data, lfanew + 6, nsec + 1)
    chars = struct.unpack_from("<H", data, lfanew + 22)[0]
    struct.pack_into("<H", data, lfanew + 22, chars | 1)     # IMAGE_FILE_RELOCS_STRIPPED
    if struct.unpack_from("<I", data, lfanew + 24 + 56)[0] != SECT_RVA: sys.exit("unexpected SizeOfImage")
    struct.pack_into("<I", data, lfanew + 24 + 56, SECT_RVA + SECT_SIZE)
    data += CAVE + bytes(SECT_SIZE - len(CAVE))

def elf_text(path):                    # .text bytes and label offsets of an i386 ELF object (no relocations)
    d = open(path, "rb").read()
    shoff = struct.unpack_from("<I", d, 0x20)[0]; shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2e)
    secs = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    names = [d[secs[shstrndx][4] + x[0]:].split(b"\0")[0].decode() for x in secs]
    if any(n.startswith(".rel") and x[5] for n, x in zip(names, secs)): sys.exit("caves.o has relocations")
    ti = names.index(".text"); text = d[secs[ti][4]:secs[ti][4] + secs[ti][5]]; syms = {}
    for x in secs:
        if x[1] != 2: continue                                   # SHT_SYMTAB
        strs = secs[x[6]]
        for i in range(x[5] // 16):
            nm, val, size, info, oth, shn = struct.unpack_from("<IIIBBH", d, x[4] + 16 * i)
            if shn == ti: syms[d[strs[4] + nm:].split(b"\0")[0].decode()] = val
    return text, syms

ENTRIES = ("kbdpad", "joygds", "pickmode")
def check_caves():
    with tempfile.TemporaryDirectory() as t:
        o = os.path.join(t, "caves.o")
        subprocess.run(["clang", "-target", "i386-pc-linux-gnu", "-c", os.path.join(HERE, "caves.s"), "-o", o], check=True)
        text, syms = elf_text(o)
    ok = text == CAVE and all(syms.get(k) == SYM.get(k) for k in ENTRIES)
    print("caves.s matches CAVE" if ok else "caves.s differs from CAVE / SYM: update patch_exe.py")
    if not ok:
        print("CAVE =", text.hex()); print("SYM =", {k: hex(syms[k]) for k in ENTRIES})
    return ok

def patch(data, src="mtv.exe"):
    """Returns the disc's mtv.exe (bytes) with every patch applied; exits on any unexpected byte."""
    data = bytearray(data)
    if len(data) != SIZE or hashlib.md5(data).hexdigest() != MD5:
        sys.exit(f"{src}: not the disc's mtv.exe (size {SIZE}, MD5 {MD5}); nothing written")
    assert 0 < len(CAVE) < 0xc00, "CAVE empty or running into the variables at 0x6bbc00"
    edits = build()
    for va, old, new in edits:
        off = T(va)
        if bytes(data[off:off + len(old)]) != old or len(old) != len(new):
            sys.exit(f"unexpected bytes at VA {va:#x}; nothing written")
    for va, old, new in edits:
        data[T(va):T(va) + len(new)] = new
    add_section(data)
    print(f"  rdeck nodialog noreg pad nocursor ({len(edits)} edits)")
    return bytes(data)

def main(src, dst):
    out = patch(open(src, "rb").read(), src)
    tmp = dst + ".tmp"
    open(tmp, "wb").write(out)
    os.replace(tmp, dst)
    print(f"{dst}: MD5 {hashlib.md5(out).hexdigest()}")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check-caves": sys.exit(0 if check_caves() else 1)
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
