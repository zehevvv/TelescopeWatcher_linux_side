from Classes.UnifiedServer import TelescopeServer
import time
import sys

# Force unbuffered output for logging
# sys.stdout = sys.stderr = open('/home/israelf/Desktop/TelescopeWatcher_linux_side/myscript.log', 'a', buffering=1)

# sudo fuser -k 5000/tcp; fuser -k 5001/tcp; fuser -k 5002/tcp; fuser -k 5003/tcp; 

def main():
    print(f"========== Starting Telescope Server at {time.strftime('%Y-%m-%d %H:%M:%S')} ==========", flush=True)
    server = TelescopeServer(port=5000)
    server.start()
    
    print("Unified Server is running.", flush=True)
    print("Endpoints:", flush=True)
    print("  Motors: /motor/read, /motor/write, /motor/stream", flush=True)
    print("  HD Camera: /cam/hd/start, /cam/hd/stop, /cam/hd/set_brightness, ...", flush=True)
    print("  UC60 Camera: /cam/uc60/start, /cam/uc60/stop, ...", flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...", flush=True)
        server.stop() 

if __name__ == "__main__":
    main()
