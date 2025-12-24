from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import urllib.parse
import os
import glob
import threading
import serial

# sudo pkill -f mjpeg_control.py

class MJPEGHandler(BaseHTTPRequestHandler):
    camera_type = None
    video_device = None
    
    @classmethod
    def set_camera_config(cls, camera_type, video_port):
        """Set camera configuration for this handler class"""
        cls.camera_type = camera_type
        cls.video_device = cls.get_camera_device_by_type(camera_type)
        cls.video_port = video_port

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
                        
                        if format_result.returncode == 0 and 'MJPG' in format_result.stdout:
                            print(f"Found {camera_type} camera at {device}")
                            return device
                except:
                    continue
                    
        except:
            pass
        
        print(f"No {camera_type} camera found")
        return None

    def start_stream(self):
        # Re-detect video device each time we start (in case camera was reconnected)
        current_device = self.get_camera_device_by_type(self.camera_type)
        
        if not current_device:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"No suitable video device found")
            return

        # Update the class variable with current device
        self.video_device = current_device
        print(f"Using video device: {self.video_device}")

        cmd = f"""mjpg_streamer -i "input_uvc.so -d {self.video_device} \
            -r 1920x1080 \
            -f 30 \
            -q 95 \
            -br 0 \
            -co 51 \
            -sh 80 \
            -sa 64 \
            " -o "output_http.so -p {self.video_port} -w /usr/local/share/mjpg-streamer/www" """

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
                subprocess.run(['killall', '-9', 'mjpg_streamer'], check=False)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Stream force stopped")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error stopping stream: {str(e)}".encode())
        
        # Camera Controls - using self.video_device
        elif self.path.startswith('/set_brightness'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            brightness = query_params.get('value', ['0'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'brightness={brightness}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Brightness set to {brightness}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set brightness")
        
        elif self.path.startswith('/set_contrast'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            contrast = query_params.get('value', ['51'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'contrast={contrast}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')  
                self.end_headers()
                self.wfile.write(f"Contrast set to {contrast}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set contrast")
        
        elif self.path.startswith('/set_saturation'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            saturation = query_params.get('value', ['64'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'saturation={saturation}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Saturation set to {saturation}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set saturation")
        
        elif self.path.startswith('/set_sharpness'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sharpness = query_params.get('value', ['80'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'sharpness={sharpness}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Sharpness set to {sharpness}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set sharpness")

        elif self.path.startswith('/set_hue'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            hue = query_params.get('value', ['0'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'hue={hue}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Hue set to {hue}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set hue")

        elif self.path.startswith('/set_gamma'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            gamma = query_params.get('value', ['300'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'gamma={gamma}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Gamma set to {gamma}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set gamma")

        elif self.path.startswith('/set_white_balance_auto'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_wb = query_params.get('value', ['1'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'white_balance_automatic={auto_wb}'], check=True)
                mode = "auto" if auto_wb == "1" else "manual"
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"White balance set to {mode}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set white balance mode")

        elif self.path.startswith('/set_white_balance_temp'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wb_temp = query_params.get('value', ['4600'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First set to manual mode
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'white_balance_automatic=0'], check=True)
                # Then set temperature
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'white_balance_temperature={wb_temp}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"White balance temperature set to {wb_temp}K".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set white balance temperature")

        elif self.path.startswith('/set_power_line_freq'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            freq = query_params.get('value', ['1'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'power_line_frequency={freq}'], check=True)
                freq_text = ["Disabled", "50Hz", "60Hz"][int(freq)]
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Power line frequency set to {freq_text}".encode())
            except (subprocess.CalledProcessError, IndexError):
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set power line frequency")

        elif self.path.startswith('/set_backlight_comp'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            backlight = query_params.get('value', ['0'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'backlight_compensation={backlight}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Backlight compensation set to {backlight}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set backlight compensation")

        elif self.path.startswith('/set_auto_exposure'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_exp = query_params.get('value', ['3'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'auto_exposure={auto_exp}'], check=True)
                exp_modes = {
                    '0': 'Manual',
                    '1': 'Auto',
                    '2': 'Shutter Priority',
                    '3': 'Aperture Priority'
                }
                mode_text = exp_modes.get(auto_exp, f"Mode {auto_exp}")
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Auto exposure set to {mode_text}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set auto exposure")

        elif self.path.startswith('/set_exposure_time'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            exposure_time = query_params.get('value', ['166'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First set to manual mode
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'auto_exposure=1'], check=True)
                # Then set exposure time
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'exposure_time_absolute={exposure_time}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Exposure time set to {exposure_time}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set exposure time")

        elif self.path.startswith('/set_exposure_dynamic'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            dynamic = query_params.get('value', ['0'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'exposure_dynamic_framerate={dynamic}'], check=True)
                mode = "enabled" if dynamic == "1" else "disabled"
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Dynamic framerate {mode}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set dynamic framerate")

        elif self.path.startswith('/set_focus'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            focus = query_params.get('value', ['68'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First disable auto focus
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'focus_automatic_continuous=0'], check=True)
                # Then set focus
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'focus_absolute={focus}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Focus set to {focus}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set focus")

        elif self.path.startswith('/set_auto_focus'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_focus = query_params.get('value', ['1'])[0]
            
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', f'focus_automatic_continuous={auto_focus}'], check=True)
                mode = "auto" if auto_focus == "1" else "manual"
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Auto focus set to {mode}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set auto focus")

        elif self.path == '/get_controls':
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                result = subprocess.run(['v4l2-ctl', '-d', self.video_device, '--list-ctrls'], 
                                       capture_output=True, text=True, check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(result.stdout.encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to get controls")

        elif self.path == '/reset_controls':
            if not self.video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # Reset all controls to default values
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'brightness=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'contrast=51'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'saturation=64'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'hue=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'white_balance_automatic=1'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'gamma=300'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'power_line_frequency=1'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'sharpness=80'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'backlight_compensation=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'auto_exposure=3'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'exposure_time_absolute=166'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'exposure_dynamic_framerate=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'focus_absolute=68'], check=False)
                subprocess.run(['v4l2-ctl', '-d', self.video_device, '-c', 'focus_automatic_continuous=1'], check=False)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"All controls reset to defaults")
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to reset some controls")
        
        else:
            self.send_response(404)
            self.end_headers()


# Create UC60 camera handler class
class UC60Handler(MJPEGHandler):
    pass

# Create Webcam camera handler class  
class WebcamHandler(MJPEGHandler):
    pass

# Configure camera types
# UC60Handler.set_camera_config('UC60', '8080')
UC60Handler.set_camera_config('HD USB Camera', '8080')
WebcamHandler.set_camera_config('Webcam', '8081')

# Start UC60 server on port 5000
uc60_server = HTTPServer(('0.0.0.0', 5000), UC60Handler)
print("UC60 MJPEG Control Server starting on port 5000...")

# Start Webcam server on port 5001
webcam_server = HTTPServer(('0.0.0.0', 5001), WebcamHandler)
print("Webcam MJPEG Control Server starting on port 5001...")

# Run both servers (you'll need threading for this to work properly)
def run_uc60_server():
    uc60_server.serve_forever()

def run_webcam_server():
    webcam_server.serve_forever()

# Start both servers in separate threads
uc60_thread = threading.Thread(target=run_uc60_server)
webcam_thread = threading.Thread(target=run_webcam_server)

uc60_thread.daemon = True
webcam_thread.daemon = True

uc60_thread.start()
webcam_thread.start()

print("Both servers are running...")
print("UC60 camera: http://ip:5000")
print("Webcam camera: http://ip:5001")

# Serial Bridge Configuration
serial_port = '/dev/ttyACM0'
serial_baud = 115200
serial_connection = None

try:
    serial_connection = serial.Serial(
        port=serial_port,
        baudrate=serial_baud,
        dsrdtr=False,
        rtscts=False,
        timeout=1
    )
    # Explicitly disable DTR/RTS to prevent Arduino reset
    serial_connection.dtr = False
    serial_connection.rts = False
    print(f"Serial connection opened on {serial_port}")
except Exception as e:
    print(f"Failed to open serial port {serial_port}: {e}")

class SerialBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global serial_connection
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        
        if parsed_path.path == '/write':
            cmd = query.get('cmd', [None])[0]
            if cmd:
                if serial_connection and serial_connection.is_open:
                    try:
                        print(f"Writing to serial: {cmd}")
                        serial_connection.write(f"{cmd}\n".encode())
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b"OK")
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(f"Serial write error: {str(e)}".encode())
                else:
                    self.send_response(503)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b"Serial connection not open")
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Missing 'cmd' parameter")
                
        elif parsed_path.path == '/read':
            if serial_connection and serial_connection.is_open:
                try:
                    if serial_connection.in_waiting > 0:
                        data = serial_connection.read(serial_connection.in_waiting).decode('utf-8', errors='ignore')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(data.encode())
                    else:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b"") # No data
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Serial read error: {str(e)}".encode())
            else:
                self.send_response(503)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Serial connection not open")
        else:
            self.send_response(404)
            self.end_headers()

# Start Serial Bridge server on port 5002
serial_server = HTTPServer(('0.0.0.0', 5002), SerialBridgeHandler)
print("Serial Bridge Server starting on port 5002...")

def run_serial_server():
    serial_server.serve_forever()

serial_thread = threading.Thread(target=run_serial_server)
serial_thread.daemon = True
serial_thread.start()

print("Serial bridge: http://ip:5002")

# Keep main thread alive
try:
    while True:
        import time
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down servers...")
    uc60_server.shutdown()
    webcam_server.shutdown()