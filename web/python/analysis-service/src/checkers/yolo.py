"""학습한 물체 인식 모델(YOLOv8, ONNX)로 사진에서 물체 상자를 찾는다. OBJECT detector='model' 이 쓴다.

모델 파일: <모델 폴더>/<이름>.onnx. 모델 폴더는 환경변수 CHECKER_MODEL_DIR, 없으면 이 폴더 옆 models/.
클래스 이름은 ONNX 메타데이터(ultralytics 가 export 때 넣는 names)에서 읽는다.
onnxruntime 이 없으면 ImportError → 판독기는 그 규칙만 '판독기 오류(UNKNOWN)'로 낸다(다른 규칙은 영향 없음).
전처리·후처리는 numpy + Pillow 만 쓴다(로봇 안에서도 같은 파일).
"""
from __future__ import annotations

import ast
import os
import threading
from pathlib import Path

import numpy as np

MODEL_DIR = Path(os.environ.get('CHECKER_MODEL_DIR') or Path(__file__).resolve().parent.parent / 'models')
_cache: dict = {}
_lock = threading.Lock()


class YoloModel:
    def __init__(self, path: Path):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(path), sess_options=opts, providers=['CPUExecutionProvider'])
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.size = int(inp.shape[2]) if isinstance(inp.shape[2], int) else 640
        meta = self.session.get_modelmeta().custom_metadata_map
        try:
            names = ast.literal_eval(meta.get('names', '{}'))
        except (ValueError, SyntaxError):
            names = {}
        self.names = {int(k): str(v) for k, v in names.items()}

    def detect(self, rgb: np.ndarray, conf: float = 0.25, iou: float = 0.5) -> list:
        """[(클래스 이름, 신뢰도, [x0, y0, x1, y1] 픽셀)] 신뢰도 높은 순."""
        from PIL import Image
        h, w = rgb.shape[:2]
        s = self.size / max(h, w)
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        px, py = (self.size - nw) // 2, (self.size - nh) // 2
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)         # 학습 때와 같은 회색 여백
        canvas[py:py + nh, px:px + nw] = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR))
        x = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = self.session.run(None, {self.input_name: x})[0][0]               # (4 + 클래스 수, 후보 수)
        boxes, scores = out[:4].T, out[4:].T
        cls = scores.argmax(axis=1)
        best = scores[np.arange(len(cls)), cls]
        keep = best >= conf
        boxes, best, cls = boxes[keep], best[keep], cls[keep]
        if not len(best):
            return []
        cx, cy, bw, bh = boxes.T
        xyxy = np.stack([(cx - bw / 2 - px) / s, (cy - bh / 2 - py) / s, (cx + bw / 2 - px) / s, (cy + bh / 2 - py) / s], 1)
        xyxy = np.clip(xyxy, 0, [w, h, w, h])
        out = []
        for c in np.unique(cls):
            idx = np.where(cls == c)[0]
            for i in _nms(xyxy[idx], best[idx], iou):
                j = idx[i]
                out.append((self.names.get(int(c), str(int(c))), float(best[j]), [float(v) for v in xyxy[j]]))
        return sorted(out, key=lambda d: -d[1])


def _nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> list:
    order, keep = scores.argsort()[::-1], []
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    while len(order):
        i = order[0]
        keep.append(int(i))
        xx0 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy0 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx1 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy1 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx1 - xx0, 0, None) * np.clip(yy1 - yy0, 0, None)
        order = order[1:][inter / (area[i] + area[order[1:]] - inter + 1e-9) < iou]
    return keep


def get_model(name: str) -> YoloModel:
    """이름으로 모델을 찾는다(한 번 읽으면 계속 쓴다)."""
    if not name or '/' in name or '\\' in name or name.startswith('.'):
        raise ValueError(f'모델 이름이 올바르지 않음: {name!r}')
    with _lock:
        if name not in _cache:
            path = MODEL_DIR / f'{name}.onnx'
            if not path.exists():
                raise FileNotFoundError(f'모델 파일 없음: {path.name}')
            _cache[name] = YoloModel(path)
        return _cache[name]
