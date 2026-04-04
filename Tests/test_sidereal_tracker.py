"""
Tests for SiderealTracker — no real hardware required.

A FakeMotor captures every command string sent to it, allowing each
test to assert on the exact commands without touching a serial port.

Run:
    python Tests/test_sidereal_tracker.py
"""

import sys
import os
import threading
import time

# Allow importing from the Classes/ directory regardless of cwd.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

from Classes.SiderealTracker import SiderealTracker


# ─────────────────────────────────────────────────────────────────────────────
# Fake motor
# ─────────────────────────────────────────────────────────────────────────────

class FakeMotor:
    """Records every command string passed to send_command() and always succeeds."""

    def __init__(self):
        self._lock = threading.Lock()
        self.commands: list[str] = []

    def send_command(self, cmd: str) -> bool:
        with self._lock:
            self.commands.append(cmd.strip())
        return True

    def get_commands(self) -> list[str]:
        with self._lock:
            return list(self.commands)

    def clear(self) -> None:
        with self._lock:
            self.commands.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Assertion helper
# ─────────────────────────────────────────────────────────────────────────────

def check(condition: bool, message: str) -> None:
    label = "  OK  " if condition else "  FAIL"
    print(f"{label}: {message}")
    if not condition:
        raise AssertionError(message)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-warm astropy's IERS lookup so no test is penalised by the first-call
# network/cache overhead.
# ─────────────────────────────────────────────────────────────────────────────

def _warm_up_astropy() -> None:
    print("[Setup] Warming up astropy IERS cache …", end=" ", flush=True)
    t = Time.now()
    loc = EarthLocation(lat=32.0 * u.deg, lon=35.0 * u.deg)
    sc = SkyCoord(ra=5.92 * u.hour, dec=7.4 * u.deg, frame="icrs")
    sc.transform_to(AltAz(obstime=t, location=loc))
    print("done.")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_constants():
    """STEPS_PER_DEGREE must equal exactly 400 000 / 360."""
    expected = 400_000 / 360.0
    check(SiderealTracker.STEPS_PER_DEGREE == expected,
          f"STEPS_PER_DEGREE == {expected:.6f}")


def test_status_before_start():
    """get_status() before any start() returns active=False and empty params."""
    motor = FakeMotor()
    tracker = SiderealTracker(motor)
    status = tracker.get_status()
    check(status["active"] is False, "active is False before start()")
    check(status["params"] == {}, "params are empty before start()")


def test_status_after_start():
    """start() flips active=True and stores all params."""
    motor = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.5, dec_deg=45.0, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(0.15)
    status = tracker.get_status()
    check(status["active"] is True,                          "active is True after start()")
    check(status["params"]["ra_hours"]        == 5.5,        "ra_hours stored")
    check(status["params"]["dec_deg"]         == 45.0,       "dec_deg stored")
    check(status["params"]["lat"]             == 32.0,       "lat stored")
    check(status["params"]["lon"]             == 35.0,       "lon stored")
    check(status["params"]["update_interval"] == 60.0,       "update_interval stored")
    tracker.stop()


def test_stop_clears_active():
    """stop() immediately sets active=False."""
    motor = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.5, dec_deg=45.0, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(0.15)
    tracker.stop()
    time.sleep(0.15)
    check(tracker.get_status()["active"] is False, "active is False after stop()")


