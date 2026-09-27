import time
from pubsub import pub
from event_bus import TOPIC_RPM_DATA, TOPIC_PID_OUTPUT

class PIDNode:
    def __init__(self, kp=1.0, ki=0.1, kd=0.05):
        # PID Gains
        self.kp = kp
        self.ki = ki
        self.kd = kd

        # Target RPM สำหรับมอเตอร์ทั้ง 4 ล้อ [M1, M2, M3, M4]
        self.target_rpm = [0.0, 0.0, 0.0, 0.0]

        self.pwm_dirs = [-1, -1, -1, -1]

        # ตัวแปรสำหรับคำนวณ PID Loop
        self.prev_errors = [0.0, 0.0, 0.0, 0.0]
        self.integrals = [0.0, 0.0, 0.0, 0.0]
        self.last_time = time.time()

        # ข้อจำกัดสัญญาณ Output PWM (BTS7960 รองรับ -255 ถึง 255)
        self.min_out = -255
        self.max_out = 255

        # Subscribe รับค่า RPM จริงจากหุ่นยนต์ผ่าน Event Bus
        pub.subscribe(self.on_rpm_received, TOPIC_RPM_DATA)
        print("[PID Node] Initialized & Active...")

    def update_gains(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.reset_pid()
        print(f"[PID Node] Gains Updated -> Kp: {self.kp:.2f}, Ki: {self.ki:.2f}, Kd: {self.kd:.2f}")

    def set_target_rpm(self, targets):
        if len(targets) == 4:
            self.target_rpm = [float(t) for t in targets]

    def reset_pid(self):
        self.prev_errors = [0.0, 0.0, 0.0, 0.0]
        self.integrals = [0.0, 0.0, 0.0, 0.0]
        self.last_time = time.time()

    def on_rpm_received(self, rpm_list):
        current_time = time.time()
        dt = current_time - self.last_time

        if dt <= 0.0:
            dt = 0.05
        elif dt > 1.0:
            dt = 0.05
            self.reset_pid()

        self.last_time = current_time
        pwm_output = []

        for i in range(4):
            target = self.target_rpm[i]
            actual = float(rpm_list[i]) if i < len(rpm_list) else 0.0

            # 1. Error = Target - Actual (เนื่องจาก RPM ล้อขวาถูกสลับให้เป็นบวกแล้ว จึงลบกันตรงๆ ได้เลย)
            error = target - actual

            # 2. Proportional Term (P)
            p_term = self.kp * error

            # 3. Integral Term (I) พร้อมระบบ Anti-windup
            self.integrals[i] += error * dt
            self.integrals[i] = max(-100.0, min(100.0, self.integrals[i]))
            i_term = self.ki * self.integrals[i]

            # 4. Derivative Term (D)
            derivative = (error - self.prev_errors[i]) / dt
            d_term = self.kd * derivative

            # 5. รวมสัญญาณ PID Output พื้นฐาน
            base_output = p_term + i_term + d_term

            # 5.1 คูณทิศทางของฮาร์ดแวร์ (สลับเครื่องหมาย M1 และ M3 ให้ติดลบเมื่อเดินหน้า)
            directional_output = base_output * self.pwm_dirs[i]

            # 6. Clamp ผลลัพธ์ PWM ให้อยู่ในช่วง [-255, 255]
            output_clamped = int(max(self.min_out, min(self.max_out, directional_output)))
            pwm_output.append(output_clamped)

            # บันทึก Error ล่าสุดสำหรับรอบถัดไป
            self.prev_errors[i] = error

        # Publish ผลลัพธ์ PWM กลับไปยัง Event Bus
        pub.sendMessage(TOPIC_PID_OUTPUT, pwm=pwm_output)

if __name__ == "__main__":
    node = PIDNode()
    print("Testing PID Node loop...")