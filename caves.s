# MTV Sports: Skateboarding (mtv.exe, the disc's Direct3D exe, 602,112 bytes, linked 31 Aug 2000, MSVC; Darkblack /
# THQ): new code for patch_exe.py. It goes into a section patch_exe.py adds to the exe, ".rdeck" at VA 0x6bb000
# (file offset 0x93000, the end of the file, 0x1000 bytes, readable / writable / executable): this code from
# 0x6bb000, its variables from 0x6bbc00 (zero when the exe loads). The exe always loads at its 0x400000 base (no
# dynamic-base flag; the patch also marks it "relocations stripped"), so absolute addresses are used throughout.
#
# Assembled with Apple clang (integrated assembler):
#   clang -target i386-pc-linux-gnu -c caves.s -o caves.o
# patch_exe.py carries the resulting bytes (CAVE) and checks them against this file when clang is around
# (patch_exe.py --check-caves). docs/TECHNICAL.md explains each routine.
#
# readpad / axis code are Redline Racer's (games/windows/Redline Racer/caves.s): XInput found at the first call
# through LoadLibraryA / GetProcAddress, nothing else of the game touched.
#
# Lesson kept from Speedster (23 Oct 2026): never keep a value in ecx / edx across an API call (Proton's
# timeGetTime and friends change them). Every routine here saves what it uses with pushad / popad, and keeps
# values across API calls only in ebx / esi / edi / ebp or memory.
.intel_syntax noprefix
.set BASE, 0x6bb000

# imports used (IAT slots of mtv.exe)
.set GetProcAddress,   0x69b478
.set LoadLibraryA,     0x69b488

# game
.set KBDFILL,  0x40c280              # void __fastcall KbdFill(SLOT *ecx, BYTE *held edx, BYTE *pressed [esp+4]),
                                     #   ret 4: clears the keyboard slot and writes it from the key arrays
.set KSLOT,    0x556740              # the keyboard's input slot (docs/TECHNICAL.md "Pad"): +0x00 X, +0x04 Y (-1 / 0 / +1, up +),
                                     #   +0x1c buttons held, +0x20 / +0x24 X / Y just pushed, +0x3c buttons just
                                     #   pressed, +0x40 present, +0x43 button set (4 = "CONFIG A")
.set JOY0,     0x5a80e0              # IDirectInputDevice2 * of the first joystick DirectInput listed
.set MODES,    0x5373d0              # the display modes the game accepts: {width, height, bytes per pixel, Hz}
.set NMODES,   0x5373cc              #   and their count (the start-up dialog's list, filled by 0x42cf60)
.set MODESEL,  0x5383e0              # the chosen mode's index

# our variables (.rdeck from 0x6bbc00, zero at load)
.set XGS,     0x6bbc00               # XInputGetState (0 = no XInput DLL)
.set XINIT,   0x6bbc04               # 1 once readpad has looked for XInput
.set PB,      0x6bbc08               # the pad as readpad last read it: XInput wButtons (DPAD_UP 1, DOWN 2, LEFT 4,
.set PLX,     0x6bbc0c               #   RIGHT 8, START 0x10, BACK 0x20, L3 0x40, R3 0x80, LB 0x100, RB 0x200,
.set PLY,     0x6bbc10               #   A 0x1000, B 0x2000, X 0x4000, Y 0x8000); left stick X / Y (signed, up +)
.set PRX,     0x6bbc14               #   right stick X / Y
.set PRY,     0x6bbc18
.set PLT,     0x6bbc1c               #   left / right trigger 0..255
.set PRT,     0x6bbc20
.set KPREV,   0x6bbc24               # kbdpad: the game buttons the pad held at the previous frame
.set KDX,     0x6bbc28               # kbdpad: the pad's X / Y direction at the previous frame (-1 / 0 / +1)
.set KDY,     0x6bbc2c
.set XS,      0x6bbc40               # an XINPUT_STATE (16 bytes)

.set DZ,      7849                   # stick dead zone for the joystick reading (XInput's own figure, 24 %)
.set DIRT,    16000                  # stick past this (about half) = a direction for the keyboard slot
.set TRIG,    64                     # trigger past this (of 255) = held

.macro PUSHI v                       # push imm32 (clang's intel syntax would make "push offset" 16-bit)
  .byte 0x68
  .long \v
.endm

.text
start:

