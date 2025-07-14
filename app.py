import os
import glob
import cv2
import pandas as pd
import socket
import qrcode
from flask import request, send_from_directory, render_template, jsonify, Flask
import base64

app = Flask(__name__)
FRAMES_DIR = 'frames/'

# Create static folder if missing
os.makedirs('static', exist_ok=True)

# Load Excel file
excel_files = glob.glob('data/*.xlsx')
if excel_files:
    EXCEL_PATH = excel_files[0]
    print(f"✅ Using Excel file: {EXCEL_PATH}")
else:
    raise FileNotFoundError("❌ No Excel file found in the 'data' folder.")

# Load coordinates from Excel
def load_excel_to_dict(path):
    df = pd.read_excel(path)
    coordinates_by_frame = {}
    for _, row in df.iterrows():
        try:
            frame_number = int(row.iloc[0])
        except (ValueError, TypeError):
            continue

        box = str(row.iloc[1]) if not pd.isna(row.iloc[1]) else ""
        label = str(row.iloc[2]) if not pd.isna(row.iloc[2]) else "Unknown"
        default_link = str(row.iloc[3]) if not pd.isna(row.iloc[3]) else ""

        optional_links = {
            'male_20-30': str(row.iloc[4]) if not pd.isna(row.iloc[4]) else "",
            'male_30-40': str(row.iloc[5]) if not pd.isna(row.iloc[5]) else "",
            'male_40-50': str(row.iloc[6]) if not pd.isna(row.iloc[6]) else "",
            'male_50-60': str(row.iloc[7]) if not pd.isna(row.iloc[7]) else "",
            'male_65+':   str(row.iloc[8]) if not pd.isna(row.iloc[8]) else "",
            'female_20-30': str(row.iloc[9]) if not pd.isna(row.iloc[9]) else "",
            'female_30-40': str(row.iloc[10]) if not pd.isna(row.iloc[10]) else "",
            'female_40-50': str(row.iloc[11]) if not pd.isna(row.iloc[11]) else "",
            'female_50-60': str(row.iloc[12]) if not pd.isna(row.iloc[12]) else "",
            'female_65+':   str(row.iloc[13]) if not pd.isna(row.iloc[13]) else "",
        }

        coordinates_by_frame.setdefault(frame_number, []).append({
            "box": box,
            "label": label,
            "default_link": default_link,
            "optional_links": optional_links
        })
    return coordinates_by_frame

coordinates_by_frame = load_excel_to_dict(EXCEL_PATH)

# Get local IP
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Generate QR Code
def generate_qr_code():
    ip = get_local_ip()
    url = f'http://{ip}:5000/video-page'
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    path = 'static/qr.png'
    img.save(path)
    return path

generate_qr_code()

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

@app.route('/frames/<filename>')
def serve_frame(filename):
    return send_from_directory(FRAMES_DIR, filename)

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
        selected_gender = data.get('gender', [])
        selected_age = data.get('age', [])

        coords_raw = coordinates_by_frame.get(frame_number, [])
        if not coords_raw:
            return jsonify({"status": "error", "message": f"No coordinates found for frame {frame_number}"}), 404

        result_coords = []

        for row in coords_raw:
            box = row['box']
            label = row['label']
            link = row['default_link']
            any_selected = False

            if selected_gender and selected_age:
                key = f"{selected_gender[0].lower()}_{selected_age[0]}"
                link = row['optional_links'].get(key, link)
                any_selected = True

            if link and not link.startswith(('http://', 'https://')):
                link = 'http://' + link

            result_coords.append({
                "box": box,
                "label": label,
                "link": link
            })

        return jsonify({
            "status": "success",
            "frame": frame_number,
            "coordinates": result_coords
        }), 200

    except Exception as e:
        app.logger.exception("Error in get_coordinates")
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
