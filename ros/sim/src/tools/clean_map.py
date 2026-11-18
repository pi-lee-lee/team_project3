"""SLAM 지도 잡음 정리: 주변에 벽이 없는 고립된 점유 칸(잡음)을 빈 칸으로 바꾼다.

정적 지도의 점은 라이다로 지워지지 않고, 로봇 반경만큼 팽창되어 좁은 복도를 막는다.
실제 현장에서도 SLAM 지도를 저장한 뒤 잡음을 정리하는 단계를 거친다.
  사용: python3 clean_map.py /maps/site.pgm   (원본은 site.raw.pgm 으로 남긴다)
기준: 3x3 이웃 중 점유 칸이 자기 포함 2개 이하이고, 5x5 이웃에 미지(회색) 칸이 없는 점유 칸.
"""
import shutil
import sys
from pathlib import Path

OCC, FREE, UNKNOWN = 0, 254, 205


def read_pgm(path):
    data = Path(path).read_bytes()
    fields, i = [], 0
    while len(fields) < 4:
        j = data.index(b'\n', i)
        line, i = data[i:j], j + 1
        if not line.startswith(b'#'):
            fields += line.split()
    w, h = int(fields[1]), int(fields[2])
    return w, h, bytearray(data[i:i + w * h])


def clean(w, h, px):
    removed = 0
    out = bytearray(px)
    for r in range(2, h - 2):
        for c in range(2, w - 2):
            if px[r * w + c] != OCC:
                continue
            occ = sum(px[(r + dr) * w + c + dc] == OCC for dr in (-1, 0, 1) for dc in (-1, 0, 1))
            unknown = any(px[(r + dr) * w + c + dc] == UNKNOWN for dr in range(-2, 3) for dc in range(-2, 3))
            if occ <= 2 and not unknown:
                out[r * w + c] = FREE
                removed += 1
    return out, removed


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else '/maps/site.pgm')
    w, h, px = read_pgm(path)
    out, removed = clean(w, h, px)
    raw = path.with_suffix('.raw.pgm')
    if not raw.exists():
        shutil.copy(path, raw)
    path.write_bytes(f'P5\n{w} {h}\n255\n'.encode() + bytes(out))
    print(f'{path}: removed {removed} isolated cells (original kept as {raw.name})')


if __name__ == '__main__':
    main()
