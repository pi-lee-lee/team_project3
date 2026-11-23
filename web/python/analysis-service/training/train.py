"""YOLO 학습. label.py 로 라벨링한 폴더를 그대로 넣으면 학습용으로 나눠서 학습까지 한다.

    source ~/yolo_venv/bin/activate
    python train.py                          # ~/dataset(raw + labels) → 학습 → ~/models/best.pt
    python train.py --epochs 80 --imgsz 640  # 더 오래·크게(느림)
    python train.py --data data.yaml         # 다른 곳(Roboflow 등)에서 만든 data.yaml 로 학습

CPU(이 노트북)로 100~150장·50번이면 30~40분 정도. 끝나면 검증 점수(mAP50)를 출력한다.
"""
import argparse
import glob
import os
import random
import shutil

from ultralytics import YOLO

CLASSES = ['fire_extinguisher', 'obstacle']


def build(root: str, val_ratio: float) -> str:
    """raw/*.jpg + labels/*.txt → yolo/{images,labels}/{train,val} + data.yaml. 라벨 없는 사진은 뺀다."""
    raw, lab, out = os.path.join(root, 'raw'), os.path.join(root, 'labels'), os.path.join(root, 'yolo')
    pairs = []
    for t in sorted(glob.glob(os.path.join(lab, '*.txt'))):
        img = os.path.join(raw, os.path.basename(t)[:-4] + '.jpg')
        if os.path.exists(img):
            pairs.append((img, t))
    if len(pairs) < 10:
        raise SystemExit(f'라벨된 사진이 {len(pairs)}장뿐. label.py 로 먼저 라벨링하세요.')
    random.Random(0).shuffle(pairs)
    n_val = max(2, int(len(pairs) * val_ratio))
    shutil.rmtree(out, ignore_errors=True)
    for split, items in (('val', pairs[:n_val]), ('train', pairs[n_val:])):
        os.makedirs(os.path.join(out, 'images', split))
        os.makedirs(os.path.join(out, 'labels', split))
        for img, t in items:
            shutil.copy(img, os.path.join(out, 'images', split))
            shutil.copy(t, os.path.join(out, 'labels', split))
    yaml = os.path.join(out, 'data.yaml')
    with open(yaml, 'w') as f:
        f.write(f'path: {out}\ntrain: images/train\nval: images/val\nnames:\n')
        for i, c in enumerate(CLASSES):
            f.write(f'  {i}: {c}\n')
    pos = sum(1 for _, t in pairs if os.path.getsize(t) > 0)
    print(f'학습 {len(pairs) - n_val}장 / 검증 {n_val}장 (대상 있음 {pos}, 없음 {len(pairs) - pos}) → {yaml}')
    return yaml


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='~/dataset', help='raw/ 와 labels/ 가 있는 폴더')
    p.add_argument('--data', default=None, help='이미 만든 data.yaml 이 있으면 그걸로 학습')
    p.add_argument('--model', default='yolov8n.pt', help='시작 모델(n: 가장 작고 빠름)')
    p.add_argument('--epochs', type=int, default=50)
    p.add_argument('--imgsz', type=int, default=480)
    p.add_argument('--batch', type=int, default=8)
    p.add_argument('--val', type=float, default=0.2, help='검증용으로 떼어 둘 비율')
    p.add_argument('--out', default='~/models/best.pt')
    args = p.parse_args()
    data = args.data or build(os.path.expanduser(args.root), args.val)
    model = YOLO(args.model)
    model.train(data=data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, name='fire_check',
                project=os.path.expanduser('~/runs'), exist_ok=True, patience=15, workers=2,
                degrees=5, perspective=0.0005, fliplr=0.5, hsv_v=0.4, scale=0.5)   # 거리·각도·밝기 변화에 강하게
    best = os.path.expanduser('~/runs/fire_check/weights/best.pt')
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copy(best, out)
    metrics = YOLO(out).val(data=data, imgsz=args.imgsz, verbose=False)
    print(f'\n결과 모델: {out}')
    print(f'mAP50 = {metrics.box.map50:.3f} (0.8 이상이면 시연에 쓸 만함)')


if __name__ == '__main__':
    main()
