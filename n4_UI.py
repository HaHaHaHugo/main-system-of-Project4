import sys
import cv2
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from pubsub import pub
from event_bus import TOPIC_PROCESSED_FRAME, TOPIC_RPM_DATA, TOPIC_CMD_SEND, TOPIC_PID_OUTPUT

class Communicate(QObject):
    frame_signal = pyqtSignal(object)
    rpm_signal = pyqtSignal(list)
    pid_signal = pyqtSignal(list)

class RobotDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Control Center - PyQt6 Pub/Sub Dashboard")
        self.resize(1100, 750)

        # 🎯 ดึง Focus มาที่หน้าต่างโดยตรงเพื่อให้กด Keyboard สั่งการได้ทันที
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.raise_()
        self.activateWindow()

        self.comm = Communicate()
        self.comm.frame_signal.connect(self.update_image)
        self.comm.rpm_signal.connect(self.update_graph)
        self.comm.pid_signal.connect(self.update_pid_graph)

        # Subscriptions
        pub.subscribe(self.on_frame, TOPIC_PROCESSED_FRAME)
        pub.subscribe(self.on_rpm, TOPIC_RPM_DATA)
        pub.subscribe(self.on_pid, TOPIC_PID_OUTPUT)

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # --- ซีกซ้าย: สตรีมภาพกล้อง ---
        self.cam_label = QLabel("Waiting for Camera Stream...")
        self.cam_label.setFixedSize(640, 480)
        self.cam_label.setStyleSheet("background-color: black; color: white;")
        main_layout.addWidget(self.cam_label)

        # --- ซีกขวา: กราฟ RPM, กราฟ PID และแผงปุ่มสั่งการ ---
        right_panel = QVBoxLayout()
        
        # 📈 1. กราฟ RPM Real-time
        self.graph_widget = pg.PlotWidget(title="4-Wheel Motors RPM Real-Time")
        self.graph_widget.addLegend()
        self.graph_widget.showGrid(x=True, y=True)
        
        self.curve_m1 = self.graph_widget.plot(pen=pg.mkPen('r', width=2), name="M1 (FL)")
        self.curve_m2 = self.graph_widget.plot(pen=pg.mkPen('y', width=2), name="M2 (FR)")
        self.curve_m3 = self.graph_widget.plot(pen=pg.mkPen('g', width=2), name="M3 (RL)")
        self.curve_m4 = self.graph_widget.plot(pen=pg.mkPen('b', width=2), name="M4 (RR)")
        
        self.m1_data, self.m2_data, self.m3_data, self.m4_data = [], [], [], []
        right_panel.addWidget(self.graph_widget)

        # 📈 2. กราฟ PID (PWM Output) สำหรับ 4 DC Motors
        self.pid_graph = pg.PlotWidget(title="PID PWM Output (-255 to 255)")
        self.pid_graph.addLegend()
        self.pid_graph.showGrid(x=True, y=True)
        self.pid_graph.setYRange(-260, 260) 
        
        self.pid_curve_m1 = self.pid_graph.plot(pen=pg.mkPen('r', width=2), name="PWM M1")
        self.pid_curve_m2 = self.pid_graph.plot(pen=pg.mkPen('y', width=2), name="PWM M2")
        self.pid_curve_m3 = self.pid_graph.plot(pen=pg.mkPen('g', width=2), name="PWM M3")
        self.pid_curve_m4 = self.pid_graph.plot(pen=pg.mkPen('b', width=2), name="PWM M4")
        
        self.pwm1_data, self.pwm2_data, self.pwm3_data, self.pwm4_data = [], [], [], []
        right_panel.addWidget(self.pid_graph) 

        self.status_label = QLabel("Keyboard Control: WASD (Move), SPACE (Stop)")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2e7d32; padding: 5px;")
        right_panel.addWidget(self.status_label)

        # ปุ่มกดควบคุม
        btn_layout = QHBoxLayout()
        btn_w = QPushButton("W (Forward)")
        btn_a = QPushButton("A (Left)")
        btn_s = QPushButton("S (Backward)")
        btn_d = QPushButton("D (Right)")
        btn_stop = QPushButton("SPACE (Stop)")

        # 🚫 ป้องกันไม่ให้ปุ่มกดมาแย่ง Focus ไปจาก Keyboard
        for btn in (btn_w, btn_a, btn_s, btn_d, btn_stop):
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        btn_w.clicked.connect(lambda: self.send_cmd('W'))
        btn_a.clicked.connect(lambda: self.send_cmd('A'))
        btn_s.clicked.connect(lambda: self.send_cmd('S'))
        btn_d.clicked.connect(lambda: self.send_cmd('D'))
        btn_stop.clicked.connect(lambda: self.send_cmd('X'))

        btn_layout.addWidget(btn_w)
        btn_layout.addWidget(btn_a)
        btn_layout.addWidget(btn_s)
        btn_layout.addWidget(btn_d)
        btn_layout.addWidget(btn_stop)
        right_panel.addLayout(btn_layout)

        container = QWidget()
        container.setLayout(main_layout)
        main_layout.addLayout(right_panel)
        self.setCentralWidget(container)

    # -------------------------------------------------------------
    # ⌨️ Keyboard Events & Commands
    # -------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_W:
            self.send_cmd('W')
            self.status_label.setText("Command: FORWARD (W)")
        elif key == Qt.Key.Key_A:
            self.send_cmd('A')
            self.status_label.setText("Command: LEFT (A)")
        elif key == Qt.Key.Key_S:
            self.send_cmd('S')
            self.status_label.setText("Command: BACKWARD (S)")
        elif key == Qt.Key.Key_D:
            self.send_cmd('D')
            self.status_label.setText("Command: RIGHT (D)")
        elif key == Qt.Key.Key_Space:
            self.send_cmd('X')
            self.status_label.setText("Command: STOP (SPACE)")

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            key = event.key()
            if key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
                self.send_cmd('X')
                self.status_label.setText("Command: STOP (Released)")

    def send_cmd(self, cmd_char):
        pub.sendMessage(TOPIC_CMD_SEND, cmd=cmd_char)

    # -------------------------------------------------------------
    # 📡 PubSub Event Handlers
    # -------------------------------------------------------------
    def on_frame(self, frame, data=None):
        self.comm.frame_signal.emit(frame)

    def on_rpm(self, rpm_list):
        self.comm.rpm_signal.emit(rpm_list)

    def on_pid(self, pwm): 
        self.comm.pid_signal.emit(pwm)

    # -------------------------------------------------------------
    # 🖼️ UI Update Methods
    # -------------------------------------------------------------
    def update_image(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.cam_label.setPixmap(QPixmap.fromImage(qt_img))

    def update_graph(self, rpm_list):
        if len(rpm_list) >= 4:
            self.m1_data.append(rpm_list[0])
            self.m2_data.append(rpm_list[1])
            self.m3_data.append(rpm_list[2])
            self.m4_data.append(rpm_list[3])

            if len(self.m1_data) > 150:
                self.m1_data.pop(0); self.m2_data.pop(0); self.m3_data.pop(0); self.m4_data.pop(0)

            self.curve_m1.setData(self.m1_data)
            self.curve_m2.setData(self.m2_data)
            self.curve_m3.setData(self.m3_data)
            self.curve_m4.setData(self.m4_data)

    def update_pid_graph(self, pwm_list): 
        if len(pwm_list) >= 4:
            self.pwm1_data.append(pwm_list[0])
            self.pwm2_data.append(pwm_list[1])
            self.pwm3_data.append(pwm_list[2])
            self.pwm4_data.append(pwm_list[3])

            if len(self.pwm1_data) > 150:
                self.pwm1_data.pop(0); self.pwm2_data.pop(0); self.pwm3_data.pop(0); self.pwm4_data.pop(0)

            self.pid_curve_m1.setData(self.pwm1_data)
            self.pid_curve_m2.setData(self.pwm2_data)
            self.pid_curve_m3.setData(self.pwm3_data)
            self.pid_curve_m4.setData(self.pwm4_data)