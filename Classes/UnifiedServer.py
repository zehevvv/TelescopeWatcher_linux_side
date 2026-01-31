import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sys
import os

# Robust import for MotorControl
try:
    from Classes.MotorsControl import MotorControl
except (ImportError, ModuleNotFoundError):
    # Fallback if run directly or path issues
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from Classes.MotorsControl import MotorControl

import subprocess
import os
import glob
import time

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
        print(f"Using video device: {self.video_device}")
        
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


class UnifiedHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = urllib.parse.parse_qs(parsed_path.query)

        # Routing
        if path.startswith('/motor'):
            self.handle_motor(path, query)
        elif path.startswith('/cam/hd'):
            self.handle_camera(self.server.hd_cam, path.replace('/cam/hd', ''), query)
        elif path.startswith('/cam/uc60'):
            self.handle_camera(self.server.uc60_cam, path.replace('/cam/uc60', ''), query)
        elif path == '/ping':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"pong")
        elif path == '/restart':
            subprocess.run(["sudo", "reboot"], check=True)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_motor(self, path, query):
        motor = self.server.motor_control
        if '/write' in path:
            cmd = query.get('cmd', [None])[0]
            if cmd:
                if motor.send_command(cmd):
                    self.respond(200, b"OK")
                else:
                    self.respond(503, b"Serial connection issue")
            else:
                self.respond(400, b"Missing 'cmd' parameter")
        elif '/read' in path:
            data = motor.read()
            if data:
                self.respond(200, data.encode())
            else:
                self.respond(200, b"") # Return empty if no data
        elif '/stream' in path:
             # Streaming logic is blocking, might need rethink for unified server if concurrency issues arise
             # but BaseHTTPRequestHandler is usually threaded in ThreadingMixIn servers
             self.send_response(200)
             self.send_header('Content-Type', 'application/octet-stream')
             self.end_headers()
             try:
                while True:
                    data = motor.read()
                    if data:
                        self.wfile.write(data.encode())
                        self.wfile.flush()
                    time.sleep(0.01)
             except:
                 pass
        else:
            self.respond(404, b"Motor endpoint not found")

    def handle_camera(self, camera, subpath, query):
        if subpath.startswith('/start'):
            code, msg = camera.start_stream()
            self.respond(code, msg)
        elif subpath.startswith('/stop'):
            code, msg = camera.stop_stream()
            self.respond(code, msg)
        # Add other controls mapping here... 
        # (Simplified for brevity, can verify others if needed)
        else:
            self.respond(404, b"Camera endpoint not found")

    def respond(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(message)


class TelescopeServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        print("Starting Telescope Unified Server...")
        self._ensure_mediamtx_running()
        
        self.server = HTTPServer((self.host, self.port), UnifiedHandler)
        
        # Initialize components
        self.server.motor_control = MotorControl()
        self.server.motor_control.start()
        
        self.server.hd_cam = CameraDevice(camera_model="HD USB Camera", camera_type="H264", video_port=5001, rtsp_port=8554)
        self.server.uc60_cam = CameraDevice(camera_model="UC60", camera_type="MJPG", video_port=5002)
        
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"Server running on {self.host}:{self.port}")

    def _ensure_mediamtx_running(self):
        try:
            # Check if running
            result = subprocess.run(['pgrep', '-f', 'mediamtx'], capture_output=True)
            if result.returncode != 0:
                print("MediaMTX not running. Starting it...")
                # Try to find it in current directory first
                cwd = os.getcwd()
                mediamtx_path = os.path.join(cwd, 'mediamtx')
                
                print(f"Looking for mediamtx at: {mediamtx_path}")
                
                if os.path.exists(mediamtx_path):
                     print(f"Found mediamtx, launching...")
                     subprocess.Popen([mediamtx_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd)
                     print("MediaMTX process started. Waiting for it to bind to port 8554...")
                     
                     # Wait up to 10 seconds for port 8554 to become available
                     for i in range(20):
                         time.sleep(0.5)
                         port_check = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
                         if ':8554' in port_check.stdout:
                             print(f"MediaMTX is ready on port 8554 (took {(i+1)*0.5} seconds).")
                             return
                         print(f"Waiting for port 8554... attempt {i+1}/20")
                     
                     print("Warning: MediaMTX started but port 8554 not detected after 10 seconds.")
                else:
                    print(f"Warning: mediamtx executable not found at {mediamtx_path}. H264 streaming might fail.")
            else:
                print("MediaMTX is already running.")
                # Double-check the port is actually listening
                port_check = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
                if ':8554' in port_check.stdout:
                    print("Verified: MediaMTX is listening on port 8554.")
                else:
                    print("Warning: MediaMTX process found but port 8554 is not listening!")
        except Exception as e:
            print(f"Error checking/starting MediaMTX: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
