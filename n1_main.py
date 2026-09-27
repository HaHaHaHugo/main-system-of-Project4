import socket
import struct
import threading
import sys
import time
import numpy as np
import cv2
from pubsub import pub
# เพิ่ม TOPIC_PID_OUTPUT เข้ามาในการ Import จาก event_bus
from event_bus import TOPIC_RAW_FRAME, TOPIC_RPM_DATA, TOPIC_CMD_SEND, TOPIC_PID_OUTPUT

PI_IP = '192.168.137.209'
CMD_PORT = 5000
CAM_PORT = 5001

class MainNode:
    def __init__(self):
        self.running = True
        self.cmd_socket = None
        
        # Subscribe ฟังคำสั่งขับเคลื่อนแบบ Manual จาก UI
        pub.subscribe(self.send_command, TOPIC_CMD_SEND)
        
        # Subscribe ฟังคำสั่ง PWM ควบคุมมอเตอร์ 4 ล้อ จาก PID Node
        pub.subscribe(self.send_pid_to_hardware, TOPIC_PID_OUTPUT)

        # เริ่ม Thread สำหรับรับส่งข้อมูล Socket
        self.t_cmd = threading.Thread(target=self.cmd_and_rpm_thread, daemon=True)
        self.t_cam = threading.Thread(target=self.video_receive_thread, daemon=True)
        
        self.connect_sockets()
        self.t_cmd.start()
        self.t_cam.start()
        print("[Node 1 Main] Network Sockets Connected & Threading Started")

    def connect_sockets(self):
        try:
            self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.cmd_socket.connect((PI_IP, CMD_PORT))
            print(f"[Node 1 Main] Control System connected (Port {CMD_PORT})")
        except Exception as e:
            self.cmd_socket = None
            print(f"[Node 1 Main Warning] Control System not ready (Port {CMD_PORT}): {e}")

    def cmd_and_rpm_thread(self):
        buffer = ""
        while self.running:
            if self.cmd_socket:
                try:
                    data = self.cmd_socket.recv(1024).decode('utf-8', errors='ignore')
                    if not data:
                        break
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        parts = line.split(',')
                        
                        if len(parts) == 5:
                            try:
                                # 1. รับค่า RPM ดิบจากบอร์ด
                                raw_m1 = float(parts[0])
                                raw_m2 = float(parts[1])
                                raw_m3 = float(parts[2])
                                raw_m4 = float(parts[3])
                                
                                rpm_dirs = [1, -1, 1, -1] 
                                
                                # 3. นำค่าดิบมาคูณตัวปรับทิศทาง
                                m1 = raw_m1 * rpm_dirs[0]
                                m2 = raw_m2 * rpm_dirs[1]
                                m3 = raw_m3 * rpm_dirs[2]
                                m4 = raw_m4 * rpm_dirs[3]
                                
                                # Publish ค่าที่ถูกปรับทิศทางแล้วไปยัง PID Node และ UI Node
                                pub.sendMessage(TOPIC_RPM_DATA, rpm_list=[m1, m2, m3, m4])
                            except ValueError:
                                pass
                except Exception:
                    break
            time.sleep(0.005)

    def video_receive_thread(self):
        try:
            cam_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cam_socket.connect((PI_IP, CAM_PORT))
            print(f"[Node 1 Main] Connected to Video Stream (Port {CAM_PORT})")

            data = b""
            payload_size = struct.calcsize(">L")

            while self.running:
                while len(data) < payload_size:
                    packet = cam_socket.recv(4096)
                    if not packet:
                        return
                    data += packet

                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack(">L", packed_msg_size)[0]

                while len(data) < msg_size:
                    data += cam_socket.recv(4096)

                frame_data = data[:msg_size]
                data = data[msg_size:]

                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    # Publish ภาพดิบส่งต่อไปยัง Vision Node และ UI Node
                    pub.sendMessage(TOPIC_RAW_FRAME, frame=frame)

        except Exception as e:
            print(f"[Node 1 Main Camera Error] {e}")
        finally:
            if 'cam_socket' in locals():
                cam_socket.close()

    def send_command(self, cmd):
        if self.cmd_socket:
            try:
                self.cmd_socket.sendall(cmd.encode('utf-8'))
            except Exception as e:
                print(f"[Node 1 Main Send Error] {e}")

    # ฟังก์ชันใหม่สำหรับรับค่า PID (PWM) แล้วส่งไปยัง Hardware
    def send_pid_to_hardware(self, pwm):
        if self.cmd_socket:
            try:
                # แปลงค่า [pwm1, pwm2, pwm3, pwm4] เป็น String ส่งเข้า Socket ไปหาบอร์ด
                cmd_str = f"PWM,{pwm[0]},{pwm[1]},{pwm[2]},{pwm[3]}\n"
                self.cmd_socket.sendall(cmd_str.encode('utf-8'))
            except Exception as e:
                print(f"[Node 1 Main PID Send Error] {e}")

    def stop(self):
        self.running = False
        if self.cmd_socket:
            self.cmd_socket.close()