# ---------------------------------------------------------------------------------------------------------------
# kbdpad (patch pad): the input update (0x450700, every frame) fills the keyboard's slot with
# "push pressed; mov edx, held; mov ecx, KSLOT; call KbdFill" (0x450727). The call comes here: the game's fill, then
# the pad added on top, the way the keyboard would press it: the buttons (padbits) held and just pressed, the left
# stick or D-pad as the arrow keys (-1 / +1) with their "just pushed" fields. Player one's controls default to the
# keyboard, so the pad works there without a visit to the Game Controls screen; a pad chosen there (a joystick slot)
# reads the same buttons through joygds.
kbdpad:
  push dword ptr [esp + 4]           # the pressed-keys array, for KbdFill (it pops it)
  .byte 0xe8                         # call KBDFILL (ecx / edx as the caller set them)
  .long KBDFILL - (BASE + (1f - start))
1:
  pushad
  call readpad
  test eax, eax
  jz 9f
  .byte 0xbe                         # mov esi, KSLOT
  .long KSLOT
  call padbits
  mov ecx, dword ptr [KPREV]
  mov dword ptr [KPREV], eax
  or dword ptr [esi + 0x1c], eax     # held
  not ecx
  and ecx, eax
  or dword ptr [esi + 0x3c], ecx     # just pressed
  call dirx
  mov ecx, dword ptr [KDX]
  mov dword ptr [KDX], eax
  test eax, eax
  jz 2f
  cmp dword ptr [esi], 0             # an arrow key wins
  jne 2f
  mov dword ptr [esi], eax
  cmp eax, ecx
  je 2f
  mov dword ptr [esi + 0x20], eax    # just pushed
2:
  call diry
  mov ecx, dword ptr [KDY]
  mov dword ptr [KDY], eax
  test eax, eax
  jz 9f
  cmp dword ptr [esi + 4], 0
  jne 9f
  mov dword ptr [esi + 4], eax
  cmp eax, ecx
  je 9f
  mov dword ptr [esi + 0x24], eax
9:
  popad
  ret 4

# dirx / diry: eax = the pad's X (right +) / Y (up +) direction, -1 / 0 / +1: the D-pad, else the left stick past
# DIRT. Change eax only.
dirx:
  test byte ptr [PB], 4
  jnz 3f
  test byte ptr [PB], 8
  jnz 4f
  mov eax, dword ptr [PLX]
  jmp 5f
diry:
  test byte ptr [PB], 2
  jnz 3f
  test byte ptr [PB], 1
  jnz 4f
  mov eax, dword ptr [PLY]
5:
  cmp eax, -DIRT
  jl 3f
  cmp eax, DIRT
  jg 4f
  xor eax, eax
  ret
3:
  or eax, -1
  ret
4:
  mov eax, 1
  ret

# padbits: eax = the game's joystick buttons from readpad's reading, as a Microsoft SideWinder game pad would give
# them (the PC game's own default, "CONFIG A"; docs/TECHNICAL.md "Pad"): 0 A, 1 B, 3 X, 4 Y, 6 LB or LT, 7 RB or RT, 8 View,
# 9 Start (2 and 5 = the SideWinder's C and Z: unused by the game's play controls). Changes eax, ecx, edx.
padbits:
  push ebx
  mov edx, dword ptr [PB]
  xor ebx, ebx
  xor eax, eax
1:
  movzx ecx, word ptr [A_BTNMAP + eax*2]
  test edx, ecx
  jz 2f
  bts ebx, eax
2:
  inc eax
  cmp eax, 10
  jb 1b
  cmp dword ptr [PLT], TRIG
  jle 3f
  or ebx, 0x40
3:
  cmp dword ptr [PRT], TRIG
  jle 4f
  or ebx, 0x80
4:
  mov eax, ebx
  pop ebx
  ret

