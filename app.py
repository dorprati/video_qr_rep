import os
import glob
import cv2
import pandas as pd
from flask import request, send_from_directory, render_template, jsonify, Flask
import base64

app = Flask(__name__)
FRAMES_DIR = 'frames/'

# Automatically find the first Excel file in the data folder
excel_files = glob.glob('data/*.xlsx')
if excel_files:
    EXCEL_PATH = excel_files[0]
    print(f"✅ Using Excel file: {EXCEL_PATH}")
else:
    raise FileNotFoundError("❌ No Excel file found in the 'data' folder.")

def load_excel_to_dict(path):
    df = pd.read_excel(path)

    coordinates_by_frame = {}

    for _, row in df.iterrows():
        try:
            frame_number = int(row.iloc[0])  # Column A
        except (ValueError, TypeError):
            continue  # Skip rows where the frame number isn't an integer

        box = str(row.iloc[1]) if not pd.isna(row.iloc[1]) else ""
        label = str(row.iloc[2]) if not pd.isna(row.iloc[2]) else "Unknown"
        link = str(row.iloc[3]) if not pd.isna(row.iloc[3]) else ""

        if frame_number not in coordinates_by_frame:
            coordinates_by_frame[frame_number] = []

        coordinates_by_frame[frame_number].append({
            "box": box,
            "label": label,
            "link": link
        })

    return coordinates_by_frame

coordinates_by_frame = load_excel_to_dict(EXCEL_PATH)

@app.route('/frames/<filename>')
def serve_frame(filename):
    return send_from_directory(FRAMES_DIR, filename)

@app.route('/')
def home():
    return render_template('host.html')

@app.route('/video-page')
def video_page():
    return render_template('video.html')

@app.route('/static/video')
def serve_video():
    video_path = os.path.join('videos', '1.mp4')
    if os.path.exists(video_path):
        return send_from_directory('videos', '1.mp4', mimetype='video/mp4')
    else:
        return "Video not found", 404

@app.route('/capture-frame', methods=['POST'])
def capture_frame():
    data = request.get_json()
    current_time = data.get('time')

    if current_time is None:
        return jsonify({"status": "error", "message": "Missing time"}), 400

    frame_number, frame_base64 = capture_frame_at_time(current_time)

    if frame_number is not None:
        closest_frames = get_two_closest_frames(frame_number)

        frame_urls = []
        if closest_frames:
            for filename in closest_frames:
                try:
                    frame_num = int(filename.split('_')[1].split('.')[0])
                    frame_urls.append({
                        "url": f"/frames/{filename}",
                        "frame": frame_num
                    })
                except Exception:
                    continue

        return jsonify({
            "status": "success",
            "frame": frame_number,
            "image": frame_base64,
            "images": frame_urls
        }), 200

    else:
        return jsonify({"status": "error", "message": "Could not process video"}), 500

@app.route('/get-coordinates', methods=['POST'])
def get_coordinates():
    try:
        data = request.get_json()

        if not data or 'frame' not in data:
            return jsonify({"status": "error", "message": "Missing frame number in request"}), 400

        frame_number = int(data.get('frame'))

        coordinates = coordinates_by_frame.get(frame_number, [])

        if not coordinates:
            return jsonify({"status": "error", "message": f"No coordinates found for frame {frame_number}"}), 404

        print(f"✅ Coordinates with labels and links for frame {frame_number}: {coordinates}")

        return jsonify({
            "status": "success",
            "frame": frame_number,
            "coordinates": coordinates
        }), 200

    except Exception as e:
        print(f"❌ Error in /get-coordinates: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def capture_frame_at_time(current_time):
    video_path = 'videos/1.mp4'
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return None, None

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(float(current_time) * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()

    if ret:
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')

        cap.release()
        return frame_number, frame_base64
    else:
        cap.release()
        return None, None

def get_two_closest_frames(frame_number):
    try:
        frame_files = sorted(
            [f for f in os.listdir(FRAMES_DIR) if f.startswith("frame_") and f.endswith(".jpg")],
            key=lambda x: int(x.split('_')[1].split('.')[0])
        )
    except FileNotFoundError:
        return None

    result = []
    for i, frame_file in enumerate(frame_files):
        num = int(frame_file.split('_')[1].split('.')[0])
        if num <= frame_number:
            if i > 0:
                result = [frame_files[i - 1], frame_files[i]]
            else:
                result = [frame_files[i]]
        else:
            break

    return result if result else None

if __name__ == '__main__':
    app.run(debug=True)
