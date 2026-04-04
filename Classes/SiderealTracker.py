import threading
import time

from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u


class SiderealTracker:
    """
    Tracks a star at a known RA/Dec by computing sidereal drift in Alt/Az
    and driving the motors accordingly — no camera required.

    On each tick the tracker:
      1. Transforms the star's RA/Dec (J2000) to Alt/Az at *now* and at
         *now + update_interval* using the observer's GPS position.
      2. Derives d_alt and d_az (the angular distance the star moves over
         the interval).
      3. Converts each delta to motor steps (400 000 steps / 360°).
      4. Spreads the steps evenly across the interval via the Arduino 't'
         command (inter-step delay in ms), so the motor moves continuously
         rather than in a single jerk.

    Motor protocol (Arduino serial, one value per line):
        v=1  – select altitude (vertical) axis
        v=0  – select azimuth (horizontal) axis
        d=1  – direction up / clockwise (positive delta)
        d=0  – direction down / counter-clockwise (negative delta)
        t=F  – inter-step delay in ms (must be set before s)
        s=N  – step count AND triggers the move
        e=1  – energise (hold torque) the currently selected axis
        e=0  – de-energise the currently selected axis

    Axis convention matches StarFollower:
        Altitude  : v=1   up=d=1  down=d=0
        Azimuth   : v=0   clockwise=d=1  counter-clockwise=d=0
    """

    STEPS_PER_DEGREE: float = 400_000 / 360.0   # ≈ 1111.11 steps / degree

    # Keep-alive strings (send_command appends its own \n, so these match
    # the StarFollower convention where "e=1\n" is stored as a constant).
    _ENABLE_ON  = "e=1\n"
    _ENABLE_OFF = "e=0\n"

    def __init__(self, motor_control):
        self.motor = motor_control
        self._lock = threading.Lock()
        # Set → tracking active.  Cleared → threads idle (wait for next start).
        self._active_event = threading.Event()
        self._params: dict = {}
        self._thread: threading.Thread | None = None
        self._keep_alive_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, ra_hours: float, dec_deg: float,
              lat: float, lon: float,
              update_interval: float = 5.0) -> None:
        """
        Begin sidereal tracking.

        Args:
            ra_hours        – Right Ascension in decimal hours (J2000).
            dec_deg         – Declination in decimal degrees (J2000).
            lat             – Observer latitude  in decimal degrees (+ = north).
            lon             – Observer longitude in decimal degrees (+ = east).
            update_interval – Seconds between motor correction ticks.
                              Steps are spread evenly across this window via t=<ms>
                              so the motor moves continuously, not in a single burst.
        """
        with self._lock:
            self._params = {
                'ra_hours':        float(ra_hours),
                'dec_deg':         float(dec_deg),
                'lat':             float(lat),
                'lon':             float(lon),
                'update_interval': float(update_interval),
            }

        self._active_event.set()

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="SiderealTrackerThread")
            self._thread.start()
            print("[SiderealTracker] Tracking thread started.")
        else:
            print("[SiderealTracker] Parameters updated; existing thread will use new values.")

        if self._keep_alive_thread is None or not self._keep_alive_thread.is_alive():
            self._keep_alive_thread = threading.Thread(
                target=self._run_keep_alive, daemon=True,
                name="SiderealTrackerKeepAliveThread")
            self._keep_alive_thread.start()
            print("[SiderealTracker] Keep-alive thread started.")

    def stop(self) -> None:
        """Pause tracking.  Threads stay alive and resume on the next start() call."""
        self._active_event.clear()
        print("[SiderealTracker] Stopped.")

    def get_status(self) -> dict:
        """Return current state and parameters (safe for JSON serialisation)."""
        with self._lock:
            params_safe = dict(self._params)
        return {
            'active': self._active_event.is_set(),
            'params': params_safe,
        }

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """
        Long-lived daemon thread.
        Idles (blocks on _active_event) when stop() has been called.
        Wakes and resumes tracking immediately when start() is called again.
        """
        print("[SiderealTracker] Thread ready.")
        while True:
            # Block here — no CPU burn — until start() sets the event.
            self._active_event.wait()

            with self._lock:
                if not self._params:
                    time.sleep(0.1)
                    continue
                p = dict(self._params)

            ra_hours        = p['ra_hours']
            dec_deg         = p['dec_deg']
            lat             = p['lat']
            lon             = p['lon']
            update_interval = p['update_interval']

            # ---- Compute sidereal drift for the next interval ----------
            t1 = Time.now()
            t2 = t1 + update_interval * u.second

            location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg)
            star     = SkyCoord(ra=ra_hours * u.hour,
                                dec=dec_deg * u.deg,
                                frame='icrs')
            frame1 = AltAz(obstime=t1, location=location)
            frame2 = AltAz(obstime=t2, location=location)

            altaz1 = star.transform_to(frame1)
            altaz2 = star.transform_to(frame2)

            d_alt = altaz2.alt.deg - altaz1.alt.deg

            # Normalise to [-180°, 180°] to handle the 359° → 0° wrap.
            d_az = altaz2.az.deg - altaz1.az.deg
            if d_az > 180.0:
                d_az -= 360.0
            elif d_az < -180.0:
                d_az += 360.0

            print(f"[SiderealTracker] Alt={altaz1.alt.deg:.3f}°  Az={altaz1.az.deg:.3f}°  "
                  f"Δalt={d_alt * 3600:.3f}\"  Δaz={d_az * 3600:.3f}\"  "
                  f"interval={update_interval}s")

            # ---- Drive altitude axis ----------------------------------
            steps_alt = round(abs(d_alt) * self.STEPS_PER_DEGREE)
            if steps_alt > 0 and self._active_event.is_set():
                t_ms_alt = (update_interval * 1000.0) / steps_alt
                dir_alt  = 1 if d_alt >= 0 else 0    # up=1, down=0
                print(f"[SiderealTracker] Altitude  steps={steps_alt}  "
                      f"t={t_ms_alt:.3f}ms/step  dir={'up' if dir_alt else 'down'}")
                self._send_move(axis=1, direction=dir_alt,
                                steps=steps_alt, t_ms=t_ms_alt)

            # Check for stop() between the two axis moves.
            if not self._active_event.is_set():
                continue

            # ---- Drive azimuth axis -----------------------------------
            steps_az = round(abs(d_az) * self.STEPS_PER_DEGREE)
            if steps_az > 0 and self._active_event.is_set():
                t_ms_az = (update_interval * 1000.0) / steps_az
                dir_az  = 1 if d_az >= 0 else 0    # clockwise=1, ccw=0
                print(f"[SiderealTracker] Azimuth   steps={steps_az}  "
                      f"t={t_ms_az:.3f}ms/step  dir={'cw' if dir_az else 'ccw'}")
                self._send_move(axis=0, direction=dir_az,
                                steps=steps_az, t_ms=t_ms_az)

            # ---- Wait for next tick -----------------------------------
            # The motors are already moving during this sleep because the
            # Arduino begins stepping immediately after receiving s=<N>.
            time.sleep(update_interval)

    def _run_keep_alive(self) -> None:
        """
        Dedicated daemon thread that energises both motor axes every second
        while tracking is active, preventing them from losing holding torque.

        Mirrors StarFollower._run_keep_alive but covers both axes.
        """
        print("[SiderealTracker] Keep-alive thread ready.")
        while True:
            self._active_event.wait()

            while self._active_event.is_set():
                self.motor.send_command("v=1")   # select altitude axis
                self.motor.send_command(self._ENABLE_ON)
                self.motor.send_command("v=0")   # select azimuth axis
                self.motor.send_command(self._ENABLE_ON)
                time.sleep(1)

            # De-energise both axes when stopped.
            self.motor.send_command("v=1")
            self.motor.send_command(self._ENABLE_OFF)
            self.motor.send_command("v=0")
            self.motor.send_command(self._ENABLE_OFF)
            print("[SiderealTracker] Keep-alive disabled (both axes de-energised).")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_move(self, axis: int, direction: int,
                   steps: int, t_ms: float) -> None:
        """
        Send the four-command sequence for a single-axis move.

        Order: v (axis select) → d (direction) → t (inter-step delay) → s (step count).
        This matches the protocol used in test_camera_rotation.py where
        "v=0\\nd=0\\nt=1\\ns=2500\\n" is sent as a combined command.

        The 't' command sets the inter-step delay in milliseconds; the
        's' command sets the step count and triggers the move.
        """
        cmds = [
            f"v={axis}",
            f"d={direction}",
            f"t={t_ms:.3f}",
            f"s={steps}",
        ]
        for cmd in cmds:
            if not self.motor.send_command(cmd):
                print(f"[SiderealTracker] Warning: failed to send '{cmd}'")
