import sys
import cv2
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QGridLayout, QLineEdit
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer
from pubsub import pub
from event_bus import TOPIC_PROCESSED_FRAME, TOPIC_RPM_DATA, TOPIC_RAW_RPM_DATA, TOPIC_CMD_SEND, TOPIC_START_RECORD, TOPIC_EVM_RESULT

class Communicate(QObject):
    frame_signal = pyqtSignal(object)
    rpm_signal = pyqtSignal(list)
    raw_rpm_signal = pyqtSignal(list)
    evm_result_signal = pyqtSignal(list)

class RobotDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Control Center & Gas Analyzer")
        self.resize(1200, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.comm = Communicate()
        self.comm.frame_signal.connect(self.update_image)
        self.comm.rpm_signal.connect(self.update_graph_adj)
        self.comm.raw_rpm_signal.connect(self.update_graph_raw)
        self.comm.evm_result_signal.connect(self.start_heatmap_playback)

        pub.subscribe(self.on_frame, TOPIC_PROCESSED_FRAME)
        pub.subscribe(self.on_rpm, TOPIC_RPM_DATA)
        pub.subscribe(self.on_raw_rpm, TOPIC_RAW_RPM_DATA)
        pub.subscribe(self.on_evm_result, TOPIC_EVM_RESULT)

        self.evm_frames = []
        self.evm_frame_index = 0
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.next_heatmap_frame)

        self.init_ui()

    def init_ui(self):
        main_layout = QGridLayout()
        main_layout.setSpacing(10)

        # ---------------------------------------------------------
        # Row 0: Camera 1 (มองทาง) | Camera 2 (กล้องก๊าซ)
        # ---------------------------------------------------------
        # Camera 1 (Left)
        cam1_layout = QVBoxLayout()
        self.cam1_label = QLabel("Camera 1 (กล้องมองทางของหุ่น)")
        self.cam1_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam1_label.setStyleSheet("background-color: black; color: white; border: 2px solid black;")
        self.cam1_label.setFixedSize(500, 350)
        cam1_layout.addWidget(self.cam1_label)
        main_layout.addLayout(cam1_layout, 0, 0)

        # Camera 2 (Right) - ใช้สตรีมเดียวกับ Cam1 ชั่วคราว
        cam2_layout = QVBoxLayout()
        self.cam2_label = QLabel("Camera 2 (กล้องสำหรับตรวจจับก๊าซ)")
        self.cam2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam2_label.setStyleSheet("background-color: black; color: white; border: 2px solid black;")
        self.cam2_label.setFixedSize(500, 350)
        cam2_layout.addWidget(self.cam2_label)
        main_layout.addLayout(cam2_layout, 0, 1)

        # ---------------------------------------------------------
        # Row 1: WASD Control Status | การอัดวิดีโอ Control
        # ---------------------------------------------------------
        self.status_label = QLabel("W A S D X (Keyboard Control)")
        self.status_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        main_layout.addWidget(self.status_label, 1, 0, Qt.AlignmentFlag.AlignLeft)

        record_layout = QHBoxLayout()
        self.btn_record = QPushButton("เริ่มอัดวิดีโอ")
        self.btn_record.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_record.clicked.connect(self.start_record)
        
        lbl_time = QLabel("เวลาการอัดวิดีโอ (วิ):")
        self.input_time = QLineEdit("5")
        self.input_time.setFixedWidth(50)
        
        record_layout.addWidget(self.btn_record)
        record_layout.addWidget(lbl_time)
        record_layout.addWidget(self.input_time)
        record_layout.addStretch()
        
        record_container = QWidget()
        record_container.setLayout(record_layout)
        main_layout.addWidget(record_container, 1, 1)

        # ---------------------------------------------------------
        # Row 2 & 3: กราฟ PID + Text RPM | Result Heatmap
        # ---------------------------------------------------------
        # กราฟ PID มอเตอร์ (ซ้าย) ซ้อน 2 เลเยอร์
        self.graph_widget = pg.PlotWidget(title="PID - กราฟมอเตอร์ทั้ง 4 ตัว")
        self.graph_widget.addLegend(offset=(10, 10))
        self.graph_widget.showGrid(x=True, y=True)
        self.graph_widget.setFixedSize(500, 300)

        # Raw RPM Curves (สีจาง 50% -> Alpha = 127)
        self.curve_m1_raw = self.graph_widget.plot(pen=pg.mkPen((255, 0, 0, 127), width=2, style=Qt.PenStyle.DashLine), name="M1 (Raw)")
        self.curve_m2_raw = self.graph_widget.plot(pen=pg.mkPen((255, 255, 0, 127), width=2, style=Qt.PenStyle.DashLine), name="M2 (Raw)")
        self.curve_m3_raw = self.graph_widget.plot(pen=pg.mkPen((0, 255, 0, 127), width=2, style=Qt.PenStyle.DashLine), name="M3 (Raw)")
        self.curve_m4_raw = self.graph_widget.plot(pen=pg.mkPen((0, 255, 255, 127), width=2, style=Qt.PenStyle.DashLine), name="M4 (Raw)")

        # Adj RPM Curves (สีเข้มปกติ 100% -> Alpha = 255)
        self.curve_m1_adj = self.graph_widget.plot(pen=pg.mkPen((255, 0, 0, 255), width=2), name="M1 (Adj)")
        self.curve_m2_adj = self.graph_widget.plot(pen=pg.mkPen((255, 255, 0, 255), width=2), name="M2 (Adj)")
        self.curve_m3_adj = self.graph_widget.plot(pen=pg.mkPen((0, 255, 0, 255), width=2), name="M3 (Adj)")
        self.curve_m4_adj = self.graph_widget.plot(pen=pg.mkPen((0, 255, 255, 255), width=2), name="M4 (Adj)")

        self.m1_raw, self.m2_raw, self.m3_raw, self.m4_raw = [], [], [], []
        self.m1_adj, self.m2_adj, self.m3_adj, self.m4_adj = [], [], [], []
        main_layout.addWidget(self.graph_widget, 2, 0)

        # ตัวเลข RPM (ด้านล่างกราฟ)
        self.rpm_text_label = QLabel("RPM: M1=0.00  M2=0.00  M3=0.00  M4=0.00")
        self.rpm_text_label.setFont(QFont("Arial", 12))
        main_layout.addWidget(self.rpm_text_label, 3, 0)

        # Result Camera 2 (ขวา) จะแสดงผลต่อเมื่อประมวลผลเสร็จ
        self.result_label = QLabel("Result of camera 2\n(ผลลัพธ์ heatmap จะแสดงหลังจากการอัดวิดีโอเสร็จสิ้น)")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("background-color: #222; color: #888; border: 2px solid black;")
        self.result_label.setFixedSize(500, 300)
        # Span 2 rows เพื่อให้สมดุลกับความสูงของฝั่งซ้าย
        main_layout.addWidget(self.result_label, 2, 1, 2, 1) 

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def keyPressEvent(self, event):
        if event.isAutoRepeat(): return
        key = event.key()
        if key == Qt.Key.Key_W: self.send_cmd('W')
        elif key == Qt.Key.Key_A: self.send_cmd('A')
        elif key == Qt.Key.Key_S: self.send_cmd('S')
        elif key == Qt.Key.Key_D: self.send_cmd('D')
        elif key == Qt.Key.Key_Space: self.send_cmd('X')

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat() and event.key() in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
            self.send_cmd('X')

    def send_cmd(self, cmd_char):
        pub.sendMessage(TOPIC_CMD_SEND, cmd=cmd_char)

    def start_record(self):
        try:
            duration = int(self.input_time.text())
        except:
            duration = 5
        self.playback_timer.stop()
        self.result_label.setText(f"กำลังอัดวิดีโอเป็นเวลา {duration} วินาที\nและทำการประมวลผล กรุณารอซักครู่...")
        self.btn_record.setEnabled(False)
        pub.sendMessage(TOPIC_START_RECORD, duration=duration)

    # --- PubSub Handlers ---
    def on_frame(self, frame, data=None): self.comm.frame_signal.emit(frame)
    def on_rpm(self, rpm_list): self.comm.rpm_signal.emit(rpm_list)
    def on_raw_rpm(self, raw_list): self.comm.raw_rpm_signal.emit(raw_list)
    def on_evm_result(self, frames): self.comm.evm_result_signal.emit(frames)

    # --- UI Updaters ---
    def update_image(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        # เนื่องจากกล้องมีแค่ตัวเดียว เลยนำภาพเดียวกันไปโชว์ทั้งคู่
        self.cam1_label.setPixmap(pixmap)
        self.cam2_label.setPixmap(pixmap)

    def update_graph_raw(self, lst):
        if len(lst) >= 4:
            self.m1_raw.append(lst[0]); self.m2_raw.append(lst[1]); self.m3_raw.append(lst[2]); self.m4_raw.append(lst[3])
            if len(self.m1_raw) > 100:
                self.m1_raw.pop(0); self.m2_raw.pop(0); self.m3_raw.pop(0); self.m4_raw.pop(0)
            self.curve_m1_raw.setData(self.m1_raw); self.curve_m2_raw.setData(self.m2_raw)
            self.curve_m3_raw.setData(self.m3_raw); self.curve_m4_raw.setData(self.m4_raw)

    def update_graph_adj(self, lst):
        if len(lst) >= 4:
            self.m1_adj.append(lst[0]); self.m2_adj.append(lst[1]); self.m3_adj.append(lst[2]); self.m4_adj.append(lst[3])
            if len(self.m1_adj) > 100:
                self.m1_adj.pop(0); self.m2_adj.pop(0); self.m3_adj.pop(0); self.m4_adj.pop(0)
            self.curve_m1_adj.setData(self.m1_adj); self.curve_m2_adj.setData(self.m2_adj)
            self.curve_m3_adj.setData(self.m3_adj); self.curve_m4_adj.setData(self.m4_adj)
            
            # อัปเดตตัวเลข RPM ใต้กราฟ
            self.rpm_text_label.setText(f"RPM: M1={lst[0]:.1f}  M2={lst[1]:.1f}  M3={lst[2]:.1f}  M4={lst[3]:.1f}")

    def start_heatmap_playback(self, frames):
        self.btn_record.setEnabled(True)
        if not frames:
            self.result_label.setText("เกิดข้อผิดพลาด หรือวิดีโอสั้นเกินไป")
            return
            
        self.evm_frames = frames
        self.evm_frame_index = 0
        # ตั้ง Playback Loop ที่ 30 FPS (~33ms)
        self.playback_timer.start(33)

    def next_heatmap_frame(self):
        if not self.evm_frames: return
        frame = self.evm_frames[self.evm_frame_index]
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.result_label.setPixmap(QPixmap.fromImage(qt_img).scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio))
        self.evm_frame_index = (self.evm_frame_index + 1) % len(self.evm_frames)