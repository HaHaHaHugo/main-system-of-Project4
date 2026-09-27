from pubsub import pub

# นิยาม Topic ทั้งหมดที่ใช้สื่อสารภายในระบบ
TOPIC_RAW_FRAME = "camera.raw_frame"       # Node 1 -> Node 2
TOPIC_PROCESSED_FRAME = "vision.processed" # Node 2 -> Node 4
TOPIC_RPM_DATA = "robot.rpm"               # Node 1 -> Node 3, Node 4 (ปรับทิศทางแล้ว)
TOPIC_RAW_RPM_DATA = "robot.raw_rpm"       # Node 1 -> Node 4 (ค่าดิบ ยังไม่ปรับทิศทาง)
TOPIC_PID_OUTPUT = "pid.output"            # Node 3 -> Node 1
TOPIC_CMD_SEND = "robot.cmd"               # Node 4 -> Node 1

# Topic สำหรับระบบตรวจจับก๊าซ
TOPIC_START_RECORD = "vision.start_record" # Node 4 -> Node 2 (สั่งเริ่มอัด)
TOPIC_EVM_RESULT = "vision.evm_result"     # Node 2 -> Node 4 (ส่งผลลัพธ์ Heatmap)