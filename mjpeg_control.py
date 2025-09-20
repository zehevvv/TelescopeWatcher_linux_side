from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import urllib.parse
import os
import glob

class MJPEGHandler(BaseHTTPRequestHandler):
    def get_available_video_device(self):
        """Find the first available video capture device"""
        video_devices = glob.glob('/dev/video*')
        for device in sorted(video_devices):
            try:
                # Check if device supports video capture
                result = subprocess.run(['v4l2-ctl', '-d', device, '--list-formats'], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0 and 'MJPG' in result.stdout:
                    return device
            except:
                continue
        return None

    def do_GET(self):
        if self.path == '/start':
            print("Starting MJPEG Streamer...")
            
            # Find available video device
            video_device = self.get_available_video_device()
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
                " -o "output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www" """

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
        elif self.path.startswith('/set_brightness'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            brightness = query_params.get('value', ['60'])[0]
            
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
        elif self.path.startswith('/set_contrast'):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            contrast = query_params.get('value', ['20'])[0]
            
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
        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer(('0.0.0.0', 5000), MJPEGHandler)
server.serve_forever()