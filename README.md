# cosmic-mission-control

macOS-style four-finger gestures for the [COSMIC](https://system76.com/cosmic) desktop.

COSMIC handles four-finger left/right on its own, but up and down do nothing, and
gestures stop working while the Workspaces Overview is open. This fills both gaps.

| Gesture | On the desktop | In the overview |
|---|---|---|
| 4 fingers up | Open the Workspaces Overview | |
| 4 fingers down | Open the App Library | Close the overview |
| 4 fingers left / right | Switch workspace (COSMIC's own) | Switch workspace, overview stays open |

Works over fullscreen video, fires mid-swipe instead of waiting for you to lift
your fingers, and copes with the four-finger "pinches" libinput reports when
your fingers drift together during a swipe.

## Install

```sh
git clone https://github.com/cityji/cosmic-mission-control
cd cosmic-mission-control
./install.sh
```

The installer adds `libinput-tools` and `ydotool` if missing, makes sure you are in the
`input` group, and starts a systemd user service. If it adds you to `input`, log out
and back in once.

Tested on Pop!_OS 24.04 with COSMIC Epoch 1 (cosmic-comp 1.0, cosmic-workspaces 1.0.12).

## How it works

* Reads gesture events from the **touchpad only** with `libinput debug-events`.
  Keyboard input is never read.
* Opens and closes the overview through its own DBus API
  (`com.system76.CosmicWorkspaces.Show` / `Hide`) and follows its `Shown` / `Hidden`
  signals, so it always knows whether the overview is really on screen.
* Inside the overview, where COSMIC ignores gestures, left/right sends COSMIC's
  workspace shortcut (`Super+Ctrl+Left/Right`) through `ydotool`.
* Launches the App Library with `cosmic-app-library`, the same command `Super+A` runs.

## Tuning

Set these in the service with `systemctl --user edit cosmic-mission-control`:

```ini
[Service]
Environment=CMC_FIRE_V=38      # vertical travel before up/down fires (about mm)
Environment=CMC_FIRE_H=45      # horizontal travel before a workspace step
Environment=CMC_DOMINANCE=1.3  # how clearly one direction must win over the other
```

## Troubleshooting

Every gesture is logged with its direction and the action taken:

```sh
tail -f ~/.cache/cosmic-mission-control.log
```

```
06:01:08 swipe 4f dx=-18 dy=-50 overview=shown  -> up: show overview
06:01:11 swipe 4f dx=-48 dy=-4  overview=shown  -> left: workspace in overview
06:01:14 swipe 4f dx=+3  dy=+39 overview=hidden -> down: hide overview
```

* **No lines appear when you swipe:** you are not in the `input` group yet. Log out and back in.
* **Left/right does nothing inside the overview:** `ydotoold` is not running.
  `sudo systemctl enable --now ydotoold`

## Uninstall

```sh
./uninstall.sh
```

## Known limits

* Switching workspace inside the overview uses a keyboard shortcut, so if you have
  remapped `Super+Ctrl+Left/Right`, update `switch()` in the script.
* When COSMIC ships native up/down gestures, uninstall this to avoid double actions.

MIT License.
