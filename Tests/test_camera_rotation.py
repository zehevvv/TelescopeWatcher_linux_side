import sys
import os
import time

# Add parent directory to path so we can import Classes
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from Classes.CameraRotationFinder import CameraRotationFinder
    from Classes.MotorsControl import MotorControl
    from Classes.CameraDevice import CameraDevice
except ImportError as e:
    print(f"Error importing classes: {e}")
    sys.exit(1)

def test_rotation_real_hardware():
    print("=== Camera Rotation Test (Hardware) ===")
    
    # 1. Initialize Motor Control
    print("Initializing Motor Control...")
    motor = MotorControl()
    motor.start()
    # Give it a moment to connect
    time.sleep(1) 
    
    # 2. Initialize Camera (Adjust model name as needed for your setup)
    # Common names: "HD USB Camera", "UC60", etc.
    camera_name = "UC60"  # Change this to match your camera model
    print(f"Initializing Camera: {camera_name}...")
    # Note: We need to ensure the camera is streaming or accessible if using 'start_stream' logic,
    # but CameraRotationFinder handles 'snapshot' from URL or direct CV2 access.
    # If using MJPG, the server usually needs to be running to serve the URL.
    # If using Direct Access (fallback in CameraRotationFinder), we don't need the server.
    
    camera = CameraDevice(camera_model=camera_name, camera_type="MJPG", video_port=5002)
    
    # 3. Initialize Rotation Finder
    finder = CameraRotationFinder(motor)
    
    # 4. Define the command to test (e.g., move right for 100ms)
    # You might need to adjust this command specific to your motor controller protocol
    test_command = "v=0\nd=0\nt=1\ns=2500\n" # Example G-code-like or custom command
    print(f"Test Command: {test_command}")
    
    # input("Press Enter to start the test (ensure telescope is clear to move)...")
    
    # 5. Run Calculation
    try:
        debug_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Camera_picture"))
        print(f"Debug images will be saved to: {debug_path}")
        angle, message = finder.calculate_rotation(camera, test_command, debug_path=debug_path)
        
        if angle is not None:
            print(f"\nSUCCESS!")
            print(f"Calculated Rotation Angle: {angle:.2f} degrees")
            print(f"Details: {message}")
        else:
            print(f"\nFAILURE.")
            print(f"Reason: {message}")
            
    except Exception as e:
        print(f"\nAn error occurred during testing: {e}")

if __name__ == "__main__":
    test_rotation_real_hardware()
