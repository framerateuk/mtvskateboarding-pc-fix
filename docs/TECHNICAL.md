# How it works

Notes on MTV Sports: Skateboarding featuring Andy Macdonald (Darkblack / THQ, 2000), `Program\mtv.exe`
602,112 bytes, linked 31 August 2000, file version 1.0.0.1, MD5 `80a10c5b34519e5fac1e4d27ac6ded14`.
Addresses are virtual addresses in that exe. `patch_exe.py` holds each patch; the new code is in
`caves.s` and goes into a section the patch adds (`.rdeck`, VA 0x6bb000, 4 KB, at the end of the file).

## The disc

Track 1 is the data track; track 2 is 9.8 s of digital silence and track 3 a second copy of track 1's
directory: nothing reads them. There is no SafeDisc or similar; the protection is against copying the
disc's files: `01.rsc`, `cd.idx` and `data1.cab` each claim about 700 MB, running over every other file,
and `jmptable.rsc` fills the end. None of them are needed. The installer (InstallShield 5) copies
`Program\` and `Program\data\`: `mtv.exe` (Direct3D), `mtv_software.exe` (software renderer),
`readme.txt`, `data\kickPC.blb` (everything else, one 247 MB archive) and 13 AVIs. `build.py` copies the
same and nothing else.

The exe never looks for the disc: its only `GetDriveTypeA` is the C runtime's, and the `cdaudio` MCI
strings are dead code (it doesn't even import winmm). No CD patch is needed.

## Exe patches

- `nodialog`: before every start a Windows dialog asked for the display device, display mode, triple
  buffer, vsync, full screen and low-detail textures (0x452410, from WinMain). `CreateDialogParamA`
  (0x4524a2) is replaced by `add esp, 0x14; xor eax, eax` (its five stdcall arguments popped: no
  window, and the calls on its handle fail harmlessly), its message loop is jumped over as if OK had
  been pressed, and the display mode read back from its list (0x4525ae) comes from `pickmode`:
  1024x768 16-bit from the game's own mode list, else 640x480 16-bit (the dialog's default). The
  other settings keep the dialog's defaults: the first DirectDraw device, vsync on, full screen, no
  triple buffer, full-detail textures.
- `noreg`: those settings were read from and written to `HKLM\Software\Darkblack\MTVSkateboarding`.
  The read (0x452439) is gone and the write's `RegOpenKeyExA` (0x4526d0) now fails, so nothing is
  written. There is no other registry use.
- `pad`: see Pad below.
- `nocursor`: the window class had the arrow as its cursor (0x450fde) and the mode scan showed an
  hourglass (0x42cf75, 0x42d291); now no class cursor and `SetCursor(NULL)`. The game hides the pointer
  itself once its display is up.

Not patched: the frame timing (the main loop 0x448040 measures each frame with
`QueryPerformanceCounter` and moves the game by that much, so it never runs fast; its only wait is for
the millisecond counter to change, at most 1 ms; dgVoodoo's vsync and `FPSLimit = 60` hold 60 frames a
second), the display check (0x451b50: the desktop at least 640x480 x 16-bit), the video-memory check
(0x42cd88, unsigned, so 256 MB is fine), the DirectX version check (0x42e510: dgVoodoo's DirectDraw 7
passes it).

## Movies and music

The game plays 13 AVIs from `data\` through Video for Windows (`AVIStreamGetFrameOpen` asking for
16-bit frames; the sound read with `AVIStreamRead` and decoded by the game through MSACM): `INT_HRV`
(intro, 640x480), `MTV_HRV` (MTV logo), `DEF_HRV` (credits) and ten `*_LRV` files, 128x64: **the
soundtrack**, one licensed song each, whose video plays on screens in the game. The game picks a song at
random or the one chosen in its sound options. All are Indeo 3.2 (`IV32`) video, 15 fps, with 44.1 kHz
stereo MS ADPCM or IMA ADPCM sound. Neither Wine/Proton nor Windows 10/11 has an Indeo 3 decoder:
`AVIStreamGetFrameOpen` fails and the game silently skips the file, sound included.

`make_raw_avi.py` rewrites each one: every video frame (decoded by ffmpeg's indeo3) as an uncompressed
16-bit RGB555 bottom-up DIB, exactly the format the game asks for, so no decoder is needed anywhere;
every sound chunk byte for byte (Windows' and Wine's own `msadp32` / `imaadp32` ACM codecs decode the
ADPCM as the game expects); the same frame count, rate, interleave and stream order; the index rebuilt.
The pad skips the intro and the logo (the game's own skip: any button of any controller).

## Picture

The exe uses `DirectDrawCreateEx` / `IDirect3D7`, full screen at a 16-bit mode from a fixed list; menus
and HUD are DirectDraw blits of pre-drawn art. dgVoodoo2 2.79.3 renders it through Direct3D 11:
`Resolution = max` draws at the screen's height, `stretched_ar` keeps 4:3 with black bars.

The game accepts only 640x480, 800x600, 1024x768, 1280x1024 and 1600x1200 (and three low modes; the
mode callback 0x42cac0), with a set of menu and HUD art drawn for each of the five big ones. 1024x768 is
the nearest to the Deck's 800 lines. To try another, change `pickmode` in `caves.s` (1024 / 768),
re-assemble and update `CAVE` in `patch_exe.py`. A widescreen mode isn't practical: the game refuses
every mode outside its 4:3 list and all of its 2D is placed for each 4:3 resolution.

## Pad

The game keeps up to eight input slots (0x556740, 0x47 bytes each): slot 0 is the keyboard, slots 1-7
the joysticks DirectInput lists. Each holds a direction, "button" bits 0-31 and the bits just pressed; a
button set per player (CONFIG A / B / C on the Game Controls screen) turns the bits into the game's
actions. The keyboard writes keys into the same bits a joystick's buttons would give, and the defaults
suit a Microsoft SideWinder game pad: bit 0 = Space, 1 = D, 3 = S, 4 = F, 6 = Num 0, 7 = scan code
0x54, 8 = Esc, 9 = Enter, the arrow keys the direction. Player one defaults to the keyboard.

- `kbdpad` (the keyboard slot's fill, 0x450727, every frame): after the keyboard, the XInput pad is added
  to the same slot as the keys would press it: A 0, B 1, X 3, Y 4, LB or LT 6, RB or RT 7, View 8,
  Start 9, the left stick (past half way) or D-pad the direction.
- `joygds` (the joystick poll's `GetDeviceState`, 0x45143a): for the first DirectInput joystick, the
  reading is written from XInput in the same numbering, analogue with a 24 % dead zone. That covers a
  pad chosen on the Game Controls screen; Proton's DirectInput would number an Xbox pad's buttons
  differently and put its triggers on one shared axis.

XInput comes from `xinput1_4.dll`, else `xinput1_3.dll` or `xinput9_1_0.dll`. The right stick, L3 and
R3 are unused, and so is the mouse.
