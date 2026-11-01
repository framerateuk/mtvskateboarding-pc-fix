#!/usr/bin/env python3
"""Rewrite one of MTV Skateboarding's Indeo 3 movies with uncompressed 16-bit video (docs/TECHNICAL.md "Movies and music").

  make_raw_avi.py IN.avi OUT.avi

The disc's 13 AVIs (Program\\data\\*.avi) are Indeo 3.2 video ("IV32") with MS ADPCM / IMA ADPCM sound. The game
plays them through Video for Windows (AVIFIL32: AVIStreamGetFrameOpen asking for a 16-bit BI_RGB frame,
AVIStreamRead for the sound, which it decodes itself through MSACM32). Neither Wine / Proton nor Windows 10/11 has an
Indeo 3 decoder, so AVIStreamGetFrameOpen fails and the game silently skips the movie -- and with it the sound: the
ten *_LRV.avi files are the licensed soundtrack (one song each, a 128x64 video shown on the in-game TV screens).

What this writes, chunk for chunk the same file otherwise:
  video  every '00dc' frame replaced by the same picture as a 16-bit BI_RGB DIB (RGB555, rows bottom-up, the exact
         format the game asks AVIStreamGetFrameOpen for: no decompressor needed on Wine or Windows); the stream
         header's handler 0, its strf biCompression 0 / biBitCount 16 / biSizeImage = width x height x 2
  sound  every '01wb' chunk copied byte for byte (the ADPCM data and its WAVEFORMATEX untouched: Wine's and
         Windows' own msadp32 / imaadp32 ACM codecs decode it, as the game expects)
  index  idx1 rebuilt (offsets from the 'movi' fourcc, every chunk a key frame); avih's buffer sizes updated
Same frame count, rate, interleave and stream order as the original. The JUNK padding and Premiere's PRMI list are
left out. Pictures decoded by ffmpeg (its indeo3 decoder), one per frame chunk (-vsync passthrough).
"""
import os, struct, subprocess, sys

def chunks(d, start, end):
    """(fourcc, data offset, size, list type or None) for each chunk in d[start:end]."""
    i = start
    while i + 8 <= end:
        tag = d[i:i + 4]; size = struct.unpack_from("<I", d, i + 4)[0]
        yield tag, i + 8, size, (d[i + 8:i + 12] if tag in (b"LIST", b"RIFF") else None)
        i += 8 + size + (size & 1)

def ck(tag, data):
    return tag + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")

def main(src, dst):
    d = open(src, "rb").read()
    if d[:4] != b"RIFF" or d[8:12] != b"AVI ":
        sys.exit(f"{src}: not an AVI")
    top = {(t, lt): (o, s) for t, o, s, lt in chunks(d, 12, len(d))}
    ho, hs = top[(b"LIST", b"hdrl")]; mo, ms = top[(b"LIST", b"movi")]
    hdr = list(chunks(d, ho + 4, ho + hs))
    avih = bytearray(d[hdr[0][1]:hdr[0][1] + hdr[0][2]]); assert hdr[0][0] == b"avih"
    strls = [(o, s) for t, o, s, lt in hdr if lt == b"strl"]
    if len(strls) != 2: sys.exit(f"{src}: expected a video and a sound stream")
    vstrl = astrl = None
    for o, s in strls:
        parts = {t: (po, ps) for t, po, ps, _ in chunks(d, o + 4, o + s)}
        typ = d[parts[b"strh"][0]:parts[b"strh"][0] + 4]
        if typ == b"vids": vstrl = parts
        elif typ == b"auds": astrl = parts
    po, ps = vstrl[b"strh"]; vstrh = bytearray(d[po:po + ps])
    po, ps = vstrl[b"strf"]; bih = bytearray(d[po:po + 40])
    if vstrh[4:8] != b"IV32" or bih[16:20] != b"IV32": sys.exit(f"{src}: video is not Indeo 3.2")
    w, h = struct.unpack_from("<ii", bih, 4)
    nframes = struct.unpack_from("<I", vstrh, 32)[0]
    fsize = w * h * 2
    if (w * 2) % 4: sys.exit(f"{src}: width {w} gives padded DIB rows")
    astrl_bytes = b"".join(ck(t, d[o:o + s]) for t, (o, s) in astrl.items())

    # the pictures: ffmpeg decodes each frame chunk; RGB555 little-endian, flipped to bottom-up rows
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-an", "-vsync", "passthrough",
                          "-vf", "vflip", "-f", "rawvideo", "-pix_fmt", "rgb555le", "-"], stdout=subprocess.PIPE)

    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        # header with placeholders, patched at the end
        vstrh[4:8] = b"\0\0\0\0"
        struct.pack_into("<I", vstrh, 36, fsize)                          # dwSuggestedBufferSize
        struct.pack_into("<HHI", bih, 12, 1, 16, 0)                        # biPlanes, biBitCount, BI_RGB
        struct.pack_into("<I", bih, 20, fsize)                             # biSizeImage
        struct.pack_into("<I", bih, 0, 40)
        vstrl_bytes = ck(b"strh", bytes(vstrh)) + ck(b"strf", bytes(bih))
        struct.pack_into("<I", avih, 4, fsize * 15 + 44100 * 4)              # dwMaxBytesPerSec
        struct.pack_into("<I", avih, 28, max(fsize, struct.unpack_from("<I", avih, 28)[0]) + 8)   # suggested buffer
        first_v = d[strls[0][0] + 4 + 8:strls[0][0] + 4 + 12] == b"vids"
        strl_v = b"LIST" + struct.pack("<I", len(vstrl_bytes) + 4) + b"strl" + vstrl_bytes
        strl_a = b"LIST" + struct.pack("<I", len(astrl_bytes) + 4) + b"strl" + astrl_bytes
        hdrl_body = b"hdrl" + ck(b"avih", bytes(avih)) + (strl_v + strl_a if first_v else strl_a + strl_v)
        f.write(b"RIFF\0\0\0\0AVI ")
        f.write(b"LIST" + struct.pack("<I", len(hdrl_body)) + hdrl_body)
        movi_pos = f.tell()
        f.write(b"LIST\0\0\0\0movi")
        idx, nv = [], 0
        for tag, o, s, lt in chunks(d, mo + 4, mo + ms):
            if lt is not None: sys.exit(f"{src}: nested list in movi")
            pos = f.tell() - (movi_pos + 8)                                  # from the 'movi' fourcc
            if tag[2:] in (b"dc", b"db"):
                data = p.stdout.read(fsize)
                if len(data) != fsize: sys.exit(f"{src}: ffmpeg gave {nv} pictures, the file has more frame chunks")
                nv += 1
                tag = tag[:2] + b"db"
            else:
                data = d[o:o + s]
            f.write(ck(tag, data))
            idx.append(struct.pack("<4sIII", tag, 0x10, pos, len(data)))
        if p.stdout.read(1): sys.exit(f"{src}: ffmpeg gave more pictures than frame chunks")
        if p.wait(): sys.exit(f"{src}: ffmpeg failed")
        if nv != nframes: sys.exit(f"{src}: {nv} frames, header says {nframes}")
        movi_end = f.tell()
        f.write(ck(b"idx1", b"".join(idx)))
        end = f.tell()
        f.seek(movi_pos + 4); f.write(struct.pack("<I", movi_end - movi_pos - 8))
        f.seek(4); f.write(struct.pack("<I", end - 8))
    os.replace(tmp, dst)
    print(f"{dst}: {nv} frames {w}x{h} RGB555, sound copied ({end // 1048576} MB)")

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
