import sys
from PyQt6.QtWidgets import QApplication

# --------------------------------------------------
# Import ทุก Node ให้ตรงตามชื่อไฟล์ใน Explorer เป๊ะๆ
# --------------------------------------------------
from n1_main import MainNode
from n2_vision import VisionNode
from n3_PID import PIDNode
from n4_UI import RobotDashboard

def main():
    app = QApplication(sys.argv)

    # 1. สตาร์ท Node ฝั่งรับ/ประมวลผลข้อมูล (Vision, PID, UI)
    vision_node = VisionNode()
    pid_node = PIDNode()
    ui_node = RobotDashboard()

    # 2. สตาร์ท Main Network Node (เชื่อมต่อ Socket Pi 5)
    main_node = MainNode()

    # 3. แสดงหน้าต่าง GUI Dashboard
    ui_node.show()

    # 4. เริ่มระบบ Event Loop ของ PyQt6
    sys.exit(app.exec())

if __name__ == '__main__':
    main()