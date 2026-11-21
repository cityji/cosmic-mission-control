# cosmic-mission-control

macOS-style four-finger gestures for the [COSMIC](https://system76.com/cosmic) desktop.

COSMIC handles four-finger left/right on its own, but up and down do nothing, and
gestures stop working while the Workspaces Overview is open. This fills both gaps.

| Gesture | On the desktop | In the overview |
|---|---|---|
| 4 fingers up | Open the Workspaces Overview | Nothing (already open) |
| 4 fingers down | Open the App Library | Close the overview |
| 4 fingers left / right | Switch workspace (COSMIC's own) | Switch workspace, overview stays open |

## What makes it feel right

* **Responds mid-swipe.** It fires the moment the direction is clear, not when you lift your fingers.
* **Flick-aware.** A quick flick fires after a short distance; a slow, deliberate swipe needs a
  little more. Short accidental drags do nothing.
* **Never loses track of the overview.** It follows the overview's own `Shown` / `Hidden`
  signals, so closing it with Esc or a click is understood.
* **Forgiving.** Four fingers drifting together mid-swipe get reported by libinput as a pinch;
  those count too.
* **Light.** One small process, one event loop. Opening the overview is a single in-process
  DBus call of about a millisecond.
* **Private.** It reads the touchpad only. Keyboard input is never read.

## Install

```sh
git clone https://github.com/cityji/cosmic-mission-control
cd cosmic-mission-control
./install.sh
```

The installer adds `libinput-tools` and `ydotool` if missing, makes sure you are in the
`input` group, and starts a systemd user service. If it adds you to `input`, log out
and back in once.

Requires COSMIC Epoch 1 or later. Tested on Pop!_OS 24.04 (cosmic-comp 1.0, cosmic-workspaces 1.0.12).

## How it works

| Piece | Mechanism |
|---|---|
| Reading gestures | `libinput debug-events --device <touchpad>`, inside a GLib main loop |
| Overview | DBus `com.system76.CosmicWorkspaces.Show` / `Hide`, state from its `Shown` / `Hidden` signals |
| App Library | `cosmic-app-library`, the same command `Super+A` runs |
| Workspace switch in the overview | COSMIC's `Super+Ctrl+Left/Right` sent through `ydotool`, since COSMIC ignores gestures there |

## Tuning

`systemctl --user edit cosmic-mission-control`, then:

```ini
[Service]
Environment=CMC_FIRE_V=38        # vertical travel that always fires (about mm)
Environment=CMC_FIRE_H=45        # horizontal travel that always fires
Environment=CMC_FLICK_MIN=18     # a flick may fire after this much travel...
Environment=CMC_FLICK_SPEED=300  # ...if it is at least this fast (units per second)
Environment=CMC_DOMINANCE=1.3    # how clearly one direction must win
```

## Troubleshooting

Every gesture is logged with its travel, duration and the action taken:

```sh
tail -f ~/.cache/cosmic-mission-control.log
```

```
06:01:08 swipe dx=-6 dy=-42 140ms -> show overview
06:01:11 swipe dx=-48 dy=-4 120ms -> workspace left in overview
06:01:14 swipe dx=+3 dy=+39 110ms -> hide overview
```

* **Nothing is logged when you swipe:** you are not in the `input` group yet. Log out and back in.
* **Left/right does nothing inside the overview:** `ydotoold` is not running.
  `sudo systemctl enable --now ydotoold`
* **Try settings without touching your desktop:** `cosmic-mission-control --dry-run` reads the
  touchpad and prints what it would do.

## Development

```sh
python3 -m unittest discover -s tests -v            # gesture logic, no hardware needed
libinput debug-events --device /dev/input/eventN > swipes.txt
./cosmic-mission-control --replay swipes.txt        # replay real gestures through the detector
```

A replay file is the most useful thing to attach to a bug report.

## Uninstall

```sh
./uninstall.sh
```

## Known limits

* Switching workspace inside the overview uses a keyboard shortcut. If you remapped
  `Super+Ctrl+Left/Right`, change it in `Controller` in the script.
* When COSMIC ships native up/down gestures, uninstall this to avoid double actions.

MIT License.
