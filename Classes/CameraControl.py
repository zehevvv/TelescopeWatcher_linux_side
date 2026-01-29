from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import urllib.parse
import os
import glob
import threading
import serial
import time
from Classes.Camera import Camera

# sudo pkill -f mjpeg_control.py

class CameraHandler(BaseHTTPRequestHandler):        
    
    @classmethod
    def set_camera_config(cls, camera_model, camera_type, video_port):
        """Set camera configuration for this handler class"""
        cls.camera_model = camera_model        
        cls.video_port = video_port
        cls.camera_type = camera_type
    
    def get_camera_device_by_type(self):
        """Find camera device by model"""
        try:
            # Then check video devices for the specified camera model
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
        # Re-detect video device each time we start (in case camera was reconnected)
        current_device = self.get_camera_device_by_type()
        
        if not current_device:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"No suitable video device found")
            return

        # Update the class variable with current device
        self.video_device = current_device
        print(f"Using video device: {self.video_device}")
        
        cmd = self.__Get_cmd()
        
        if not cmd:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Unsupported camera type")
            return
        
        try:
            subprocess.Popen(cmd, shell=True)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Stream started on {self.video_device}".encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Failed to start stream: {str(e)}".encode())
            
    def __Get_cmd(self):
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
        elif self.camera_type == "H264":
            # Push to local RTSP server (mediamtx) on default port 8554
            cmd = f"""ffmpeg -f v4l2 -input_format h264 -video_size 1920x1080 -framerate 15 \
            -i {self.video_device} -c:v copy -f rtsp rtsp://localhost:8554/cam"""
        else:
            cmd = None
            
        return cmd

    def do_GET(self):
        if self.path.startswith('/start'):
            self.start_stream()
                 
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"pong")
        elif self.path == '/stop':
            try:
                # Force kill all mjpg_streamer processes with multiple methods
                subprocess.run(['pkill', '-9', '-f', 'mjpg_streamer'], check=False)
                subprocess.run(['pkill', '-f', 'mjpg_streamer'], check=False)
                subprocess.run(['pkill', '-9', '-f', 'ffmpeg'], check=False)
                subprocess.run(['pkill', '-f', 'ffmpeg'], check=False)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Stream force stopped")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error stopping stream: {str(e)}".encode())
                
        elif self.path == '/restart':
            subprocess.run(["sudo", "reboot"], check=True)