#!/usr/bin/env bash
# Installs cosmic-mission-control for the current user.
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '  %s\n' "$*"; }
fail() { printf '\n  ✗ %s\n\n' "$*" >&2; exit 1; }

echo
echo "cosmic-mission-control installer"
echo

[ "${XDG_CURRENT_DESKTOP:-}" = "COSMIC" ] || pidof cosmic-comp >/dev/null || fail "COSMIC desktop not detected."
command -v python3 >/dev/null || fail "python3 is required."
command -v gdbus   >/dev/null || fail "gdbus is required (package: libglib2.0-bin)."

need=()
command -v libinput >/dev/null || need+=(libinput-tools)
command -v ydotool  >/dev/null || need+=(ydotool)
python3 -c "import evdev" 2>/dev/null || need+=(python3-evdev)
if [ ${#need[@]} -gt 0 ]; then
  say "Installing: ${need[*]}"
  sudo apt-get install -y "${need[@]}" >/dev/null
fi

# libinput needs read access to the touchpad: the user must be in the 'input' group.
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  say "Adding $USER to the 'input' group (log out and back in afterwards)."
  sudo usermod -aG input "$USER"
  RELOGIN=1
fi

# ydotool needs its daemon for the in-overview workspace shortcut.
if ! pgrep -x ydotoold >/dev/null; then
  if systemctl list-unit-files ydotoold.service >/dev/null 2>&1; then
    say "Enabling ydotoold."
    sudo systemctl enable --now ydotoold >/dev/null 2>&1 || true
  fi
  pgrep -x ydotoold >/dev/null || say "Note: start ydotoold so left/right works inside the overview."
fi

# Three-finger drag moves the pointer through a virtual mouse. Give that device flat
# acceleration so drag speed matches the touchpad exactly instead of being accelerated twice.
DEVCFG="$HOME/.config/cosmic/com.system76.CosmicComp/v1/input_devices"
if [ ! -s "$DEVCFG" ]; then
  mkdir -p "$(dirname "$DEVCFG")"
  # write then rename: COSMIC watches this folder and would otherwise read a half-written file
  cat > "$DEVCFG.tmp" <<'RON'
{
    "cosmic-mission-control pointer": (
        state: Enabled,
        acceleration: Some((
            profile: Some(Flat),
            speed: 0.0,
        )),
    ),
}
RON
  mv "$DEVCFG.tmp" "$DEVCFG"
elif ! grep -q "cosmic-mission-control pointer" "$DEVCFG"; then
  say "Note: $DEVCFG already exists; add flat acceleration for"
  say "      \"cosmic-mission-control pointer\" by hand for exact drag speed."
fi

# Replace the earlier name of this tool if present.
systemctl --user disable --now swipe-overview.service >/dev/null 2>&1 || true

install -Dm755 cosmic-mission-control "$HOME/.local/bin/cosmic-mission-control"
install -Dm644 cosmic-mission-control.service "$HOME/.config/systemd/user/cosmic-mission-control.service"
systemctl --user daemon-reload
systemctl --user enable cosmic-mission-control.service >/dev/null 2>&1
systemctl --user restart cosmic-mission-control.service

sleep 1
if systemctl --user is-active --quiet cosmic-mission-control.service; then
  echo
  say "✓ Installed and running."
  say "  4 fingers up      Workspaces Overview"
  say "  4 fingers down    App Library (or close the overview)"
  say "  4 left / right    switch workspaces, also inside the overview"
  say "  3 fingers         drag windows, text and files (macOS three-finger drag)"
  say "  Log: ~/.cache/cosmic-mission-control.log"
else
  fail "Service did not start. Check: journalctl --user -u cosmic-mission-control"
fi
[ "${RELOGIN:-0}" = 1 ] && say "  Log out and back in once so the 'input' group takes effect."
echo
