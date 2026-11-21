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
        self.now = 100.0
        self.det = cmc.Detector(cmc.Controller(self.bus, run=lambda *c: self.ran.append(" ".join(c)),
                                               clock=lambda: self.now))

    def swipe(self, dx, dy, gap=1.0, **kw):
        self.now += gap                          # seconds since the previous gesture
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
        self.assertEqual(h.bus.calls, ["Show", "Hide"])   # no redundant Show after a step
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

    def test_sideways_flick_does_not_step(self):
        h = Harness()
        h.swipe(0, -50)
        self.assertIsNone(h.swipe(-24, 0, duration=0.05))                       # quick 2 cm twitch
        self.assertEqual(h.ran, [])

    def test_deliberate_sideways_swipe_steps(self):
        h = Harness()
        h.swipe(0, -50)
        self.assertEqual(h.swipe(-45, 0, duration=0.15), "workspace left in overview")

    def test_bouncy_double_swipe_steps_once(self):
        h = Harness()
        h.swipe(0, -50)
        h.swipe(-45, 0)
        self.assertEqual(h.swipe(-45, 0, gap=0.15), "ignored: too soon after the last step")
        self.assertEqual(h.ran, ["ydotool key super+ctrl+Left"])

    def test_step_arms_reshow(self):
        h = Harness()
        h.swipe(0, -50)
        h.swipe(45, 0)
        self.assertAlmostEqual(h.bus.reshow_until, h.now + cmc.RESHOW_WINDOW)


class FakeTimers:
    def __init__(self):
        self.pending, self.next = {}, 1

    def later(self, ms, fn):
        tid, self.next = self.next, self.next + 1
        self.pending[tid] = fn
        return tid

    def cancel(self, tid):
        self.pending.pop(tid, None)

    def fire_all(self):
        for tid in list(self.pending):
            self.pending.pop(tid)()


MM = 31.0                                    # raw touchpad units per mm on the reference pad


class DragHarness:
    def __init__(self):
        self.ptr = cmc.LogPointer()
        self.timers = FakeTimers()
        self.curve = cmc.PointerCurve(persist=False)
        self.drag = cmc.Dragger(self.ptr, self.curve, self.timers.later, self.timers.cancel, MM)
        self.t = 10.0

    def frames(self, count, dx_mm=0.0, dy_mm=0.0, n=1, hz=125):
        for _ in range(n):
            self.t += 1 / hz
            self.drag.frame(count, dx_mm * MM / n, dy_mm * MM / n, self.t)

    def stroke(self, dx_mm, dy_mm, seconds=0.3, lift=True):
        self.frames(3)                                         # fingers land
        self.frames(3, dx_mm, dy_mm, n=max(int(seconds * 125), 1))
        if lift:
            self.frames(0)

    def moved(self):
        return (sum(e[1] for e in self.ptr.events if e[0] == "move"),
                sum(e[2] for e in self.ptr.events if e[0] == "move"))

    def kinds(self):
        return [e[0] for e in self.ptr.events if e[0] != "move"]


class DragTest(unittest.TestCase):
    def test_press_hold_during_grace_then_release(self):
        h = DragHarness()
        h.stroke(30, 0)
        self.assertEqual(h.kinds(), ["press"])
        h.timers.fire_all()
        self.assertEqual(h.kinds(), ["press", "release"])

    def test_drag_matches_one_finger_pointer_distance(self):
        h = DragHarness()
        h.stroke(40, 0, seconds=0.5)                           # 80 mm/s: ordinary pointing speed
        speed = 40 * MM / 500                                  # raw units per ms
        expected = 40 * MM * h.curve.gain(speed)
        self.assertAlmostEqual(h.moved()[0], expected, delta=expected * 0.03)

    def test_no_motion_is_lost_at_the_start(self):
        h = DragHarness()
        h.frames(3)
        h.frames(3, 0.7, 0, n=2)                               # below the start threshold...
        self.assertEqual(h.ptr.events, [])
        h.frames(3, 20, 0, n=40)                               # ...then the real drag
        total_mm = 20.7
        self.assertGreater(h.moved()[0], total_mm * MM * 0.33 * 0.95)

    def test_lift_and_continue_is_one_drag(self):
        h = DragHarness()
        h.stroke(20, 0)
        h.stroke(20, 0)
        h.timers.fire_all()
        self.assertEqual(h.kinds(), ["press", "release"])

    def test_resting_fingers_and_taps_never_click(self):
        h = DragHarness()
        h.frames(3, 0.3, 0, n=20)
        h.frames(0)
        h.timers.fire_all()
        self.assertEqual(h.ptr.events, [])

    def test_four_fingers_never_click_and_block_until_lift(self):
        h = DragHarness()
        h.frames(3)                                            # third finger first...
        h.frames(4, 10, 0, n=10)                               # ...fourth lands: a swipe
        h.frames(3, 10, 0, n=10)                               # one lifts early
        h.frames(0)
        self.assertEqual(h.ptr.events, [])

    def test_fourth_finger_drops_a_drag(self):
        h = DragHarness()
        h.stroke(20, 0, lift=False)
        h.frames(4)
        self.assertEqual(h.kinds(), ["press", "release"])

    def test_pointing_during_grace_drops(self):
        h = DragHarness()
        h.stroke(20, 0)
        h.frames(1, 3, 0, n=5)
        self.assertEqual(h.kinds(), ["press", "release"])

    def test_click_drops_immediately(self):
        h = DragHarness()
        h.stroke(20, 0)
        h.drag.touch()
        self.assertEqual(h.kinds(), ["press", "release"])
        self.assertEqual(h.timers.pending, {})

    def test_sub_pixel_motion_is_not_lost(self):
        h = DragHarness()
        h.frames(3)
        h.frames(3, 30, 0, n=300)                              # ~0.1 mm per frame
        self.assertGreater(h.moved()[0], 0)
        expected = 30 * MM * h.curve.gain(30 * MM / 2400)
        self.assertAlmostEqual(h.moved()[0], expected, delta=3)


class CurveTest(unittest.TestCase):
    def test_learns_from_pointer_motion(self):
        c = cmc.PointerCurve(persist=False)
        t = 1.0
        for _ in range(300):                                   # pointer reports 0.5 px per unit at 1 u/ms
            t += 0.008
            c.observe(f" event4   POINTER_MOTION   +{t:.3f}s\t  4.00/  0.00 ( 8.00/ +0.00)")
        self.assertAlmostEqual(c.gain(1.0), 0.5, delta=0.03)

    def test_seed_is_monotonic_enough(self):
        c = cmc.PointerCurve(persist=False)
        self.assertLess(c.gain(0.03), c.gain(1.0))
        self.assertLess(c.gain(1.0), c.gain(10.0))


if __name__ == "__main__":
    unittest.main()
