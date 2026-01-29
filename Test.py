import threading
from Classes.Camera import Camera
from Classes.MotorsServer import MotorsServer
from Classes.CameraControl import CameraHandler
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

cam = None
motor_server = None
hd_cam_server = None
u60_cam_server = None

def test_camera():
    global cam
    print("Testing Camera class...")
    
    # Try with a camera name that hopefully exists or fails gracefully
    # Based on previous context, 'HD USB Camera' or 'UC60' might be used
    camera_name = "HD USB Camera" 
    
    print(f"Initializing Camera: {camera_name}")
    cam = Camera(camera_name)
    
    if cam.video_device:
        print(f"Camera found at: {cam.video_device}")
        print("Starting stream...")
        cam.start()
        
        # print("Stream running for 5 seconds...")
        # time.sleep(500)
        
        # print("Stopping stream (simulated, as stop() kills the process)...")
        # cam.stop()
        # print("Test complete.")
    else:
        print(f"Camera '{camera_name}' not found. Please ensure the camera is connected and the name matches.")
        
def test_camera_server():
    global hd_cam_server, u60_cam_server
    print("Testing CameraHandler class...")
    
    class HD_CAM_Handler(CameraHandler):
        pass
            
    HD_CAM_Handler.set_camera_config(camera_model= "HD USB Camera", camera_type='H264', video_port=5005)
    hd_cam_server = HTTPServer(('0.0.0.0', 5001), HD_CAM_Handler)
    
    hd_cam_thread = threading.Thread(target=hd_cam_server.serve_forever)
    hd_cam_thread.daemon = True
    hd_cam_thread.start()
    
    class U60_Handler(CameraHandler):
        pass
            
    U60_Handler.set_camera_config(camera_model= "UC60", camera_type='MJPG', video_port=5006)
    u60_cam_server = HTTPServer(('0.0.0.0', 5002), U60_Handler)
    
    u60_cam_thread = threading.Thread(target=u60_cam_server.serve_forever)
    u60_cam_thread.daemon = True
    u60_cam_thread.start()
    

def test_motors_server():
    global motor_server
    print("Testing MotorsServer class...")
    
    motor_server = MotorsServer('0.0.0.0', 5003)
    motor_server.start_server()
    
    # print("MotorsServer started. Running for 5 seconds...")    
    
    # time.sleep(5000)
    
    # motor_server.stop_server()

if __name__ == "__main__":
    # test_camera()
    
    try:
        test_camera_server()
        test_motors_server()
        
        while True:        
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down servers...")
        if motor_server:
            motor_server.stop_server()
        if hd_cam_server:
            hd_cam_server.shutdown()
        print("Exited cleanly.")