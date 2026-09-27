import cv2
import numpy as np
import scipy.fft as fft
import threading
import time
from pubsub import pub
from event_bus import TOPIC_RAW_FRAME, TOPIC_PROCESSED_FRAME, TOPIC_START_RECORD, TOPIC_EVM_RESULT

class VisionNode:
    def __init__(self):
        self.state = "IDLE"
        self.record_buffer = []
        self.start_time = 0
        self.duration = 5

        pub.subscribe(self.on_raw_frame, TOPIC_RAW_FRAME)
        pub.subscribe(self.on_start_record, TOPIC_START_RECORD)
        print("[Vision Node] Gas Plume Analyzer Initialized...")

    def on_start_record(self, duration):
        if self.state == "IDLE":
            self.duration = duration
            self.record_buffer = []
            self.start_time = time.time()
            self.state = "RECORDING"
            print(f"[Vision Node] Started Recording for {duration} seconds.")

    def on_raw_frame(self, frame):
        if frame is None:
            return

        annotated_frame = frame.copy()
        
        # 1. ระบบ Record วิดีโอเพื่อนำไปประมวลผลก๊าซ
        if self.state == "RECORDING":
            elapsed = time.time() - self.start_time
            if elapsed <= self.duration:
                # ลดขนาดภาพเพื่อลดภาระ RAM ระหว่างทำ EVM FFT
                small_frame = cv2.resize(frame, (320, 240))
                self.record_buffer.append(small_frame)
            else:
                self.state = "PROCESSING"
                print("[Vision Node] Recording Done. Starting EVM Processing...")
                threading.Thread(target=self.process_gas_plume, args=(self.record_buffer,), daemon=True).start()

        # 2. ส่งภาพ Real-time ให้ UI ปกติ
        pub.sendMessage(TOPIC_PROCESSED_FRAME, frame=annotated_frame, data={"state": self.state})

    def process_gas_plume(self, frames):
        if len(frames) < 15:
            print("[Vision Node Error] Not enough frames recorded.")
            pub.sendMessage(TOPIC_EVM_RESULT, frames=[])
            self.state = "IDLE"
            return

        h, w = frames[0].shape[:2]
        levels = 3
        alpha = 50.0
        low_freq, high_freq = 0.5, 2.0
        fps = len(frames) / self.duration

        print(f"[Vision Node] Running EVM FFT on {len(frames)} frames...")
        tensor = np.zeros((len(frames), h, w, 2), dtype=np.float32)

        # Build Laplacian/Gaussian Pyramid for Chroma
        for i, frame in enumerate(frames):
            ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            chroma = ycrcb[:, :, 1:].astype(np.float32)
            pyr = [chroma]
            for _ in range(levels - 1):
                pyr.append(cv2.pyrDown(pyr[-1]))
            tensor[i] = cv2.resize(pyr[-1], (w, h), interpolation=cv2.INTER_LINEAR)

        # Temporal Bandpass Filtering (FFT)
        fft_data = fft.fft(tensor, axis=0, workers=4)
        frequencies = fft.fftfreq(len(frames), d=1.0 / fps)
        keep = (np.abs(frequencies) >= low_freq) & (np.abs(frequencies) <= high_freq)
        fft_data[~keep, ...] = 0

        filtered = np.real(fft.ifft(fft_data, axis=0, workers=4)).astype(np.float32)
        filtered *= alpha

        result_frames = []
        for i, orig_frame in enumerate(frames):
            chroma_diff = np.hypot(filtered[i, :, :, 0], filtered[i, :, :, 1])
            chroma_diff = cv2.GaussianBlur(chroma_diff, (7, 7), 0)
            norm_diff = cv2.normalize(chroma_diff, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

            _, motion_mask = cv2.threshold(norm_diff, 40, 255, cv2.THRESH_BINARY)
            color_map = cv2.applyColorMap(norm_diff, cv2.COLORMAP_JET)
            color_mask_3ch = cv2.cvtColor(motion_mask, cv2.COLOR_GRAY2BGR)
            colored_gas = cv2.bitwise_and(color_map, color_mask_3ch)

            overlay = cv2.addWeighted(orig_frame, 0.7, colored_gas, 0.8, 0)
            result_frames.append(overlay)

        print("[Vision Node] Processing Complete. Sending Heatmap Results to UI.")
        pub.sendMessage(TOPIC_EVM_RESULT, frames=result_frames)
        self.state = "IDLE"