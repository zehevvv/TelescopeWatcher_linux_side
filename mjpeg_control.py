from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import urllib.parse
import os
import glob

# sudo pkill -f mjpeg_control.py

class MJPEGHandler(BaseHTTPRequestHandler):
    def get_camera_device(self, camera_type):
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
                            return device
                except:
                    continue
                    
        except:
            pass
        
        return None    
    
    def start_stream(self, video_device, port):
        if not video_device:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"No suitable video device found")
            return
        
        print(f"Using video device: {video_device}")
        
        cmd = f"""mjpg_streamer -i "input_uvc.so -d {video_device} \
            -r 1280x720 \
            -f 5 \
            -q 90 \
            -br 60 \
            -co 20 \
            -sh 50 \
            -sa 0 \
            " -o "output_http.so -p {port} -w /usr/local/share/mjpg-streamer/www" """

        try:
            subprocess.Popen(cmd, shell=True)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Stream started on {video_device}".encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Failed to start stream: {str(e)}".encode())

    def do_GET(self):
        if self.path == '/start_main_cam':
            print("Starting main MJPEG Streamer...")
            
            # Find available video device
            video_device = self.get_camera_device('UC60')
            self.start_stream(video_device, 8080)

        elif self.path == '/start_secondary_cam':
            print("Starting secondary MJPEG Streamer...")
            
            # Find available video device
            video_device = self.get_camera_device('Webcam')
            self.start_stream(video_device, 8081)
                
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"pong")
        elif self.path == '/stop':
            try:
                # Kill all mjpg_streamer processes
                subprocess.run(['pkill', '-f', 'mjpg_streamer'], check=False)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Stream stopped")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error stopping stream: {str(e)}".encode())
        
        # Brightness Control (range: -64 to 64)
        elif self.path.startswith('/set_brightness'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            brightness = query_params.get('value', ['0'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'brightness={brightness}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Brightness set to {brightness}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set brightness")
        
        # Contrast Control (range: 0 to 100)
        elif self.path.startswith('/set_contrast'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            contrast = query_params.get('value', ['51'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'contrast={contrast}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')  
                self.end_headers()
                self.wfile.write(f"Contrast set to {contrast}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set contrast")
        
        # Saturation Control (range: 0 to 100)
        elif self.path.startswith('/set_saturation'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            saturation = query_params.get('value', ['64'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'saturation={saturation}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Saturation set to {saturation}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set saturation")
        
        # Sharpness Control (range: 0 to 100)
        elif self.path.startswith('/set_sharpness'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sharpness = query_params.get('value', ['80'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'sharpness={sharpness}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Sharpness set to {sharpness}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set sharpness")
        
        # Hue Control (range: -180 to 180)
        elif self.path.startswith('/set_hue'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            hue = query_params.get('value', ['0'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'hue={hue}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Hue set to {hue}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set hue")
        
        # Gamma Control (range: 100 to 500)
        elif self.path.startswith('/set_gamma'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            gamma = query_params.get('value', ['300'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'gamma={gamma}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Gamma set to {gamma}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set gamma")
        
        # White Balance Automatic (0=manual, 1=auto)
        elif self.path.startswith('/set_white_balance_auto'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_wb = query_params.get('value', ['1'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'white_balance_automatic={auto_wb}'], check=True)
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
        
        # White Balance Temperature (range: 2800 to 6500, only when manual mode)
        elif self.path.startswith('/set_white_balance_temp'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wb_temp = query_params.get('value', ['4600'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First set to manual mode
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'white_balance_automatic=0'], check=True)
                # Then set temperature
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'white_balance_temperature={wb_temp}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"White balance temperature set to {wb_temp}K".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set white balance temperature")
        
        # Power Line Frequency (0=Disabled, 1=50Hz, 2=60Hz)
        elif self.path.startswith('/set_power_line_freq'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            freq = query_params.get('value', ['1'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'power_line_frequency={freq}'], check=True)
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
        
        # Backlight Compensation (range: 0 to 2)
        elif self.path.startswith('/set_backlight_comp'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            backlight = query_params.get('value', ['0'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'backlight_compensation={backlight}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Backlight compensation set to {backlight}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set backlight compensation")
        
        # Auto Exposure (0=Manual, 1=Auto, 3=Shutter Priority, etc.)
        elif self.path.startswith('/set_auto_exposure'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_exp = query_params.get('value', ['3'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'auto_exposure={auto_exp}'], check=True)
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
        
        # Exposure Time Absolute (range: 50 to 10000, only when manual exposure)
        elif self.path.startswith('/set_exposure_time'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            exposure_time = query_params.get('value', ['166'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First set to manual mode
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'auto_exposure=1'], check=True)
                # Then set exposure time
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'exposure_time_absolute={exposure_time}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Exposure time set to {exposure_time}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set exposure time")
        
        # Exposure Dynamic Framerate (0=off, 1=on)
        elif self.path.startswith('/set_exposure_dynamic'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            dynamic = query_params.get('value', ['0'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'exposure_dynamic_framerate={dynamic}'], check=True)
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
        
        # Focus Absolute (range: 0 to 1023, only when manual focus)
        elif self.path.startswith('/set_focus'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            focus = query_params.get('value', ['68'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # First disable auto focus
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'focus_automatic_continuous=0'], check=True)
                # Then set focus
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'focus_absolute={focus}'], check=True)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Focus set to {focus}".encode())
            except subprocess.CalledProcessError:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"Failed to set focus")
        
        # Focus Automatic Continuous (0=manual, 1=auto)
        elif self.path.startswith('/set_auto_focus'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auto_focus = query_params.get('value', ['1'])[0]
            
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', f'focus_automatic_continuous={auto_focus}'], check=True)
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
        
        # Get all available controls
        elif self.path == '/get_controls':
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                result = subprocess.run(['v4l2-ctl', '-d', video_device, '--list-ctrls'], 
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
        
        # Reset all controls to defaults
        elif self.path == '/reset_controls':
            video_device = self.get_available_video_device()
            if not video_device:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No video device found")
                return
            
            try:
                # Reset all controls to default values
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'brightness=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'contrast=51'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'saturation=64'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'hue=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'white_balance_automatic=1'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'gamma=300'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'power_line_frequency=1'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'sharpness=80'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'backlight_compensation=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'auto_exposure=3'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'exposure_time_absolute=166'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'exposure_dynamic_framerate=0'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'focus_absolute=68'], check=False)
                subprocess.run(['v4l2-ctl', '-d', video_device, '-c', 'focus_automatic_continuous=1'], check=False)
                
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

server = HTTPServer(('0.0.0.0', 5000), MJPEGHandler)
print("MJPEG Control Server starting on port 5000...")
server.serve_forever()