# ---------------------------------------------------------------------------------------------------------------
# joygds (patch pad): the joystick poll (0x4513a0, every frame, each joystick DirectInput listed) reads a device
# with "push buf; push 0x110; push dev; call [vtbl + 0x24]; test eax, eax" (GetDeviceState(DIJOYSTATE2), 0x45143a).
# Those 5 bytes are now "call joygds": the same call, then, for the first joystick with an XInput pad connected, the
# reading written from XInput (joyfill) and DI_OK. Under Proton DirectInput puts an Xbox pad's triggers on one shared
# Z axis (both held = neither) and numbers its buttons A B X Y LB RB View Start: the game's buttons need the
# SideWinder numbering (padbits). Returns with the flags of "test eax, eax", as the replaced code left them.
joygds:
  push dword ptr [esp + 0xc]         # buf
  push dword ptr [esp + 0xc]         # 0x110
  push dword ptr [esp + 0xc]         # dev
  call dword ptr [ecx + 0x24]        # GetDeviceState (ecx = the vtable, as the game loaded it)
  pushad
  mov edi, dword ptr [esp + 0x24]    # dev (pushad 0x20, return address)
  mov esi, dword ptr [esp + 0x2c]    # buf
  cmp edi, dword ptr [JOY0]
  jne 9f
  call readpad
  test eax, eax
  jz 9f
  call joyfill
  mov dword ptr [esp + 0x1c], 0      # eax (pushad's slot) = DI_OK
9:
  popad
  test eax, eax
  ret 0xc

# joyfill: esi = a DIJOYSTATE2 (0x110 bytes), written from readpad's reading in DirectInput's default ranges:
#   lX / lY   the left stick, 0..0xffff, centre 0x8000, down = larger Y; dead zone DZ; the D-pad overrides with
#             full deflection
#   lZ lRx lRy lRz, both sliders   0x8000 (centred: the game subtracts 0x8000 from each)
#   rgdwPOV[0]  the D-pad in hundredths of a degree (0xffffffff = centred); the other three centred
#   rgbButtons  padbits' buttons, 0x80 = down
joyfill:
  push edi
  mov edi, esi
  mov ecx, 0x110 / 4
  xor eax, eax
  rep stosd
  pop edi
  mov eax, dword ptr [PLX]
  call axisraw
  test byte ptr [PB], 4
  jz 1f
  xor eax, eax
1:
  test byte ptr [PB], 8
  jz 2f
  mov eax, 0xffff
2:
  mov dword ptr [esi], eax
  mov eax, dword ptr [PLY]
  neg eax                            # XInput up +, DirectInput up = smaller
  call axisraw
  test byte ptr [PB], 1
  jz 3f
  xor eax, eax
3:
  test byte ptr [PB], 2
  jz 4f
  mov eax, 0xffff
4:
  mov dword ptr [esi + 4], eax
  mov eax, 0x8000
  mov dword ptr [esi + 0x08], eax
  mov dword ptr [esi + 0x0c], eax
  mov dword ptr [esi + 0x10], eax
  mov dword ptr [esi + 0x14], eax
  mov dword ptr [esi + 0x18], eax
  mov dword ptr [esi + 0x1c], eax
  or eax, -1
  mov dword ptr [esi + 0x24], eax
  mov dword ptr [esi + 0x28], eax
  mov dword ptr [esi + 0x2c], eax
  mov edx, dword ptr [PB]
  and edx, 0xf                       # D-pad up 1, down 2, left 4, right 8
  mov eax, dword ptr [A_POVTAB + edx*4]
  mov dword ptr [esi + 0x20], eax
  call padbits
  xor ecx, ecx
5:
  bt eax, ecx
  jnc 6f
  mov byte ptr [esi + 0x30 + ecx], 0x80
6:
  inc ecx
  cmp ecx, 10
  jb 5b
  ret

# axisraw: eax = a stick axis (-32768..32767, sign as wanted) -> 0..0xffff, 0x8000 inside the dead zone DZ.
axisraw:
  mov ecx, eax
  cdq
  xor eax, edx
  sub eax, edx                       # |value|
  cmp eax, DZ
  jg 1f
  mov eax, 0x8000
  ret
1:
  mov eax, ecx
  add eax, 0x8000
  jns 2f
  xor eax, eax
2:
  cmp eax, 0xffff
  jle 3f
  mov eax, 0xffff
3:
  ret

# ---------------------------------------------------------------------------------------------------------------
# pickmode (patch nodialog): with the start-up dialog gone, the game's code after it reads the chosen display mode
# from the dialog's (now absent) list: "mov [MODESEL], eax" (0x4525ae, eax = the list's selection) is now
# "call pickmode": the 1024 x 768 16-bit mode from the game's own mode list (filled from DirectDraw just before),
# else 640 x 480 16-bit (the dialog's own default), else the first mode. docs/TECHNICAL.md "Picture".
pickmode:
  push ebx
  push ecx
  push edx
  mov ebx, 1024
  mov edx, 768
  call findmode
  jns 8f
  mov ebx, 640
  mov edx, 480
  call findmode
  jns 8f
  xor eax, eax
