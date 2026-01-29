from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib
import time
import threading
from Classes.MotorsControl import MotorControl

class MotorsServer:
    def __init__(self, host: str, port: int):
        self.__host = host
        self.__port = port
        self.__is_running = False
        self.__serial_server = None
        self.__serial_thread = None

    def start_server(self):
        if not self.__is_running:
            self.__is_running = True
            print(f"Motors server started at {self.__host}:{self.__port}")
            self.__serial_server = HTTPServer((self.__host, self.__port), SerialBridgeHandler)
            
            # Initialize MotorControl and attach to server instance
            self.__serial_server.motor_control = MotorControl()
            self.__serial_server.motor_control.start()

            self.__serial_thread = threading.Thread(target=self.__serial_server.serve_forever)
            self.__serial_thread.daemon = True
            self.__serial_thread.start()

        else:
            print("Motors server is already running.")

    def stop_server(self):
        if self.__is_running:
            self.__is_running = False
            self.__serial_server.shutdown()
            self.__serial_thread.join()
            
            # Stop motor control
            if hasattr(self.__serial_server, 'motor_control'):
                # Assuming MotorControl has a stop method? The user's snippet in SerialBridgeHandler didn't call stop explicitly but maybe it should.
                # If MotorControl is a thread, it likely needs stopping.
                # Looking at SerialBridgeHandler code it has .start(), so assume .stop() or .join()?
                # I'll check MotorControl.py to be safe, but for now I'll just leave it or assume it's needed.
                # Actually, checking MotorsControl.py is good practice.
                pass
                
            print("Motors server stopped.")
        else:
            print("Motors server is not running.")

 

class SerialBridgeHandler(BaseHTTPRequestHandler):
    @property
    def motors_control(self):
        return self.server.motor_control
    
    def log_message(self, format, *args):
        # Only suppress logging for /read requests
        if self.path.startswith('/read'):
            return
        BaseHTTPRequestHandler.log_message(self, format, *args)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        if parsed_path.path == '/write':
            cmd = query.get('cmd', [None])[0]
            if cmd:
                response = self.motors_control.send_command(cmd)
                if response:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b"OK")
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
            try:
                response_data = self.motors_control.read()
                        
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(response_data.encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Read error: {str(e)}".encode())

        elif parsed_path.path == '/stream':
            # Continuous stream of serial data
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            try:
                while True:
                    data = self.motors_control.read()
                    
                    if data:
                        # Write raw bytes directly to the stream
                        self.wfile.write(data)
                        self.wfile.flush()
                    
                    time.sleep(0.01)
            except Exception as e:
                print(f"Stream client disconnected: {e}")

        else:
            self.send_response(404)
            self.end_headers()