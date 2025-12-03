import os
import json
import logging
import subprocess
import sys
import torch
import base64
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
except ImportError:
    logger.info("ultralytics not found → installing now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics>=8.2.0", "--no-cache-dir"])
    from ultralytics import YOLO

model = None

def model_fn(model_dir):
    global model
    logger.info("=== model_fn started ===")
    logger.info(f"Loading model from {model_dir}")
    logger.info(f"Files in model_dir: {os.listdir(model_dir)}")
    
    model_path = os.path.join(model_dir, "best_yolo.pt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    logger.info("Loading YOLO model...")
    model = YOLO(model_path)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    logger.info(f"YOLO model loaded successfully on {device}")
    return model

def input_fn(request_body, content_type):
    logger.info(f"Received content_type: {content_type}")
    if content_type in ["application/octet-stream", "application/x-image", "image/jpeg", "image/png"]:
        img_bytes = request_body
    elif content_type == "application/json":
        payload = json.loads(request_body)
        img_bytes = base64.b64decode(payload["image"])    
    else:
        raise ValueError(f"Unsupported content_type: {content_type}")
    
    from PIL import Image
    image = Image.open(BytesIO(img_bytes)).convert("RGB")
    image = image.resize((640, 640), Image.Resampling.LANCZOS)
    return image

def predict_fn(input_data, model):
    results = model(input_data, verbose=False)[0]
    return results

def output_fn(prediction, accept):
    preds = []
    if prediction.boxes is not None:
        for box in prediction.boxes:
            conf = float(box.conf[0])
            if conf > 0.25:
                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                cls_id = int(box.cls[0])
                preds.append({
                    "class": model.names[cls_id],
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2]
                })
    return json.dumps({"predictions": preds})
