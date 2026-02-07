import cv2
import numpy as np
import time
import requests
import threading
import os

class CameraRotationFinder:
    def __init__(self, motor_control):
        self.motor = motor_control

    def calculate_rotation(self, camera_device, move_command, debug_path=None):
        """
        Takes a picture, moves telescope, takes another picture, 
        calculates rotation angle of the shift vector.
        
        Returns: (angle_degrees, message)
        """
        print(f"Starting Rotation Check on {camera_device.camera_model} with command '{move_command}'")
        
        # 1. Capture Image 1
        img1 = self._capture_frame(camera_device)
        if img1 is None:
            return None, "Failed to capture first image (Check if camera is connected)"
        print("Captured Image 1")

        if debug_path:
            try:
                if not os.path.exists(debug_path):
                    os.makedirs(debug_path)
                cv2.imwrite(os.path.join(debug_path, "debug_img1.jpg"), img1)
                print(f"Saved debug_img1.jpg to {debug_path}")
            except Exception as e:
                print(f"Failed to save debug image 1: {e}")

        # 2. Move Telescope
        if not self.motor.send_command(move_command):
             return None, "Failed to send motor command"
        print(f"Sent command: {move_command}")

        # 3. Wait 2 seconds (as requested)
        time.sleep(5)

        # 4. Capture Image 2
        img2 = self._capture_frame(camera_device)
        if img2 is None:
            return None, "Failed to capture second image"
        print("Captured Image 2")

        if debug_path:
            try:
                cv2.imwrite(os.path.join(debug_path, "debug_img2.jpg"), img2)
                print(f"Saved debug_img2.jpg to {debug_path}")
            except Exception as e:
                print(f"Failed to save debug image 2: {e}")

        # 5. Calculate Angle
        try:
            angle_deg, shift_x, shift_y = self._compute_shift_angle(img1, img2)
            print(f"Calculated Angle: {angle_deg:.2f} (Shift: {shift_x:.2f}, {shift_y:.2f})")
            return angle_deg, f"Shift: {shift_x:.2f}, {shift_y:.2f}"
        except Exception as e:
            print(f"Calculation Error: {e}")
            return None, f"Calculation error: {str(e)}"

    def _capture_frame(self, camera_device):
        """
        Tries to capture a single frame from the camera.
        """
        frame = None
        
        # Ensure we know the device
        if not camera_device.video_device:
            camera_device.video_device = camera_device.get_camera_device_by_type()
            
        # Strategy 1: HTTP Snapshot (for MJPG)
        if camera_device.camera_type == "MJPG":
            url = f"http://localhost:{camera_device.video_port}/?action=snapshot"
            try:
                # Short timeout
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
                    frame = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
                    if frame is not None:
                        return frame
            except Exception as e:
                print(f"Snapshot failed: {e}")
                
        # Strategy 2: RTSP Capture (for H264)
        elif camera_device.camera_type == "H264":
            rtsp_url = f"rtsp://localhost:{camera_device.rtsp_port}/cam"
            try:
                cap = cv2.VideoCapture(rtsp_url)
                if cap.isOpened():
                    ret, frame_read = cap.read()
                    cap.release()
                    if ret and frame_read is not None:
                        return cv2.cvtColor(frame_read, cv2.COLOR_BGR2GRAY)
            except Exception as e:
                print(f"RTSP Capture failed: {e}")
        
        # Strategy 3: Direct Device Access (Fallback)
        # Only try if we have a device path
        if camera_device.video_device:
            try:
                print(f"Attempting direct capture from {camera_device.video_device}")
                cap = cv2.VideoCapture(camera_device.video_device)
                if cap.isOpened():
                    # Read a few frames to settle sensor
                    for _ in range(5):
                        cap.read()
                    ret, frame_read = cap.read()
                    cap.release()
                    if ret and frame_read is not None:
                         return cv2.cvtColor(frame_read, cv2.COLOR_BGR2GRAY)
            except Exception as e:
                 print(f"Direct capture failed: {e}")
             
        return None

    def _compute_shift_angle(self, img1, img2):
        # Use ORB to find keypoints and match
        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)
        
        if des1 is None or des2 is None or len(des1) < 5 or len(des2) < 5:
             raise Exception("Not enough features found (bad light or focus?)")

        # BFMatcher with Hamming distance
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        
        # Sort matches by distance
        matches = sorted(matches, key = lambda x:x.distance)
        
        # Take top matches (or all if few)
        if len(matches) == 0:
            raise Exception("No matches found")
            
        good_matches = matches[:min(50, len(matches))]
        
        if len(good_matches) < 3:
             raise Exception("Not enough good matches")

        # Extract location of good matches
        pts1 = np.float32([ kp1[m.queryIdx].pt for m in good_matches ])
        pts2 = np.float32([ kp2[m.trainIdx].pt for m in good_matches ])
        
        # Calculate shift (pts2 - pts1)
        shifts = pts2 - pts1
        
        # Median shift
        dx = np.median(shifts[:, 0])
        dy = np.median(shifts[:, 1])
        
        magnitude = np.sqrt(dx**2 + dy**2)
        if magnitude < 1.0:
            raise Exception("Movement too small to determine angle")
        
        # Calculate angle
        # atan2(y, x) returns radians
        angle_rad = np.arctan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        
        return angle_deg, dx, dy
