import cv2
import numpy as np
import math

def find_angle(x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    magnitude = math.hypot(dx, dy)
    if magnitude == 0:
        return 0.0
    cos_theta = dy / magnitude
    angle = math.degrees(math.acos(np.clip(cos_theta, -1.0, 1.0)))
    return angle

def detect_posture(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Haar cascade face detection
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    height, width = frame.shape[:2]
    torso_center = (width // 2, int(height * 0.8))  # Approximate torso base

    for (x, y, w, h) in faces:
        face_center = (x + w // 2, y + h // 2)
        shoulder_center = (x + w // 2, y + h + int(h * 0.4))  # Estimate below face

        # Draw markers
        cv2.circle(frame, face_center, 5, (0, 255, 0), -1)
        cv2.circle(frame, shoulder_center, 5, (255, 0, 0), -1)
        cv2.circle(frame, torso_center, 5, (0, 0, 255), -1)

        # Neck and back inclination
        neck_angle = find_angle(*face_center, *shoulder_center)
        back_angle = find_angle(*shoulder_center, *torso_center)

        # Draw lines
        cv2.line(frame, face_center, shoulder_center, (0, 255, 0), 2)
        cv2.line(frame, shoulder_center, torso_center, (255, 0, 0), 2)

        # Display angles
        cv2.putText(frame, f'Neck: {neck_angle:.1f} deg', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f'Back: {back_angle:.1f} deg', (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    return frame

def run_posture_analysis():
    cap = cv2.VideoCapture(0)  # 0 = webcam

    if not cap.isOpened():
        print("Cannot open webcam.")
        return

    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (640, 480))
        analyzed_frame = detect_posture(frame)
        cv2.imshow('Posture Estimator', analyzed_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_posture_analysis()
