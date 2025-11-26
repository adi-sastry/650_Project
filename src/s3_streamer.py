# stage2_yolov8/src/s3_streamer.py
import io
import logging
from typing import Iterable, Tuple, Iterator

import boto3
import numpy as np
import cv2

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def fetch_image_bytes(bucket: str, key: str, s3:boto3.client=None) -> bytes:
    s3 = s3 or boto3.client("s3")
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()

def decode_image_rgb(img_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Failed to decode image")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb

def stream_images(bucket: str, keys: Iterable[str], s3_client:boto3.client = None) -> Iterator[Tuple[str, np.ndarray]]:
    """
    Yield (key, image_rgb_ndarray) for each provided S3 key.
    No local files used, no ListBucket required.
    """
    s3 = s3_client or boto3.client("s3")
    for key in keys:
        try:
            img_bytes = fetch_image_bytes(bucket, key, s3=s3)
            img = decode_image_rgb(img_bytes)
            yield key, img
        except Exception as e:
            logger.error("Failed to stream %s/%s: %s", bucket, key, e)
            continue