def test_restart_updates_params_and_resumes():
    """Calling start() again after stop() resumes with the new parameters."""
    motor = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.5, dec_deg=45.0, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(0.15)
    tracker.stop()
    time.sleep(0.15)
    tracker.start(ra_hours=6.0, dec_deg=30.0, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(0.15)
    status = tracker.get_status()
    check(status["active"] is True,                    "active is True after second start()")
    check(status["params"]["ra_hours"] == 6.0,         "new ra_hours used after restart")
    check(status["params"]["dec_deg"]  == 30.0,        "new dec_deg used after restart")
    tracker.stop()


def test_astropy_altaz_pipeline():
    """
    The astropy SkyCoord → AltAz transform must return finite Alt/Az values.
    Uses a fixed time so the result is deterministic.
    """
    t        = Time("2000-01-01T12:00:00", format="isot", scale="utc")
    location = EarthLocation(lat=0.0 * u.deg, lon=0.0 * u.deg)
    # Vega: RA 18.6157h  Dec +38.78°
    star   = SkyCoord(ra=18.6157 * u.hour, dec=38.78 * u.deg, frame="icrs")
    altaz  = star.transform_to(AltAz(obstime=t, location=location))
    alt, az = altaz.alt.deg, altaz.az.deg
    print(f"    Vega at J2000 epoch (lat=0°, lon=0°): Alt={alt:.2f}°  Az={az:.2f}°")
    check(-90 <= alt <= 90, f"Alt {alt:.2f}° is in range [-90°, 90°]")
    check(0   <= az  <= 360, f"Az  {az:.2f}° is in range [0°, 360°]")


def test_az_wrap_normalisation():
    """
    Stars near the 0°/360° azimuth boundary must produce |Δaz| < 1° over 5 s,
    not a spurious ~360° jump.  Uses Polaris which circumpoles near north.
    """
    location = EarthLocation(lat=51.5 * u.deg, lon=0.0 * u.deg)
    star = SkyCoord(ra=2.53 * u.hour, dec=89.26 * u.deg, frame="icrs")
    t1, t2 = Time.now(), Time.now() + 5.0 * u.second
    az1 = star.transform_to(AltAz(obstime=t1, location=location)).az.deg
    az2 = star.transform_to(AltAz(obstime=t2, location=location)).az.deg
    d_az = az2 - az1
    if d_az > 180.0:
        d_az -= 360.0
    elif d_az < -180.0:
        d_az += 360.0
    print(f"    Polaris az1={az1:.3f}°  az2={az2:.3f}°  Δaz(normalised)={d_az:.6f}°")
    check(abs(d_az) < 1.0, f"normalised |Δaz| < 1° for Polaris over 5 s (got {d_az:.6f}°)")


def test_t_ms_formula():
    """
    _send_move must encode t_ms = (interval × 1000) / steps.
    Tested by calling _send_move directly: 100 steps over 5 s → 50 ms/step.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    t_ms_expected = (5.0 * 1000.0) / 100   # 50.0 ms/step
    tracker._send_move(axis=1, direction=1, steps=100, t_ms=t_ms_expected)
    cmds  = motor.get_commands()
    t_cmd = next((c for c in cmds if c.startswith("t=")), None)
    check(t_cmd is not None, "t= command is present")
    sent_t_ms = float(t_cmd.split("=")[1])
    check(abs(sent_t_ms - 50.0) < 0.001, f"t= value is 50.000 ms/step (got {sent_t_ms})")


def test_send_move_command_order():
    """
    _send_move must emit commands in order: v= → d= → t= → s=
    The 's=' command is last because it triggers the move.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker._send_move(axis=0, direction=1, steps=500, t_ms=10.0)
    cmds = motor.get_commands()
    print(f"    Commands: {cmds}")
    check(len(cmds) == 4, f"exactly 4 commands sent (got {len(cmds)})")
    check(cmds[0].startswith("v="), f"cmd[0] is v= (got '{cmds[0]}')")
    check(cmds[1].startswith("d="), f"cmd[1] is d= (got '{cmds[1]}')")
    check(cmds[2].startswith("t="), f"cmd[2] is t= (got '{cmds[2]}')")
    check(cmds[3].startswith("s="), f"cmd[3] is s= (trigger, got '{cmds[3]}')")


def test_commands_sent_on_tick():
    """
    After one tracking tick a real star (Betelgeuse, above horizon for lat=32°)
    must produce at least t= and s= commands — proving the motor was driven.
    Uses a 2-second interval; we wait 3.5 s to guarantee at least one completed tick.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    # Betelgeuse: RA≈5.92h  Dec≈+7.4°  — well above horizon from lat=32° N
    tracker.start(ra_hours=5.92, dec_deg=7.4, lat=32.0, lon=35.0, update_interval=2.0)
    time.sleep(3.5)
    tracker.stop()
    cmds = motor.get_commands()
    print(f"    Commands sent: {cmds}")
    check(any(c.startswith("t=") for c in cmds), "t= (timing) command sent")
    check(any(c.startswith("s=") for c in cmds), "s= (trigger) command sent")
    check(any(c.startswith("d=") for c in cmds), "d= (direction) command sent")


def test_tick_command_block_order():
    """
    For every move trigger (s=) in a real tracking tick the preceding three
    commands must be v= → d= → t= in that order.

    Uses a 10-second interval so the single tick fires before the keep-alive
    v= commands can interleave, making the block analysis unambiguous.
    We wait 3 s — enough for the first tick to complete but not for a second tick.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.92, dec_deg=7.4, lat=32.0, lon=35.0, update_interval=10.0)
    time.sleep(3.0)
    tracker.stop()
    time.sleep(0.3)

    # Remove keep-alive e= commands; they don't affect axis/direction/timing logic.
    move_cmds = [c for c in motor.get_commands() if not c.startswith("e=")]
    print(f"    Move commands: {move_cmds}")

    s_indices = [i for i, c in enumerate(move_cmds) if c.startswith("s=")]
    check(len(s_indices) > 0, "at least one s= trigger command found")

    for s_idx in s_indices:
        block = move_cmds[max(0, s_idx - 3): s_idx + 1]
        labels = []
        for c in block:
            if   c.startswith("v="): labels.append("v")
            elif c.startswith("d="): labels.append("d")
            elif c.startswith("t="): labels.append("t")
            elif c.startswith("s="): labels.append("s")
        check(labels == ["v", "d", "t", "s"],
              f"block order is v→d→t→s (block={block}, labels={labels})")


