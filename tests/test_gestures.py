"""Gesture logic tests. No touchpad, compositor or DBus needed.

Run: python3 -m unittest discover -s tests -v
"""
import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loader = importlib.machinery.SourceFileLoader("cmc", str(ROOT / "cosmic-mission-control"))
_spec = importlib.util.spec_from_loader("cmc", _loader)
cmc = importlib.util.module_from_spec(_spec)
_loader.exec_module(cmc)
cmc.log.path = Path(tempfile.gettempdir()) / "cmc-test.log"


def lines(dx, dy, steps=10, duration=0.2, fingers=4, kind="SWIPE", t0=1.0):
    """Synthetic `libinput debug-events` output for one gesture."""
    out = [f"-event4   GESTURE_{kind}_BEGIN     +{t0:.3f}s\t{fingers}"]
    for i in range(1, steps + 1):
        t = t0 + duration * i / steps
        out.append(f" event4   GESTURE_{kind}_UPDATE    +{t:.3f}s\t{fingers} "
                   f"{dx / steps:5.2f}/{dy / steps:5.2f} ({dx / steps:5.2f}/{dy / steps:5.2f} unaccelerated)")
    out.append(f" event4   GESTURE_{kind}_END       +{t0 + duration + 0.01:.3f}s\t{fingers}")
    return out


class Harness:
    def __init__(self):
        self.bus = cmc.SimBus()
        self.ran = []
        self.det = cmc.Detector(cmc.Controller(self.bus, run=lambda *c: self.ran.append(" ".join(c))))

    def swipe(self, dx, dy, **kw):
        for line in lines(dx, dy, **kw):
            self.det.feed(line)
        return self.det.result


class ParseTest(unittest.TestCase):
    def test_update_line(self):
        ev = cmc.parse(" event4   GESTURE_SWIPE_UPDATE    +3.470s\t4  3.21/-12.45 ( 4.00/-15.00 unaccelerated)")
        self.assertEqual((ev["phase"], ev["fingers"], ev["dx"], ev["dy"], ev["t"]), ("UPDATE", 4, 3.21, -12.45, 3.47))

    def test_space_after_slash(self):
        ev = cmc.parse("-event4   GESTURE_PINCH_UPDATE    +9.001s\t4 -0.31/ 1.02 (-0.39/ 1.28 unaccelerated)  1.00 @  0.00")
        self.assertEqual((ev["kind"], ev["dx"], ev["dy"]), ("pinch", -0.31, 1.02))

    def test_event_number_not_mistaken_for_finger_count(self):
        ev = cmc.parse(" event4   GESTURE_SWIPE_UPDATE    +1.000s\t3  4.00/ 4.00 ( 4.00/ 4.00 unaccelerated)")
        self.assertEqual(ev["fingers"], 3)

    def test_ignores_other_events(self):
        self.assertIsNone(cmc.parse(" event4   POINTER_MOTION   +1.0s  1.00/ 2.00"))


class FlowTest(unittest.TestCase):
    def test_full_mission_control_flow(self):
        h = Harness()
        self.assertEqual(h.swipe(0, -50), "show overview")
        self.assertEqual(h.swipe(-55, 0), "workspace left in overview")
        self.assertEqual(h.swipe(55, 0), "workspace right in overview")
        self.assertEqual(h.swipe(0, 50), "hide overview")
        self.assertEqual(h.swipe(0, 50), "app library")
        self.assertEqual(h.bus.calls, ["Show", "Show", "Show", "Hide"])
        self.assertEqual(h.ran, ["ydotool key super+ctrl+Left", "ydotool key super+ctrl+Right",
                                 "cosmic-app-library"])

    def test_up_while_open_does_not_flicker(self):
        h = Harness()
        h.swipe(0, -50)
        self.assertEqual(h.swipe(0, -50), "overview already open")
        self.assertEqual(h.bus.calls, ["Show"])

    def test_desktop_left_right_left_to_cosmic(self):
        h = Harness()
        self.assertEqual(h.swipe(60, 0), "desktop: COSMIC switches workspace")
        self.assertEqual(h.ran, [])

    def test_overview_closed_elsewhere_is_respected(self):
        h = Harness()
        h.swipe(0, -50)
        h.bus.shown = False                     # e.g. Esc pressed: Hidden signal arrives
        self.assertEqual(h.swipe(0, 50), "app library")

    def test_fires_once_per_gesture(self):
        h = Harness()
        h.swipe(0, -200)
        self.assertEqual(h.bus.calls, ["Show"])

    def test_three_fingers_ignored(self):
        h = Harness()
        self.assertIsNone(h.swipe(0, -80, fingers=3))

    def test_pinch_counts_as_swipe(self):
        h = Harness()
        self.assertEqual(h.swipe(0, -50, kind="PINCH"), "show overview")

    def test_diagonal_is_ignored(self):
        h = Harness()
        self.assertIsNone(h.swipe(40, -40))


class FeelTest(unittest.TestCase):
    def test_quick_flick_fires_early(self):
        h = Harness()
        self.assertEqual(h.swipe(0, -24, duration=0.06), "show overview")      # 400 units/s

    def test_slow_short_drag_does_not_fire(self):
        h = Harness()
        self.assertIsNone(h.swipe(0, -24, duration=0.5))                        # 48 units/s

    def test_slow_full_swipe_fires(self):
        h = Harness()
        self.assertEqual(h.swipe(0, -40, duration=0.8), "show overview")


if __name__ == "__main__":
    unittest.main()
