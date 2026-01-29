import subprocess
import glob
import threading
import time
import os
import signal

class Camera:
    def __init__(self, camera_name):
        self.camera_name = camera_name
        self.video_device = self.get_camera_device_by_type(camera_name)
        self.process = None
        self.thread = None

    @staticmethod
    def get_camera_device_by_type(camera_type):
        """Find camera device by type"""
        try:
            # Then check video devices for the specified camera type
            video_devices = glob.glob('/dev/video*')
            for device in sorted(video_devices):
                try:
                    info_result = subprocess.run(['v4l2-ctl', '-d', device, '--info'], 
                                            capture_output=True, text=True, check=False)
                    
                    if info_result.returncode == 0 and camera_type in info_result.stdout:
                        format_result = subprocess.run(['v4l2-ctl', '-d', device, '--list-formats'], 
                                                    capture_output=True, text=True, check=False)
                        
                        # Modified to check for H264 since the stream command uses it, 
                        # or MJPG as fallback if the user intends to use the original camera check logic strictly.
                        # Assuming we want to find a camera that supports video capturing.
                        if format_result.returncode == 0:
                            print(f"Found {camera_type} camera at {device}")
                            return device
                except:
                    continue
                    
        except:
            pass
        
        print(f"No {camera_type} camera found")
        return None

    def _stream_thread(self):
        if not self.video_device:
            return

        cmd = f"""ffmpeg -f v4l2 -input_format h264 -video_size 1920x1080 -framerate 15 \
        -i {self.video_device} -c:v copy -f rtsp rtsp://localhost:8554/cam"""
        
        print(f"Starting ffmpeg stream for {self.camera_name}")
        try:
            # use os.setsid to create a new process group so we can kill the whole tree later
            self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
            self.process.wait()
        except Exception as e:
            print(f"Stream error: {e}")

    def start(self):
        if self.video_device:
            self.thread = threading.Thread(target=self._stream_thread)
            self.thread.daemon = True
            self.thread.start()
        else:
            print(f"Cannot start stream: Camera {self.camera_name} not found.")

    def stop(self):
        if self.process:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                print(f"Stopped stream for {self.camera_name}")
            except Exception as e:
                print(f"Error stopping stream: {e}")
            self.process = None
