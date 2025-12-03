import json
import os
import logging
import torch
from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = None

def model_fn(model_dir):
    global model
    logger.info(f"Loading model from {model_dir}")
    logger.info(f"Files in model_dir: {os.listdir(model_dir)}")
    
    os.environ["ULTRALYTICS_TRACE"] = "0"
    model_path = os.path.join(model_dir, "best_yolo.pt")
    model = YOLO(model_path)

    device = "cuda"
    model.to(device)
    logger.info("Model loaded successfully")
    return model

def input_fn(request_body, content_type):
    logger.info(f"Received content_type: {content_type}")
    if content_type in ["application/octet-stream", "application/x-image", "image/jpeg", "image/png"]:
        img_bytes = request_body
    elif content_type == "application/json":
        payload = json.loads(request_body)

        if "image" not in payload:
            raise ValueError("JSON payload must contain 'image' key with base64 string")
        img_bytes = base64.b64decode(payload["image"])
    else:
        raise ValueError(f"Unsupported content_type: {content_type}")
   
    # Open and convert resize (fast)
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
            if float(box.conf) > 0.25:
                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                cls_id = int(box.cls[0])
                preds.append({
                    "class": model.names[cls_id],
                    "confidence": float(box.conf[0]),
                    "bbox": [x1, y1, x2, y2]
                })
    return json.dumps({"predictions": preds})