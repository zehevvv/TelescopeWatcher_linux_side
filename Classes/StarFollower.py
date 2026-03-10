import cv2
import numpy as np
import threading
import time
import requests


class StarFollower:
    """
    Tracks the brightest star in the camera frame and sends corrective motor
    commands to keep it centred.

    The heavyweight work runs in a single long-lived daemon thread.
    start() / stop() only update shared state; they never block.

    Motor direction commands (Arduino serial strings):
        Up    – v=1\\nd=1
        Down  – v=1\\nd=0
        Left  – v=0\\nd=0
        Right – v=0\\nd=1
    """

    # Raw Arduino serial direction strings
    _CMD_UP    = "v=1\nd=1\n"
    _CMD_DOWN  = "v=1\nd=0\n"    
    _CMD_LEFT  = "v=0\nd=0\n"
    _CMD_RIGHT = "v=0\nd=1\n"
    _ALWAYS_ENABLE_ON = "e=1\n"  
    _ALWAYS_ENABLE_OFF = "e=0\n"  

    def __init__(self, motor_control):
        self.motor = motor_control
        self._lock = threading.Lock()
        # Set   → loop is active.   Cleared → loop idles (waits to be re-activated).
        self._active_event = threading.Event()
        self._params: dict = {}
        self._thread: threading.Thread | None = None
        self._keep_alive_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API (called by the HTTP handler; never block the server)
    # ------------------------------------------------------------------

    def start(self, duration: float, threshold: float,
              steps_cmd: str, speed_cmd: str, camera_device) -> None:
        """
        Activate (or update) the auto-centre loop.

        Args:
            duration       – seconds between correction attempts.
            threshold      – dead-zone in percent (0-100).  A correction is only
                             sent when the star is displaced by more than this
                             fraction of the frame width (horizontal) or height
                             (vertical).  E.g. 10 means > 10 %.
            steps_cmd      – raw Arduino serial string that sets the step count
                             (e.g. "s=100").
            speed_cmd      – raw Arduino serial string that sets the move speed
                             (e.g. "sp=50").
            camera_device  – CameraDevice instance to grab frames from.
        """
        with self._lock:
            self._params = {
                'duration':      float(duration),
                'threshold':     float(threshold),
                'steps_cmd':     steps_cmd,
                'speed_cmd':     speed_cmd,
                'camera_device': camera_device,
            }

        # Tell the running thread to (re)start work
        self._active_event.set()

        # Spawn the background thread only once
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="StarFollowerThread")
            self._thread.start()
            print("[StarFollower] Background thread started.")
        else:
            print("[StarFollower] Parameters updated; existing thread will use new values.")

        # Spawn the keep-alive thread only once
        if self._keep_alive_thread is None or not self._keep_alive_thread.is_alive():
            self._keep_alive_thread = threading.Thread(target=self._run_keep_alive, daemon=True,
                                                       name="StarFollowerKeepAliveThread")
            self._keep_alive_thread.start()
            print("[StarFollower] Keep-alive thread started.")

    def stop(self) -> None:
        """Pause the auto-centre loop.  The background thread keeps running but idles."""
        self._active_event.clear()
        print("[StarFollower] Stopped.")

    def get_status(self) -> dict:
        """Return the current state and parameters (safe for JSON serialisation)."""
        with self._lock:
            # Exclude the non-serialisable CameraDevice reference
            params_safe = {k: v for k, v in self._params.items()
                           if k != 'camera_device'}
            if 'camera_device' in self._params:
                params_safe['camera'] = getattr(
                    self._params['camera_device'], 'camera_model', 'unknown')

        return {
            'active': self._active_event.is_set(),
            'params': params_safe,
        }

    def debug_star(self, camera_device) -> dict:
        """
        Capture one frame and report where the brightest star blob is detected.

        Returns a dict with keys:
            found          – bool
            cx / cy        – pixel centroid of the detected star
            frame_w        – frame width in pixels
            frame_h        – frame height in pixels
            offset_x_pct   – horizontal offset from centre as % of frame width
                             (positive = star is right of centre)
            offset_y_pct   – vertical offset from centre as % of frame height
                             (positive = star is below centre)
        """
        frame = self._capture_frame(camera_device)
        if frame is None:
            return {'found': False, 'error': 'Could not capture frame'}

        h, w = frame.shape[:2]

        # Compute the same DoG pipeline as _find_star to expose diagnostics
        frame_f      = frame.astype(np.float32)
        background_f = cv2.GaussianBlur(frame_f, (51, 51), 0)
        residual_f   = frame_f - background_f
        tight  = cv2.GaussianBlur(residual_f, (5, 5), 1)
        wide   = cv2.GaussianBlur(residual_f, (21, 21), 5)
        dog    = tight - wide
        _, max_val, _, _ = cv2.minMaxLoc(dog)
        mean_v, std_v = cv2.meanStdDev(dog)
        mean_v = float(mean_v[0][0])
        std_v  = float(std_v[0][0])
        sigma  = round((max_val - mean_v) / std_v, 2) if std_v >= 0.1 else 0.0

        star = self._find_star(frame)

        if star is None:
            return {
                'found':      False,
                'frame_w':    w,
                'frame_h':    h,
                'peak_sigma': sigma,
                'peak_val':   round(float(max_val), 2),
                'noise_std':  round(std_v, 2),
            }

        cx, cy = star
        offset_x_pct = round((cx - w / 2) / w * 100, 2)
        offset_y_pct = round((cy - h / 2) / h * 100, 2)

        return {
            'found':        True,
            'cx':           cx,
            'cy':           cy,
            'frame_w':      w,
            'frame_h':      h,
            'offset_x_pct': offset_x_pct,
            'offset_y_pct': offset_y_pct,
            'peak_sigma':   sigma,
            'peak_val':     round(float(max_val), 2),
            'noise_std':    round(std_v, 2),
        }

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """
        Long-lived daemon thread.
        Idles (blocks on _active_event) when stop() has been called.
        Wakes immediately and restarts work when start() is called again.
        """
        print("[StarFollower] Thread ready.")
        while True:
            # Block here – no CPU burn – until start() sets the event
            self._active_event.wait()

            # Snapshot params under the lock so start() can safely update them
            with self._lock:
                if not self._params:
                    # Shouldn't happen, but guard anyway
                    time.sleep(0.1)
                    continue
                p = dict(self._params)

            duration      = p['duration']
            threshold_pct = p['threshold']
            steps_cmd     = p['steps_cmd']
            speed_cmd     = p['speed_cmd']
            camera        = p['camera_device']

            # ---- Capture frame ----------------------------------------
            frame = self._capture_frame(camera)
            if frame is None:
                print("[StarFollower] Frame capture failed, retrying after delay...")
                time.sleep(duration)
                continue

            h, w = frame.shape[:2]

            # ---- Detect star ------------------------------------------
            star = self._find_star(frame)
            if star is None:
                print("[StarFollower] No star detected in frame.")
                time.sleep(duration)
                continue

            cx, cy = star
            dx = cx - w / 2   # positive → star is RIGHT of centre
            dy = cy - h / 2   # positive → star is BELOW centre

            offset_x_pct = abs(dx) / w * 100
            offset_y_pct = abs(dy) / h * 100

            print(f"[StarFollower] Star at ({cx}, {cy})  "
                  f"offset_x={offset_x_pct:.1f}%  offset_y={offset_y_pct:.1f}%  "
                  f"(threshold={threshold_pct}%)")

            # ---- Horizontal correction --------------------------------
            if offset_x_pct > threshold_pct:
                direction = self._CMD_RIGHT if dx > 0 else self._CMD_LEFT
                axis_name = "right" if dx > 0 else "left"
                print(f"[StarFollower] Correcting horizontal → {axis_name}")
                self._send_move(speed_cmd, steps_cmd, direction)

            # Re-check: stop() may have been called during the motor send
            if not self._active_event.is_set():
                continue

            # ---- Vertical correction ----------------------------------
            if offset_y_pct > threshold_pct:
                direction = self._CMD_DOWN if dy > 0 else self._CMD_UP
                axis_name = "down" if dy > 0 else "up"
                print(f"[StarFollower] Correcting vertical → {axis_name}")
                self._send_move(speed_cmd, steps_cmd, direction)

            # ---- Wait for next cycle ---------------------------------
            # time.sleep returns after `duration` seconds; stop() will take
            # effect at the latest after the current sleep expires.
            time.sleep(duration)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_keep_alive(self) -> None:
        """
        Dedicated daemon thread that keeps the up/down motor energised while
        the follower is active.

        While active  – sends v=1 (select vertical axis) + e=1 every second.
        When stopped  – sends v=1 + e=0 once, then idles until re-activated.
        """
        print("[StarFollower] Keep-alive thread ready.")
        while True:
            # Block here until start() sets the event
            self._active_event.wait()

            # Inner loop: send keep-alive every second while active
            while self._active_event.is_set():
                self.motor.send_command("v=1")  # select up/down motor
                self.motor.send_command(self._ALWAYS_ENABLE_ON)
                time.sleep(1)

            # Active event cleared: release motor hold
            self.motor.send_command("v=1")  # select up/down motor
            self.motor.send_command(self._ALWAYS_ENABLE_OFF)
            print("[StarFollower] Keep-alive disabled (e=0 sent to up/down motor).")

    def _send_move(self, speed_cmd: str, steps_cmd: str, direction_cmd: str) -> None:
        """Send the three-stage command sequence: speed → steps → direction."""
        for cmd in (speed_cmd, steps_cmd, direction_cmd):
            if not self.motor.send_command(cmd):
                print(f"[StarFollower] Warning: failed to send command: '{cmd}'")

    def _find_star(self, frame) -> tuple[int, int] | None:
        """
        Locate the brightest star in a grayscale frame.

        Pipeline:
            1. Gaussian blur  – merges star pixels into a smooth blob and
                               suppresses isolated hot pixels / noise.
            2. minMaxLoc      – the single brightest point in the blurred image
                               is the star's centroid.

        Otsu thresholding is intentionally avoided: in a nearly all-black sky
        image the vast majority of pixels are background, so Otsu splits noise
        levels rather than separating star from sky, producing wildly wrong
        centroids.

        Returns (cx, cy) in pixel coordinates, or None if the frame is too dark.
        """
        # Step 1: float background subtraction (removes slow sky gradient).
        frame_f      = frame.astype(np.float32)
        background_f = cv2.GaussianBlur(frame_f, (51, 51), 0)
        residual_f   = frame_f - background_f

        # Step 2: Difference of Gaussians (DoG) — the key point-source filter.
        # A real star (2-5 px wide) gives a LARGE DoG response because the tight
        # blur sees it strongly and the wide blur sees it weakly → big difference.
        # A JPEG compression block artifact (8+ px wide) gives a SMALL DoG
        # response because both blur sizes see it with similar amplitude → near 0.
        tight = cv2.GaussianBlur(residual_f, (5, 5), 1)
        wide  = cv2.GaussianBlur(residual_f, (21, 21), 5)
        dog   = tight - wide   # strong only for point-source-sized features

        # Step 3: find the brightest point in the DoG image.
        _, max_val, _, max_loc = cv2.minMaxLoc(dog)

        # Step 4: sigma test on the DoG image.
        mean, std = cv2.meanStdDev(dog)
        mean = float(mean[0][0])
        std  = float(std[0][0])

        if std < 0.1:
            return None

        # no-star artifact: ~55-68σ  |  real star: ~131-290σ
        # Threshold at 100σ sits cleanly in the gap.
        sigma = (max_val - mean) / std
        if sigma < 80:
            return None

        return max_loc  # (cx, cy)

    def _capture_frame(self, camera_device):
        """
        Capture a single grayscale frame from *camera_device*.

        Mirrors the capture strategy used by CameraRotationFinder and PlateSolver:
            1. HTTP snapshot (MJPG streams)
            2. RTSP capture  (H264 streams)
            3. Direct device access (fallback)

        Returns a grayscale numpy array (rotated 180°), or None on failure.
        """
        if not camera_device.video_device:
            camera_device.video_device = camera_device.get_camera_device_by_type()

        # ---- Strategy 1: HTTP snapshot (MJPG) -------------------------
        if camera_device.camera_type == "MJPG":
            url = f"http://localhost:{camera_device.video_port}/?action=snapshot"
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    arr = np.asarray(bytearray(response.content), dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
                    if frame is not None:
                        return cv2.rotate(frame, cv2.ROTATE_180)
            except Exception as e:
                print(f"[StarFollower] MJPG snapshot failed: {e}")

        # ---- Strategy 2: RTSP capture (H264) --------------------------
        elif camera_device.camera_type == "H264":
            rtsp_url = f"rtsp://localhost:{camera_device.rtsp_port}/cam"
            try:
                cap = cv2.VideoCapture(rtsp_url)
                if cap.isOpened():
                    ret, frame_bgr = cap.read()
                    cap.release()
                    if ret and frame_bgr is not None:
                        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                        return cv2.rotate(gray, cv2.ROTATE_180)
            except Exception as e:
                print(f"[StarFollower] RTSP capture failed: {e}")

        # ---- Strategy 3: Direct device access (fallback) --------------
        if camera_device.video_device:
            cap = None
            try:
                cap = cv2.VideoCapture(camera_device.video_device)
                if cap.isOpened():
                    for _ in range(5):   # flush stale buffered frames
                        cap.read()
                    ret, frame_bgr = cap.read()
                    if ret and frame_bgr is not None:
                        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                        return cv2.rotate(gray, cv2.ROTATE_180)
            except Exception as e:
                print(f"[StarFollower] Direct capture failed: {e}")
            finally:
                if cap:
                    cap.release()

        return None