8:
  mov dword ptr [MODESEL], eax
  pop edx
  pop ecx
  pop ebx
  ret

# findmode: eax = the index of mode ebx x edx at 2 bytes a pixel in MODES, or -1 (sign flag set). Changes eax, ecx.
findmode:
  push esi
  .byte 0xbe                         # mov esi, MODES
  .long MODES
  xor eax, eax
1:
  cmp eax, dword ptr [NMODES]
  jae 3f
  cmp dword ptr [esi], ebx
  jne 2f
  cmp dword ptr [esi + 4], edx
  jne 2f
  cmp dword ptr [esi + 8], 2
  je 4f
2:
  inc eax
  add esi, 16
  jmp 1b
3:
  or eax, -1
4:
  pop esi
  test eax, eax
  ret

# ---------------------------------------------------------------------------------------------------------------
# readpad: the pad into PB / PLX / PLY / PRX / PRY / PLT / PRT (XInput layout): XInput pad 0..3, the first
# connected one. The first call looks for XInputGetState in xinput1_4.dll, else xinput1_3.dll, else
# xinput9_1_0.dll (Proton has all three; Windows 8+ has 1_4 and 9_1_0; the exe imports none of them).
# Returns eax = 1 with a reading, 0 without (no XInput, no pad). Keeps every other register.
readpad:
  pushad
  cmp dword ptr [XINIT], 0
  jne 10f
  mov dword ptr [XINIT], 1
  .byte 0xbe                         # mov esi, the three names (16 bytes each)
  .long A_XINPUT
  mov ebx, 3
2:
  push esi
  call dword ptr [LoadLibraryA]
  test eax, eax
  jz 3f
  PUSHI BASE + (s_xgs - start)
  push eax
  call dword ptr [GetProcAddress]
  test eax, eax
  jz 3f
  mov dword ptr [XGS], eax
  jmp 10f
3:
  add esi, 16
  dec ebx
  jnz 2b
10:
  cmp dword ptr [XGS], 0
  je 99f
  xor ebx, ebx                       # pad index
11:
  PUSHI XS
  push ebx
  call dword ptr [XGS]
  test eax, eax
  jz 12f
  inc ebx
  cmp ebx, 4
  jb 11b
  jmp 99f
12:
  movzx eax, word ptr [XS + 4]
  mov dword ptr [PB], eax
  movzx eax, byte ptr [XS + 6]
  mov dword ptr [PLT], eax
  movzx eax, byte ptr [XS + 7]
  mov dword ptr [PRT], eax
  movsx eax, word ptr [XS + 8]
  mov dword ptr [PLX], eax
  movsx eax, word ptr [XS + 10]
  mov dword ptr [PLY], eax
  movsx eax, word ptr [XS + 12]
  mov dword ptr [PRX], eax
  movsx eax, word ptr [XS + 14]
  mov dword ptr [PRY], eax
  popad
  mov eax, 1
  ret
99:
  xor eax, eax
  mov dword ptr [PB], eax
  mov dword ptr [PLX], eax
  mov dword ptr [PLY], eax
  mov dword ptr [PRX], eax
  mov dword ptr [PRY], eax
  mov dword ptr [PLT], eax
  mov dword ptr [PRT], eax
  popad
  xor eax, eax
  ret

# ---------------------------------------------------------------------------------------------------------------
  .p2align 2
btnmap:    .short 0x1000, 0x2000, 0x0000, 0x4000, 0x8000, 0x0000, 0x0100, 0x0200, 0x0020, 0x0010
                                     # game buttons 0-9 (SideWinder A B C X Y Z L R M Start) as XInput bits:
                                     # A B - X Y - LB RB View Start
  .p2align 2
povtab:    .long -1, 0, 18000, -1, 27000, 31500, 22500, 27000, 9000, 4500, 13500, 9000, -1, 0, 18000, -1
                                     # D-pad bits (up 1, down 2, left 4, right 8) -> POV hundredths of a degree
s_xgs:     .asciz "XInputGetState"
  .p2align 4
s_xinput:  .asciz "xinput1_4.dll"
  .p2align 4
           .asciz "xinput1_3.dll"
  .p2align 4
           .asciz "xinput9_1_0.dll"
.set A_XINPUT, BASE + (s_xinput - start)
.set A_BTNMAP, BASE + (btnmap - start)
.set A_POVTAB, BASE + (povtab - start)
