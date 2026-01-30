from Classes.UnifiedServer import TelescopeServer
import time


# sudo fuser -k 5000/tcp; fuser -k 5001/tcp; fuser -k 5002/tcp; fuser -k 5003/tcp; 

def main():
    server = TelescopeServer(port=5000)
    server.start()
    
    print("Unified Server is running.")
    print("Endpoints:")
    print("  Motors: /motor/read, /motor/write, /motor/stream")
    print("  HD Camera: /cam/hd/start, /cam/hd/stop, /cam/hd/set_brightness, ...")
    print("  UC60 Camera: /cam/uc60/start, /cam/uc60/stop, ...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()

if __name__ == "__main__":
    main()
