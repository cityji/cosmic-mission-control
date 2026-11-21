#!/usr/bin/env bash
# Removes cosmic-mission-control for the current user.
set -euo pipefail
systemctl --user disable --now cosmic-mission-control.service >/dev/null 2>&1 || true
rm -f "$HOME/.local/bin/cosmic-mission-control" \
      "$HOME/.config/systemd/user/cosmic-mission-control.service" \
      "$HOME/.cache/cosmic-mission-control.log"
DEVCFG="$HOME/.config/cosmic/com.system76.CosmicComp/v1/input_devices"
if [ -f "$DEVCFG" ] && grep -q "cosmic-mission-control pointer" "$DEVCFG" && [ "$(grep -c '": (' "$DEVCFG")" = 1 ]; then
  rm -f "$DEVCFG"
fi
systemctl --user daemon-reload
echo "cosmic-mission-control removed."
