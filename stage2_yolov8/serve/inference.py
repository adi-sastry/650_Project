import os
import io
import json
from typing import Any, Dict, List

from PIL import Image
from ultralytics import YOLO


# --------------------------- Model loading (SageMaker hook) --------------------------- #
def model_fn(model_dir: str) -> YOLO:
    """
    Load the YOLOv8 model from the model directory.

    SageMaker unpacks model.tar.gz into `model_dir`.
    We try a few common filenames to be robust.
    """
    # Try several possible filenames inside /opt/ml/model
    candidate_files = [
        "yolov8n.pt",
        "best.pt",
        "model.pt",
    ]

    for fname in candidate_files:
        path = os.path.join(model_dir, fname)
        if os.path.exists(path):
            print(f"[INFO] Loading YOLO model from: {path}")
            model = YOLO(path)
            return model

    # If we get here, nothing was found
    files = os.listdir(model_dir)
    raise FileNotFoundError(
        f"No YOLO weights found in {model_dir}. "
        f"Files present: {files}"
    )


# --------------------------- Input processing (SageMaker hook) --------------------------- #
def input_fn(request_body: bytes, content_type: str) -> Image.Image:
    """
    Deserialize the incoming request.

    Our client sends raw image bytes with content_type 'application/x-image'.
    """
    if content_type in ("application/x-image", "application/octet-stream", "image/jpeg", "image/png"):
        try:
            image = Image.open(io.BytesIO(request_body)).convert("RGB")
            return image
        except Exception as e:
            raise ValueError(f"Failed to decode image: {e}")
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


# --------------------------- Prediction (SageMaker hook) --------------------------- #
def predict_fn(input_data: Image.Image, model: YOLO) -> List[Dict[str, Any]]:
    """
    Run YOLOv8 inference on the input image and return a list of detections.
    Each detection is a dict with {class_id, class_name, confidence, bbox}.
    """
    # Run inference
    results = model(input_data)

    detections = []
    # YOLOv8 returns a list; we take the first result
    for box in results[0].boxes:
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

        detections.append(
            {
                "class_id": cls_id,
                "class_name": model.names.get(cls_id, str(cls_id)),
                "confidence": conf,
                "bbox_xyxy": xyxy,
            }
        )

    return detections


# --------------------------- Output serialization (SageMaker hook) --------------------------- #
def output_fn(prediction: List[Dict[str, Any]], accept: str) -> str:
    """
    Serialize the prediction result to JSON.
    """
    if accept in ("application/json", "text/json", "application/jsonlines", "application/x-json"):
        return json.dumps({"detections": prediction})
    # Default to JSON anyway
    return json.dumps({"detections": prediction})