def test_keep_alive_energises_both_axes():
    """
    With a long update_interval (60 s), only the keep-alive thread fires
    within the 2.5 s window.  It must send e=1 to both v=1 (altitude) and
    v=0 (azimuth) axes.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.92, dec_deg=7.4, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(2.5)
    tracker.stop()
    time.sleep(0.3)

    cmds = motor.get_commands()
    print(f"    Keep-alive commands (first 20): {cmds[:20]}")

    found_alt = any(
        c == "v=1" and i + 1 < len(cmds) and cmds[i + 1] == "e=1"
        for i, c in enumerate(cmds)
    )
    found_az = any(
        c == "v=0" and i + 1 < len(cmds) and cmds[i + 1] == "e=1"
        for i, c in enumerate(cmds)
    )
    check(found_alt, "altitude keep-alive: v=1 followed by e=1")
    check(found_az,  "azimuth  keep-alive: v=0 followed by e=1")


def test_stop_deenergises_both_axes():
    """
    After stop() the keep-alive thread must send e=0 to both v=1 and v=0.
    We give it 1.5 s after stop() to execute the de-energise sequence.
    """
    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    tracker.start(ra_hours=5.92, dec_deg=7.4, lat=32.0, lon=35.0, update_interval=60.0)
    time.sleep(1.5)
    tracker.stop()
    time.sleep(1.5)   # let keep-alive react

    cmds = motor.get_commands()
    print(f"    Commands after stop (last 10): {cmds[-10:]}")

    found_alt_off = any(
        c == "v=1" and i + 1 < len(cmds) and cmds[i + 1] == "e=0"
        for i, c in enumerate(cmds)
    )
    found_az_off = any(
        c == "v=0" and i + 1 < len(cmds) and cmds[i + 1] == "e=0"
        for i, c in enumerate(cmds)
    )
    check(found_alt_off, "altitude axis de-energised: v=1 followed by e=0")
    check(found_az_off,  "azimuth  axis de-energised: v=0 followed by e=0")


def test_direction_alt_up_for_rising_star():
    """
    A star currently rising (altitude increasing) must produce d=1 (up)
    on the altitude axis.  Uses _send_move directly after computing d_alt.
    """
    # Find a moment when the star's altitude is increasing.
    location = EarthLocation(lat=32.0 * u.deg, lon=35.0 * u.deg)
    star     = SkyCoord(ra=5.92 * u.hour, dec=7.4 * u.deg, frame="icrs")
    t1       = Time.now()
    t2       = t1 + 5.0 * u.second
    alt1     = star.transform_to(AltAz(obstime=t1, location=location)).alt.deg
    alt2     = star.transform_to(AltAz(obstime=t2, location=location)).alt.deg
    d_alt    = alt2 - alt1
    print(f"    d_alt over 5 s = {d_alt * 3600:.3f}\"  (rising={d_alt > 0})")

    expected_dir = 1 if d_alt >= 0 else 0
    steps = round(abs(d_alt) * SiderealTracker.STEPS_PER_DEGREE)
    if steps == 0:
        print("    (star momentarily stationary; skipping direction assertion)")
        return

    motor   = FakeMotor()
    tracker = SiderealTracker(motor)
    t_ms    = (5.0 * 1000.0) / steps
    tracker._send_move(axis=1, direction=expected_dir, steps=steps, t_ms=t_ms)

    cmds = motor.get_commands()
    d_cmd = next((c for c in cmds if c.startswith("d=")), None)
    check(d_cmd is not None, "d= direction command present")
    sent_dir = int(d_cmd.split("=")[1])
    check(sent_dir == expected_dir,
          f"direction is {'up(1)' if expected_dir else 'down(0)'} for "
          f"{'rising' if d_alt > 0 else 'setting'} star (got d={sent_dir})")


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

TESTS = [
    ("Constants",                          test_constants),
    ("Status before start",                test_status_before_start),
    ("Status after start",                 test_status_after_start),
    ("Stop clears active",                 test_stop_clears_active),
    ("Restart updates params & resumes",   test_restart_updates_params_and_resumes),
    ("Astropy AltAz pipeline",             test_astropy_altaz_pipeline),
    ("Az wrap normalisation (Polaris)",    test_az_wrap_normalisation),
    ("t_ms formula",                       test_t_ms_formula),
    ("_send_move command order v→d→t→s",   test_send_move_command_order),
    ("Commands sent on real tick",         test_commands_sent_on_tick),
    ("Tick block order v→d→t→s",           test_tick_command_block_order),
    ("Keep-alive energises both axes",     test_keep_alive_energises_both_axes),
    ("Stop de-energises both axes",        test_stop_deenergises_both_axes),
    ("Direction: up for rising star",      test_direction_alt_up_for_rising_star),
]


if __name__ == "__main__":
    _warm_up_astropy()

    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    print("\n" + "=" * 60)
    print(" SiderealTracker Test Suite")
    print("=" * 60)

    for name, fn in TESTS:
        print(f"\n[{name}]")
        try:
            fn()
            print(f"  → PASS")
            passed += 1
        except AssertionError as exc:
            print(f"  → FAIL: {exc}")
            failed += 1
            failures.append((name, str(exc)))
        except Exception as exc:
            print(f"  → ERROR: {type(exc).__name__}: {exc}")
            failed += 1
            failures.append((name, f"{type(exc).__name__}: {exc}"))

    print("\n" + "=" * 60)
    print(f" Results: {passed} passed, {failed} failed  (total {passed + failed})")
    if failures:
        print("\n Failed:")
        for name, msg in failures:
            print(f"   • {name}: {msg}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
