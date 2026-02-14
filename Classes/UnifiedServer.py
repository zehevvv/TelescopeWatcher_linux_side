import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sys
import os

# Robust import for MotorControl
try:
    from Classes.MotorsControl import MotorControl
    from Classes.CameraDevice import CameraDevice
    from Classes.CameraRotationFinder import CameraRotationFinder
except (ImportError, ModuleNotFoundError):
    # Fallback if run directly or path issues
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from Classes.MotorsControl import MotorControl
    from Classes.CameraDevice import CameraDevice
    from Classes.CameraRotationFinder import CameraRotationFinder

import subprocess
import os
import glob
import time


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
        elif path.startswith('/cam/check_rotation'):
            self.handle_rotation_check(query)
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
        elif subpath.startswith('/controls'):
            code, msg = camera.get_controls()
            self.respond(code, msg)
        elif subpath.startswith('/reset_controls'):
            code, msg = camera.reset_defaults()
            self.respond(code, msg)
        elif subpath.startswith('/set_control'):
            name = query.get('name', [None])[0]
            value = query.get('value', [None])[0]
            if name and value:
                code, msg = camera.set_control(name, value)
                self.respond(code, msg)
            else:
                self.respond(400, b"Missing 'name' or 'value' parameter")
        else:
            self.respond(404, b"Camera endpoint not found")

    def handle_rotation_check(self, query):
        cam_name = query.get('camera', [None])[0]
        cmd = query.get('cmd', [None])[0]
        
        if not cam_name or not cmd:
            self.respond(400, b"Missing 'camera' or 'cmd'")
            return
            
        target_cam = None
        if cam_name.lower() == 'hd':
            target_cam = self.server.hd_cam
        elif cam_name.lower() == 'uc60':
            target_cam = self.server.uc60_cam
        else:
            self.respond(400, f"Unknown camera '{cam_name}'".encode())
            return
            
        try:
            angle, msg = self.server.rotation_finder.calculate_rotation(target_cam, cmd)
            if angle is not None:
                self.respond(200, f"{angle}".encode())
            else:
                self.respond(500, f"Error: {msg}".encode())
        except Exception as e:
            self.respond(500, f"Server Error: {str(e)}".encode())

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
        
        # self.server.hd_cam = CameraDevice(camera_model="HD USB Camera", camera_type="H264", video_port=5001, rtsp_port=8554)
        self.server.hd_cam = CameraDevice(camera_model="HD USB Camera", camera_type="MJPG", video_port=5001, rtsp_port=8554)
        self.server.uc60_cam = CameraDevice(camera_model="UC60", camera_type="MJPG", video_port=5002)
        
        self.server.rotation_finder = CameraRotationFinder(self.server.motor_control)
        
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
                mediamtx_path = os.path.join(cwd, 'Others/mediamtx/mediamtx')
                
                print(f"Looking for mediamtx at: {mediamtx_path}")
                
                if os.path.exists(mediamtx_path):
                     print(f"Found mediamtx, launching...")
                     # Use the mediamtx directory as the working directory so it finds mediamtx.yml
                     mediamtx_dir = os.path.dirname(mediamtx_path)
                     subprocess.Popen([mediamtx_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=mediamtx_dir)
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
