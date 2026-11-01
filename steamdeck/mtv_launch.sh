#!/bin/bash
# MTV Sports: Skateboarding (Darkblack / THQ, 2000) Steam Deck / Proton launch wrapper.
#
# Steam > MTV Sports: Skateboarding > Properties > Launch Options:
#   /home/deck/Games/MTVSkateboarding/mtv_launch.sh %command%
# Shortcut target: /home/deck/Games/MTVSkateboarding/game/mtv.exe, Start In: /home/deck/Games/MTVSkateboarding/game/
#
# mtv.exe is the disc's Direct3D exe patched (patch_exe.py): no start-up dialog (1024x768 16-bit chosen), no
# registry, the pad through XInput, no mouse pointer. The game never looks for its CD. Saves, high scores and
# settings are in game/KICKFLIP.SAV. The movies and the soundtrack (game/data/*.avi) are uncompressed video with
# the disc's ADPCM sound (make_raw_avi.py): Proton has no Indeo 3 decoder.
# Every launch sets DLL overrides so Wine loads the DLLs beside the exe:
#   ddraw + d3dimm = dgVoodoo2 2.79.3 (Direct3D 7 -> D3D11 -> DXVK; the game's 1024x768 rendered at the screen's
#   height, 4:3 with black bars, 60 frames a second: dgVoodoo.conf)
# RENDERER (before the script path in Launch Options, or a file RENDERER beside this script holding the word):
#   dgvoodoo  (default) ddraw + d3dimm from dgVoodoo2
#   wined3d   plain Wine ddraw / Direct3D (1024x768 stretched to the screen by gamescope; no frame cap)

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "cwd: $(pwd)"

[ -z "${RENDERER:-}" ] && [ -s "$HERE/RENDERER" ] && RENDERER="$(tr -d ' \n' < "$HERE/RENDERER")"
RENDERER="${RENDERER:-dgvoodoo}"
log "RENDERER=$RENDERER  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# Proton appends its own overrides after ours.
case "$RENDERER" in
  dgvoodoo) OVR="ddraw=n,b;d3dimm=n,b" ;;
  wined3d)  OVR="ddraw=b;d3dimm=b" ;;
  *)        log "unknown RENDERER '$RENDERER', using dgvoodoo"; OVR="ddraw=n,b;d3dimm=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# Debugging: if a file named PROTON_LOG exists beside this script, Proton writes steam-<appid>.log here. A file
# WINEDEBUG beside it adds Wine debug channels (e.g. +dinput,+ddraw). Create / delete them from Desktop Mode.
if [ -e "$HERE/PROTON_LOG" ]; then
  export PROTON_LOG=1 PROTON_LOG_DIR="$HERE"
  log "PROTON_LOG on -> $HERE/steam-*.log"
  if [ -s "$HERE/WINEDEBUG" ]; then
    export WINEDEBUG="+timestamp,+tid,+seh,+loaddll,$(tr -d ' \n' < "$HERE/WINEDEBUG")"
    log "WINEDEBUG=$WINEDEBUG"
  fi
fi

# Frame rate / GPU load overlay (DXVK, on top of dgVoodoo's D3D11): a file DXVK_HUD beside this script holding
# e.g. fps,gpuload.
if [ -s "$HERE/DXVK_HUD" ]; then
  export DXVK_HUD="$(tr -d ' \n' < "$HERE/DXVK_HUD")"
  log "DXVK_HUD=$DXVK_HUD"
fi

for f in mtv.exe ddraw.dll d3dimm.dll dgVoodoo.conf data/kickPC.blb data/INT_HRV.avi data/MTV_HRV.avi \
         data/DEF_HRV.avi data/Cyp_LRV.avi data/NUN_LRV.avi; do
  [ -e "$HERE/game/$f" ] || log "WARNING: game/$f missing"
done
log "saves: $(ls -l "$HERE/game/KICKFLIP.SAV" 2>/dev/null | awk '{print $5, $NF}')"

log "exec: $*"
exec "$@"
