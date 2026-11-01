#!/usr/bin/env python3
"""Build a ready-to-run MTV Sports: Skateboarding folder for modern PCs from your own CD.

Usage:
  python3 build.py DISC.cue|DISC.ccd --dgvoodoo DGVOODOO.zip [--out DIR] [--windows]

  DISC          your MTV Sports: Skateboarding featuring Andy Macdonald PC CD (Darkblack / THQ, 2000) as .cue + .bin
                or .ccd + .img
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --out         where to create MTVSkateboarding/ (default: this folder)
  --windows     a folder for Windows only: the same game/ folder, without the Steam Deck launch script

Needs Python 3.8+ and ffmpeg on the PATH (its Indeo 3 decoder rewrites the movies and the soundtrack's videos).
Nothing from the game is in this repository: every game file comes from your disc.
"""
import argparse, hashlib, os, shutil, sys, tempfile, zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, patch_exe, make_raw_avi

EXE_MD5 = "80a10c5b34519e5fac1e4d27ac6ded14"            # Program\mtv.exe, 31 Aug 2000, 1.0.0.1 (Direct3D)
BLB_MD5 = "4b6d8bfa7df76dcbcd555e9ab4835059"            # Program\data\kickPC.blb
PATCHED_MD5 = "4f6c106be3cc061eef7875099706cf8a"
MOVIES = 13


def md5(data): return hashlib.md5(data).hexdigest()


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--dgvoodoo", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"): sys.exit("needs ffmpeg on the PATH (for the Indeo 3 movies)")

    tracks = disc.tracks(a.disc)
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.upper(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk(joliet=True)}
    if "PROGRAM/MTV.EXE" not in entries: sys.exit("no Program\\mtv.exe on this CD: it isn't the MTV Skateboarding PC disc")
    exe = dt.read_file(*entries["PROGRAM/MTV.EXE"][2:])
    if md5(exe) != EXE_MD5:
        sys.exit(f"this CD's mtv.exe is not the 31 Aug 2000 exe the kit was made for (MD5 {md5(exe)})")

    pkg = os.path.join(os.path.abspath(a.out), "MTVSkateboarding"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    # What the installer copied from the disc's Program\ (the rest of the disc is the installer, DirectX 7a and
    # oversized dummy files)
    print("1/4 game files from the CD")
    for name in ("readme.txt", "data/kickPC.blb"):
        dt.copy_file(*entries["PROGRAM/" + name.upper()][2:], os.path.join(game, *name.split("/")))
    if md5(open(os.path.join(game, "data", "kickPC.blb"), "rb").read()) != BLB_MD5:
        sys.exit("data\\kickPC.blb differs from the disc the kit was made for")
    write(os.path.join(game, "_spare", "mtv.exe"), exe)
    dt.copy_file(*entries["PROGRAM/MTV_SOFTWARE.EXE"][2:], os.path.join(game, "_spare", "mtv_software.exe"))

    print("2/4 exe patches")
    out = patch_exe.patch(exe)
    if md5(out) != PATCHED_MD5: sys.exit("patching gave an unexpected mtv.exe")
    write(os.path.join(game, "mtv.exe"), out)

    print("3/4 movies and soundtrack: Indeo 3 video -> uncompressed, the sound untouched (a few minutes)")
    avis = [(k, v) for k, v in entries.items() if k.startswith("PROGRAM/DATA/") and k.endswith(".AVI")]
    if len(avis) != MOVIES: sys.exit(f"expected {MOVIES} movies on the disc, found {len(avis)}")
    with tempfile.TemporaryDirectory() as tmp:
        def one(item):
            k, (p, is_dir, l, s) = item
            name = p.rsplit("/", 1)[1]
            src = os.path.join(tmp, name); dt.copy_file(l, s, src)
            make_raw_avi.main(src, os.path.join(game, "data", name))
            os.remove(src)
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
            list(pool.map(one, avis))

    print("4/4 dgVoodoo2 and its settings" + ("" if a.windows else ", Steam Deck launch script"))
    write(os.path.join(game, "ddraw.dll"), take(a.dgvoodoo, "MS/x86/DDraw.dll"))
    write(os.path.join(game, "d3dimm.dll"), take(a.dgvoodoo, "MS/x86/D3DImm.dll"))
    shutil.copyfile(os.path.join(HERE, "config", "dgVoodoo.conf"), os.path.join(game, "dgVoodoo.conf"))
    if not a.windows:
        launch = os.path.join(pkg, "mtv_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "mtv_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
