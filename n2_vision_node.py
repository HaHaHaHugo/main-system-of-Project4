import cv2
import numpy as np
from pubsub import pub
from event_bus import TOPIC_RAW_FRAME, TOPIC_PROCESSED_FRAME

class VisionNode:
    def __init__(self):
        # Subscribe รับ Frame ดิบจาก Network
        pub.subscribe(self.on_raw_frame, TOPIC_RAW_FRAME)
        print("[Vision Node] Initialized & Listening for frames...")

    def on_raw_frame(self, frame):
        if frame is None:
            return

        # -------------------------------------------------------------
        # 🧠 พื้นที่สำหรับเขียน Image Processing / Contour / AI ในอนาคต
        # -------------------------------------------------------------
        annotated_frame = frame.copy()
        h, w, _ = frame.shape
        cv2.circle(annotated_frame, (w // 2, h // 2), 6, (0, 255, 0), -1) # วาดจุดศูนย์กลาง

        # Publish ภาพที่ประมวลผลแล้วออกไปให้ UI Node แสดงผล
        pub.sendMessage(TOPIC_PROCESSED_FRAME, frame=annotated_frame, data={"center": (w//2, h//2)})