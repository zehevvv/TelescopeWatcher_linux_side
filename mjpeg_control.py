from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess

class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/start':
            subprocess.Popen(['mjpg_streamer', '-i', 'input_uvc.so', '-o', 'output_http.so -p 8080'])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Stream started")
        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer(('0.0.0.0', 5000), MJPEGHandler)
server.serve_forever()