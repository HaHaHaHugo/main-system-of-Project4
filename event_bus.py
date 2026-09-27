from pubsub import pub

# นิยาม Topic ทั้งหมดที่ใช้สื่อสารภายในระบบ
TOPIC_RAW_FRAME = "camera.raw_frame"       # Node 1 -> Node 2
TOPIC_PROCESSED_FRAME = "vision.processed" # Node 2 -> Node 4
TOPIC_RPM_DATA = "robot.rpm"               # Node 1 -> Node 3, Node 4
TOPIC_PID_OUTPUT = "pid.output"            # Node 3 -> Node 1
TOPIC_CMD_SEND = "robot.cmd"               # Node 4 -> Node 1