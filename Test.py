from Classes.Camera import Camera
from Classes.MotorsServer import MotorsServer
import time

cam = None
motor_server = None

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

def test_motors_server():
    global motor_server
    print("Testing MotorsServer class...")
    
    motor_server = MotorsServer('0.0.0.0', 5002)
    motor_server.start_server()
    
    # print("MotorsServer started. Running for 5 seconds...")    
    
    # time.sleep(5000)
    
    # motor_server.stop_server()

if __name__ == "__main__":
    test_camera()
    test_motors_server()
    
    while True:        
        time.sleep(1)