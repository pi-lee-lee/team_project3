"""PC 에서 바로 하는 라벨링(웹사이트 없이). 사진마다 상자를 먼저 제안하고, 맞으면 Enter 만 누른다.

    python3 label.py                     # ~/dataset/raw 의 사진 → ~/dataset/labels/*.txt (YOLO 형식)

제안 상자: 바로 앞 사진의 상자(연속 촬영이라 거의 같은 자리) → 없으면 가장 큰 빨간 덩어리.
태그가 empty 로 시작하는 사진(python3 capture.py --tag empty)은 "대상 없음"으로 자동 처리한다.

키 (사진 창에서)
    Enter / 스페이스 : 지금 상자로 확정하고 다음
    d               : 마우스로 소화기 상자 새로 그리기(그린 뒤 Enter). 여러 번 누르면 여러 개
    o               : 마우스로 적치물(obstacle) 상자 그리기
    c               : 상자 모두 지우기
    n               : 대상 없음(빈 사진)으로 확정하고 다음
    b               : 이전 사진으로
    x               : 이 사진 버리기(학습에서 뺌, 흐린 사진 등)
    q / Esc         : 저장하고 끝(다음에 이어서 함)
"""
import argparse
import glob
import os

import cv2
import numpy as np

CLASSES = ['fire_extinguisher', 'obstacle']
COLORS = [(0, 255, 0), (255, 160, 0)]


def red_box(img):
    """가장 큰 빨간 덩어리의 상자(x0, y0, x1, y1). 없으면 None."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 90, 60), (10, 255, 255)) | cv2.inRange(hsv, (170, 90, 60), (180, 255, 255))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[i]
    if area < img.shape[0] * img.shape[1] * 0.005:
        return None
    return int(x), int(y), int(x + w), int(y + h)


def read_label(path, w, h):
    boxes = []
    if os.path.exists(path):
        for line in open(path):
            p = line.split()
            if len(p) == 5:
                c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
                boxes.append((c, int((cx - bw / 2) * w), int((cy - bh / 2) * h), int((cx + bw / 2) * w), int((cy + bh / 2) * h)))
    return boxes


def write_label(path, boxes, w, h):
    with open(path, 'w') as f:
        for c, x0, y0, x1, y1 in boxes:
            x0, x1 = sorted((max(0, x0), min(w, x1)))
            y0, y1 = sorted((max(0, y0), min(h, y1)))
            if x1 - x0 < 3 or y1 - y0 < 3:
                continue
            f.write(f'{c} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='~/dataset', help='raw/ 사진 폴더와 labels/ 가 있는 곳')
    args = p.parse_args()
    root = os.path.expanduser(args.root)
    raw, lab = os.path.join(root, 'raw'), os.path.join(root, 'labels')
    os.makedirs(lab, exist_ok=True)
    files = sorted(glob.glob(os.path.join(raw, '*.jpg')))
    if not files:
        print(f'사진 없음: {raw}')
        return

    def label_path(f):
        return os.path.join(lab, os.path.splitext(os.path.basename(f))[0] + '.txt')

    def skip_path(f):
        return label_path(f)[:-4] + '.skip'

    # empty 태그는 자동으로 빈 라벨
    auto = 0
    for f in files:
        if os.path.basename(f).startswith('empty') and not os.path.exists(label_path(f)):
            open(label_path(f), 'w').close()
            auto += 1
    if auto:
        print(f'empty 사진 {auto}장은 대상 없음으로 자동 처리')

    todo = [i for i, f in enumerate(files) if not os.path.exists(label_path(f)) and not os.path.exists(skip_path(f))]
    i = todo[0] if todo else 0
    prev_boxes = []
    win = 'label'
    cv2.namedWindow(win)
    while 0 <= i < len(files):
        f = files[i]
        img = cv2.imread(f)
        h, w = img.shape[:2]
        if os.path.exists(label_path(f)):
            boxes, suggested = read_label(label_path(f), w, h), False
        elif prev_boxes:
            boxes, suggested = list(prev_boxes), True
        else:
            rb = red_box(img)
            boxes, suggested = ([(0, *rb)] if rb else []), True
        while True:
            view = img.copy()
            for c, x0, y0, x1, y1 in boxes:
                cv2.rectangle(view, (x0, y0), (x1, y1), COLORS[c], 2)
                cv2.putText(view, CLASSES[c], (x0 + 3, max(15, y0 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[c], 2)
            done = sum(os.path.exists(label_path(x)) or os.path.exists(skip_path(x)) for x in files)
            state = 'suggest' if suggested else ('saved' if os.path.exists(label_path(f)) else '')
            cv2.putText(view, f'{i + 1}/{len(files)}  done {done}  {state}', (10, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(view, 'Enter=ok d=draw o=obstacle c=clear n=none b=back x=drop q=quit', (10, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.imshow(win, view)
            k = cv2.waitKey(0) & 0xFF
            if k in (13, 10, ord(' ')):
                write_label(label_path(f), boxes, w, h)
                prev_boxes = boxes
                i += 1
                break
            if k == ord('n'):
                write_label(label_path(f), [], w, h)
                prev_boxes = []
                i += 1
                break
            if k in (ord('d'), ord('o')):
                if suggested:
                    boxes, suggested = [], False
                x, y, bw, bh = cv2.selectROI(win, img, showCrosshair=False)
                if bw > 2 and bh > 2:
                    boxes.append((0 if k == ord('d') else 1, x, y, x + bw, y + bh))
            elif k == ord('c'):
                boxes, suggested = [], False
            elif k == ord('b'):
                i = max(0, i - 1)
                prev_boxes = []
                break
            elif k == ord('x'):
                open(skip_path(f), 'w').close()
                if os.path.exists(label_path(f)):
                    os.remove(label_path(f))
                i += 1
                break
            elif k in (ord('q'), 27):
                i = -1
                break
    cv2.destroyAllWindows()
    n_lab = len(glob.glob(os.path.join(lab, '*.txt')))
    n_pos = sum(1 for t in glob.glob(os.path.join(lab, '*.txt')) if os.path.getsize(t) > 0)
    print(f'라벨 {n_lab}장(대상 있음 {n_pos}, 없음 {n_lab - n_pos}) → {lab}')


if __name__ == '__main__':
    main()
