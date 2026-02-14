import subprocess
import glob
import threading
import time
import os
import signal
import re
import json

class CameraDevice:
    def __init__(self, camera_model, camera_type, video_port, rtsp_port=8554):
        self.camera_model = camera_model
        self.camera_type = camera_type
        self.video_port = video_port
        self.rtsp_port = rtsp_port
        self.video_device = None
        
    def get_camera_device_by_type(self):
        """Find camera device by model"""
        try:
            video_devices = glob.glob('/dev/video*')
            for device in sorted(video_devices):
                try:
                    info_result = subprocess.run(['v4l2-ctl', '-d', device, '--info'], 
                                            capture_output=True, text=True, check=False)
                    
                    if info_result.returncode == 0 and self.camera_model in info_result.stdout:
                        format_result = subprocess.run(['v4l2-ctl', '-d', device, '--list-formats'], 
                                                    capture_output=True, text=True, check=False)
                        
                        if format_result.returncode == 0 and self.camera_type in format_result.stdout:
                            print(f"Found {self.camera_model} camera at {device}")
                            return device
                except:
                    continue
        except:
            pass
        print(f"No {self.camera_model} camera found")
        return None

    def start_stream(self):
        current_device = self.get_camera_device_by_type()
        
        if not current_device:
            return 500, b"No suitable video device found"

        self.video_device = current_device
        print(f"Using video device: {self.video_device}, starting stream with type {self.camera_type}")
        
        if self.camera_type == "MJPG":
            cmd = f"""mjpg_streamer -i "input_uvc.so -d {self.video_device} \
                -r 1920x1080 \
                -f 30 \
                -q 95 \
                -br 0 \
                -co 51 \
                -sh 80 \
                -sa 64 \
                " -o "output_http.so -p {self.video_port} -w /usr/local/share/mjpg-streamer/www" """
                
            print(f"Starting MJPG Stream with command: {cmd}")
        elif self.camera_type == "H264":
            cmd = f"""ffmpeg -f v4l2 -input_format h264 -video_size 1920x1080 -framerate 15 \
            -i {self.video_device} -c:v copy -f rtsp rtsp://localhost:{self.rtsp_port}/cam"""
        else:
            return 500, b"Unsupported camera type"
        
        try:
            subprocess.Popen(cmd, shell=True)
            return 200, f"Stream started on {self.video_device}".encode()
        except Exception as e:
            return 500, f"Failed to start stream: {str(e)}".encode()

    def stop_stream(self):
        try:
             # Stop specific to camera type if needed, or generic kill
            if self.camera_type == "MJPG":
                subprocess.run(['pkill', '-f', 'mjpg_streamer'], check=False)
            elif self.camera_type == "H264":
                subprocess.run(['pkill', '-f', 'ffmpeg'], check=False)
            return 200, b"Stream stopped"
        except Exception as e:
            return 500, f"Error stopping stream: {str(e)}".encode()

    def _get_device_controls_list(self):
        if not self.video_device:
            self.video_device = self.get_camera_device_by_type()
            if not self.video_device:
                return None
        
        try:
            result = subprocess.run(['v4l2-ctl', '-d', self.video_device, '-l'], 
                                   capture_output=True, text=True, check=True)
            controls = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line: continue
                parts = line.split(':', 1)
                if len(parts) != 2: continue
                
                info_part = parts[0].strip()
                values_part = parts[1].strip()
                
                name_match = re.match(r'^(\w+)\s+0x[0-9a-fA-F]+\s+\(([\w\s]+)\)', info_part)
                if not name_match: continue
                
                name = name_match.group(1)
                ctrl_type = name_match.group(2)
                
                ctrl_data = {"name": name, "type": ctrl_type}
                for pair in values_part.split():
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        if v.replace('-', '', 1).isdigit():
                            ctrl_data[k] = int(v)
                        else:
                            ctrl_data[k] = v
                controls.append(ctrl_data)
            return controls
        except Exception:
            return None

    def get_controls(self):
        controls = self._get_device_controls_list()
        if controls is None:
            return 500, b"Error getting controls or no device found"
        return 200, json.dumps(controls).encode()

    def reset_defaults(self):
        controls = self._get_device_controls_list()
        if controls is None:
            return 500, b"Error getting controls or no device found"
        
        count = 0
        errors = 0
        for ctrl in controls:
            if 'default' in ctrl:
                try:
                    subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f"{ctrl['name']}={ctrl['default']}"], check=True)
                    count += 1
                except:
                    errors += 1
        
        return 200, f"Reset {count} controls to default. {errors} errors.".encode()

    def set_control(self, control_name, value):
        if not self.video_device:
             # Try to find it if not already found (e.g. if set_control called before start)
             self.video_device = self.get_camera_device_by_type()
             if not self.video_device:
                return 500, b"No video device found"

        try:
            subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'{control_name}={value}'], check=True)
            return 200, f"{control_name} set to {value}".encode()
        except subprocess.CalledProcessError:
            return 500, f"Failed to set {control_name}".encode()