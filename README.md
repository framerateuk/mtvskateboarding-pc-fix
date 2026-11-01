# MTV Sports: Skateboarding (PC, 2000) on modern PCs and the Steam Deck

## Why this exists

We didn't get Tony Hawk's on PC. But we did get this, and while it's not quite as good, it does have
an amazing soundtrack which introduced me to the likes of System of a Down.

## What this does

Turns **your own** MTV Sports: Skateboarding featuring Andy Macdonald PC CD (Darkblack / THQ, 2000)
into a folder that runs on the Steam Deck (Proton) or on Windows 10/11, with no installer and no
registry entries:

- **The soundtrack and the movies play again.** They are Indeo 3 video, which neither Windows 10/11
  nor Proton can decode, and the game then silently skips them, music included (each song is a small
  music video shown on the screens in the parks). `build.py` rewrites the pictures uncompressed and
  keeps the disc's own sound untouched.
- **No start-up dialog**: the game starts straight in 1024x768, full screen, vsync on, full-detail
  textures, instead of a Windows settings box before every run.
- **No registry**: saves, high scores and options are in `KICKFLIP.SAV` in the game folder.
- **Gamepad**: an Xbox-style pad (the Steam Deck's included) through XInput, laid out as the
  SideWinder pad the game expected; Start and View work as Enter and Esc, so no Steam Input set-up
  is needed.
- **No mouse pointer** over the game.
- **dgVoodoo2** runs the game's Direct3D 7 at your screen's height, 4:3 with black bars, 60 frames a
  second.

**No game files are in this repository.** Everything from the game comes from your disc when you
run `build.py`.

## What you need

| | |
|---|---|
| The game | The **MTV Sports: Skateboarding PC CD** (Darkblack / THQ, 2000; `Program\mtv.exe` of 31 August 2000, version 1.0.0.1) as `.cue` + `.bin` or CloneCD `.ccd` + `.img`. `build.py` checks the exe and stops on another version. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| ffmpeg | on the PATH (ffmpeg.org; any normal build has the Indeo 3 decoder). Tested with 8.0.1. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |

## Build

```
python3 build.py MTVSkateboarding.cue --dgvoodoo dgVoodoo2_79_3.zip
```

creates `MTVSkateboarding/` with `game/` and `mtv_launch.sh` (for the Steam Deck), in a few minutes
(the movies are rewritten from 230 MB to 1.4 GB). The same `game/` folder runs on Windows;
`--windows` leaves out the launch script. `--out DIR` puts the result somewhere else. The disc's
original exe and its software-renderer exe are kept in `game/_spare/`.

## Play on the Steam Deck

1. Copy `MTVSkateboarding/` to the Deck, for example to `/home/deck/Games/MTVSkateboarding/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../MTVSkateboarding/game/mtv.exe`.
   Rename the shortcut "MTV Sports: Skateboarding".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/MTVSkateboarding/mtv_launch.sh %command%
   ```
5. Controller layout: the standard **Gamepad** layout. The game reads the pad itself.

## Play on Windows

Run `game/mtv.exe`. An Xbox pad works as on the Deck; the keyboard works as the game's own.

## Controls

| Pad | Game button (keyboard) | Does (the game's CONFIG A) |
|---|---|---|
| Left stick, D-pad | direction (arrow keys) | skate / turn; menus: move |
| A | 0 (Space) | first trick button (ollie / speed up); choose in menus |
| B | 1 (D) | a trick button; back in some menus |
| X | 3 (S) | a trick button |
| Y | 4 (F) | a trick button |
| LB or LT | 6 (Num 0) | rotate left |
| RB or RT | 7 | rotate right |
| Start (Menu) | 9 (Enter) | pause / options, choose |
| View | 8 (Esc) | back |

The Game Controls screen shows which trick (Ollie / Speed Up, Grab, Kick, Flat / Grind) is on which
button; CONFIG B and C rearrange them.

## Settings

- Saves, high scores, options: the game's Load and Save menu, kept in `game/KICKFLIP.SAV`.
- Smoothing: `Resampling = bilinear` (the kit's) or `pointsampled` (sharp pixels) in
  `game/dgVoodoo.conf`. 3D resolution: `[DirectX] Resolution` (`max` = the screen's height,
  `unforced` = the game's 1024x768).
- Deck renderer: `RENDERER=wined3d` before the script path in the launch options uses Wine's own
  DirectDraw / Direct3D instead of dgVoodoo (stretched, no frame cap).

There is no widescreen mode: the game accepts only its 4:3 modes, and its menus and HUD are pixel
art made for each of them.

## Troubleshooting

- *No music in a run*: some songs open with a spoken-word intro before the music starts. With no
  sound at all, check that `game/data/*_LRV.avi` exist (the soundtrack).
- *A settings dialog at start*: you're running the unpatched exe from `_spare/`.
- *Flicker or a black screen*: `ddraw.dll`, `d3dimm.dll` and `dgVoodoo.conf` must sit beside
  `mtv.exe`.
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

Tested: on the Steam Deck (Proton 9.0) and on Windows 11.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game files, patches the exe, rewrites the movies, adds dgVoodoo2 and its settings. Python standard library plus ffmpeg. |
| `patch_exe.py` | The exe patches, each explained, with the new code's bytes; also runs on its own. |
| `caves.s` | The source of that new code (x86 assembly); `patch_exe.py --check-caves` re-assembles it with clang and compares. Only needed to change a patch. |
| `make_raw_avi.py` | Rewrites one Indeo 3 AVI with uncompressed 16-bit pictures and the original sound; also runs on its own. |
| `disc.py` | Reads the CD image: `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 with Joliet names. |
| `config/dgVoodoo.conf` | dgVoodoo2's settings. |
| `steamdeck/mtv_launch.sh` | Proton launch wrapper: DLL overrides. |
| `docs/TECHNICAL.md` | How the game works and what each patch does. |

## Credits

- **Darkblack** made MTV Sports: Skateboarding; **THQ** published it. Please own the game: this kit
  needs your disc.
- **Dege**: dgVoodoo2. **FFmpeg**: the Indeo 3 decoder.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, dgVoodoo2 or ffmpeg.

Not affiliated with or endorsed by the game's rights holders.
