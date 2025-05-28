import cv2
import os


def process_and_save_frame():
    video_path = 'videos/1.mp4'
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return None

    frame_number = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
    ret, frame = cap.read()

    if ret:
        # Save the frame every 12th frame (e.g., frame_0000, frame_0012, ...)
        if frame_number % 12 == 0:
            filename = f"frames/frame_{frame_number:04d}.jpg"
            cv2.imwrite(filename, frame)
            cap.release()
            return frame_number
        cap.release()
    return None
