import threading
import time
import serial

class MotorControl:
    def __init__(self):
        # Serial Bridge Configuration
        serial_port = '/dev/ttyACM0'
        serial_baud = 115200
        self.__serial_connection = None
        self.__serial_buffer = bytearray()
        self.__serial_buffer_lock = threading.Lock()

        try:
            self.__serial_connection = serial.Serial(
                port=serial_port,
                baudrate=serial_baud,
                dsrdtr=False,
                rtscts=False,
                timeout=1
            )
            # Explicitly disable DTR/RTS to prevent Arduino reset
            self.__serial_connection.dtr = False
            self.__serial_connection.rts = False
            print(f"Serial connection opened on {serial_port}")
        except Exception as e:
            print(f"Failed to open serial port {serial_port}: {e}")
            
    def __serial_read_worker(self):
        """Background thread to continuously read from serial port to buffer"""
        while True:
            if self.__serial_connection and self.__serial_connection.is_open:
                try:
                    if self.__serial_connection.in_waiting > 0:
                        data = self.__serial_connection.read(self.__serial_connection.in_waiting)
                    
                    # Decode bytes to string to interpret control characters like \n
                    print(f"////// Reading from serial:\n {data.decode('utf-8', errors='replace')} \\\\\\\\\\\\")
                    
                    if data:
                        with self.__serial_buffer_lock:
                            self.__serial_buffer.extend(data)
                except Exception as e:
                    print(f"Serial background read error: {e}")
                    time.sleep(1)
            time.sleep(0.01)

    def start(self):        
        # Start the serial reader thread
        serial_reader_thread = threading.Thread(target=self.__serial_read_worker)
        serial_reader_thread.daemon = True
        serial_reader_thread.start()
        
    def send_command(self, command):
        if command:
            if self.__serial_connection and self.__serial_connection.is_open:
                try:
                    print(f"Writing to serial: {command}")
                    self.__serial_connection.write(f"{command}\n".encode())
                    return True
                except Exception as e:
                    print(f"Serial write error: {e}")
                    return False
        return False
    
    def read(self):
        with self.__serial_buffer_lock:
            if len(self.__serial_buffer) > 0:
                # Decode bytes to string (handling errors)
                response_data = self.__serial_buffer.decode('utf-8', errors='ignore')
                # Clear the buffer
                # print(f"##### Sending to HTTP client:\n {response_data} #####")
                self.__serial_buffer.clear()
                
                return response_data
        return None
    
    