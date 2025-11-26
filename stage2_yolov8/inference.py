import json
import torch
from ultralytics import YOLO
from PIL import Image
import io

# Load model at startup
model = None

def model_fn(model_dir):
    global model
    model_path = f"{model_dir}/yolov8n.pt"
    model = YOLO(model_path)
    return model

def input_fn(request_body, content_type):
    if content_type == "application/x-image":
        return Image.open(io.BytesIO(request_body)).convert("RGB")
    raise ValueError("Unsupported content type: {}".format(content_type))

def predict_fn(image, model):
    results = model(image)
    output = []
    for det in results[0].boxes:
        output.append({
            "class": model.names[int(det.cls)],
            "score": float(det.conf),
            "bbox": det.xyxy[0].tolist()
        })
    return output

def output_fn(prediction, accept="application/json"):
    return json.dumps({"detections": prediction})
