"""시연 사진 만들기: 열화상(정상 · 경고 · 비상)과 압력계(정상 · 주의 · 위험).

열화상 카메라 · 실물 압력계 대신 이 사진을 인쇄해(또는 화면에 띄워) 세워 두고 로봇의 일반 카메라로 본다.
학습 모델 없이 판독기가 색으로 읽도록, 판독기와 약속한 모양으로 그린다.

열화상(THERMAL palette 'rainbow', tempMin 15 · tempMax 300 · tempScale 'log' 로 읽는다)
  - 온도 장(°C)을 먼저 만들고 무지개 색표로 칠한다. 온도 범위를 15 ~ 300°C 로 고정해 같은 색이면 늘 같은 온도다.
  - normal: 실내(벽 · 바닥 · 분전반 · 선반)만 / warning: 분전반 차단기 하나가 과열(최고 약 190°C, 작은 영역)
    / emergency: 쓰레기통에서 오르는 불(최고 약 265°C, 큰 영역)
  - 오른쪽 검은 띠에 온도 막대(위 300 · 아래 15). 판독기는 바탕(파랑 · 하늘색) 사이에 낀 곳만 판으로 보므로 막대는 빠진다.
압력계(GAUGE style 'zone' 으로 읽는다)
  - 흰 눈금판 + 검은 테두리 + 굵은 초록(0 ~ 0.6) · 노랑(0.6 ~ 0.8) · 빨강(0.8 ~ 1.0) 띠 + 굵고 긴 검은 바늘, 0 ~ 1.0 MPa.
  - normal 0.35 · warning 0.70 · danger 0.90(각 구간 한가운데). 배경은 밝은 판(어둡게 찍혀도 테두리로 오인하지 않게).

사용(호스트에서): python3 demo_images.py            → ros/sim/src/models/photo_panels/materials/textures/ 에 6장
                  python3 demo_images.py --print 폴더  → 인쇄용(1280×960)도 그 폴더에
"""
import argparse
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
TEXTURES = HERE.parent / 'models' / 'photo_panels' / 'materials' / 'textures'
W, H = 640, 480

THERMAL_VARIANTS = ('normal', 'warning', 'emergency')
THERMAL_RANGE = (15.0, 300.0)            # °C, 로그 눈금
RAINBOW = [(0.00, (0, 0, 30)), (0.10, (20, 20, 160)), (0.22, (0, 90, 255)), (0.34, (0, 200, 255)),
           (0.46, (0, 230, 120)), (0.58, (200, 240, 0)), (0.70, (255, 200, 0)), (0.82, (255, 100, 0)),
           (0.93, (230, 0, 0)), (1.00, (255, 255, 255))]
GAUGE_VALUES = {'normal': 0.35, 'warning': 0.70, 'danger': 0.90}
GAUGE_ZONES = [(0.0, 0.6, (20, 165, 60)), (0.6, 0.8, (250, 195, 0)), (0.8, 1.0, (225, 25, 25))]


def _font(name, size):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        for f in ('DejaVuSans-Bold.ttf', 'DejaVuSans.ttf'):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
        return ImageFont.load_default()


def _rainbow(u):
    u = np.clip(u, 0, 1)
    out = np.zeros(u.shape + (3,), np.float32)
    for (a, ca), (b, cb) in zip(RAINBOW[:-1], RAINBOW[1:]):
        m = (u >= a) & (u <= b)
        t = ((u - a) / (b - a))[m][:, None]
        out[m] = np.array(ca, np.float32) * (1 - t) + np.array(cb, np.float32) * t
    return out.astype(np.uint8)


def thermal(variant, seed=7):
    """열화상 한 장 → (PIL 이미지, {'hotspot': (x, y) 픽셀, 'maxC': 최고 °C})."""
    if variant not in THERMAL_VARIANTS:
        raise ValueError(f'열화상 종류는 {THERMAL_VARIANTS}')
    rng = np.random.default_rng(seed)
    bar_w = 56
    sw = W - bar_w

    def smooth(scale, octaves=4):
        acc, amp, tot = np.zeros((H, sw), np.float32), 1.0, 0.0
        for o in range(octaves):
            s = max(2, int(scale / (2 ** o)))
            small = rng.random((H // s + 2, sw // s + 2)).astype(np.float32)
            big = np.array(Image.fromarray((small * 255).astype(np.uint8)).resize((sw + 2 * s, H + 2 * s), Image.BICUBIC),
                           np.float32)[:H, :sw] / 255.0
            acc += amp * big
            tot += amp
            amp *= 0.5
        return acc / tot

    def streaks(sx, sy, octaves=4):
        acc, amp, tot = np.zeros((H, sw), np.float32), 1.0, 0.0
        for o in range(octaves):
            kx, ky = max(2, int(sx / 2 ** o)), max(2, int(sy / 2 ** o))
            small = rng.random((H // ky + 2, sw // kx + 2)).astype(np.float32)
            big = np.array(Image.fromarray((small * 255).astype(np.uint8)).resize(((sw // kx + 2) * kx, (H // ky + 2) * ky),
                                                                                  Image.BICUBIC), np.float32)[:H, :sw] / 255.0
            acc += amp * big
            tot += amp
            amp *= 0.55
        return acc / tot

    yy, xx = np.mgrid[0:H, 0:sw].astype(np.float32)
    # 방: 벽 21 ~ 24°C, 바닥 19 ~ 21°C, 문틀 · 분전반 · 선반
    T = 21.0 + 2.5 * (1 - yy / H) + 0.8 * smooth(120)
    floor = yy > 340
    T[floor] = 19.5 + 1.0 * smooth(60)[floor]
    T[(xx > 40) & (xx < 60)] -= 1.5
    db = (xx > 70) & (xx < 190) & (yy > 120) & (yy < 300)
    T[db] = 24.0 + 1.5 * smooth(30)[db]
    T[(xx > 150) & (xx < 175) & (yy > 140) & (yy < 175)] = 38.0
    shelf = (xx > 430) & (xx < 560) & (yy > 180) & (yy < 340)
    T[shelf] = 18.0 + 0.6 * smooth(25)[shelf]
    # 불(쓰레기통 윗면 x≈300, y≈352 에서 솟는 불꽃 · 심부 · 뜨거운 공기). 종류와 관계없이 계산해 잡음 순서를 같게 둔다
    cx, cy = 300.0, 352.0
    dx, dy = xx - cx, yy - cy
    up = np.clip(-dy, 0, None)
    tongue = streaks(18, 70)
    flame = np.exp(-(dx / (22 + 0.30 * up)) ** 2) * np.exp(-(up / (95 + 90 * tongue)) ** 2) * (dy < 4)
    flame *= np.clip((tongue - 0.25) * 2.2, 0, 1.3)
    core = np.exp(-((dx / 26) ** 2 + ((dy + 18) / 26) ** 2))
    plume = np.exp(-(dx / (55 + 0.45 * up)) ** 2) * np.exp(-((yy - 140) / 85) ** 2) * (0.5 + 0.7 * smooth(50))
    fire = 420.0 * (1 - np.exp(-(330.0 * flame + 240.0 * core + 55.0 * plume) / 420.0))
    if variant == 'emergency':
        T = T + fire
        binbox = (np.abs(xx - cx) < 26) & (yy > cy) & (yy < cy + 40)
        T[binbox] = np.maximum(T[binbox], 95.0 + 60.0 * np.exp(-((yy[binbox] - cy) / 18) ** 2))
    elif variant == 'warning':                           # 분전반 차단기 하나가 과열
        T = T + 150.0 * np.exp(-(((xx - 160) / 26) ** 2 + ((yy - 165) / 30) ** 2))
    refl = floor & (np.abs(dx) < 140)
    T[refl] += 6.0 * np.exp(-(dx[refl] / 90) ** 2) * np.exp(-((yy[refl] - 370) / 60) ** 2)
    for _ in range(2):                                   # 살짝 흐리게(열화상 렌즈 느낌)
        P = np.pad(T, 1, mode='edge')
        T = sum(P[1 + a:1 + a + H, 1 + b:1 + b + sw] for a in (-1, 0, 1) for b in (-1, 0, 1)) / 9.0
    T += rng.normal(0, 0.15, T.shape).astype(np.float32)
    lo, hi = THERMAL_RANGE
    T = np.clip(T, lo, hi)
    img = np.zeros((H, W, 3), np.uint8)
    img[:, :sw] = _rainbow(np.log1p(T - lo) / np.log1p(hi - lo))
    img[40:H - 40, sw + 8:sw + 26] = _rainbow(np.linspace(1, 0, H - 80)[:, None].repeat(18, 1))
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    f = _font('arial.ttf', 14)
    d.text((sw + 4, 14), f'{hi:.0f}', fill=(255, 255, 255), font=f)
    d.text((sw + 4, H - 34), f'{lo:.0f}', fill=(255, 255, 255), font=f)
    d.text((sw + 28, H // 2 - 7), '°C', fill=(255, 255, 255), font=f)
    hy, hx = np.unravel_index(np.argmax(T), T.shape)
    return pil, {'hotspot': (int(hx), int(hy)), 'maxC': round(float(T.max()), 1)}


def gauge(state):
    """압력계 한 장 → PIL 이미지."""
    if state not in GAUGE_VALUES:
        raise ValueError(f'압력계 종류는 {tuple(GAUGE_VALUES)}')
    S = 4                                                 # 크게 그려 줄여서 매끄럽게
    cx, cy, R = 320 * S, 240 * S, 205 * S

    def ang(v):                                           # 값 → 화면 각도(오른쪽 0 · 반시계 +): 225° → 시계 방향 270°
        return 225.0 - 270.0 * v

    def pt(a_deg, r):
        a = math.radians(a_deg)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    big, unit = _font('arialbd.ttf', 34 * S), _font('arialbd.ttf', 30 * S)
    im = Image.new('RGB', (W * S, H * S), (218, 221, 225))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - R - 12 * S, cy - R - 12 * S, cx + R + 12 * S, cy + R + 12 * S], fill=(178, 181, 185))   # 은색 테
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(20, 20, 20))                                        # 검은 테두리
    rf = R * 0.92
    d.ellipse([cx - rf, cy - rf, cx + rf, cy + rf], fill=(250, 250, 247))                                 # 흰 눈금판
    for a0, a1, rgb in GAUGE_ZONES:                                                                       # 굵은 색 띠(0.62 ~ 0.92)
        d.pieslice([cx - rf, cy - rf, cx + rf, cy + rf], -ang(a0), -ang(a1), fill=rgb)
    ri = R * 0.62
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=(250, 250, 247))
    for k in (0.0, 0.6, 0.8, 1.0):                                                                        # 구간 경계 · 양 끝 굵은 눈금
        d.line([pt(ang(k), R * 0.60), pt(ang(k), R * 0.92)], fill=(20, 20, 20), width=7 * S)
    for k in (0.2, 0.4):
        d.line([pt(ang(k), R * 0.62), pt(ang(k), R * 0.72)], fill=(20, 20, 20), width=4 * S)
    for k, t in ((0.0, '0'), (0.5, '0.5'), (1.0, '1.0')):
        x, y = pt(ang(k), R * 0.47)
        d.text((x - d.textlength(t, font=big) / 2, y - 19 * S), t, fill=(20, 20, 20), font=big)
    d.text((cx - d.textlength('MPa', font=unit) / 2, cy + R * 0.42), 'MPa', fill=(20, 20, 20), font=unit)
    a = ang(GAUGE_VALUES[state])                                                                          # 바늘(0.78 까지)
    tip, tail = pt(a, R * 0.78), pt(a + 180, R * 0.15)
    perp = math.radians(a + 90)
    hw, tw = 11 * S, 4 * S
    d.polygon([(tail[0] + hw * math.cos(perp), tail[1] - hw * math.sin(perp)),
               (tip[0] + tw * math.cos(perp), tip[1] - tw * math.sin(perp)),
               (tip[0] - tw * math.cos(perp), tip[1] + tw * math.sin(perp)),
               (tail[0] - hw * math.cos(perp), tail[1] + hw * math.sin(perp))], fill=(10, 10, 10))
    d.ellipse([cx - 24 * S, cy - 24 * S, cx + 24 * S, cy + 24 * S], fill=(10, 10, 10))
    return im.resize((W, H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description='시연 사진(열화상 · 압력계) 만들기')
    ap.add_argument('--out', default=str(TEXTURES), help='시뮬레이션 사진 판 재질 폴더(기본)')
    ap.add_argument('--print', dest='print_dir', help='인쇄용(1280×960) 사본을 둘 폴더')
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    made = {f'thermal_{v}.png': thermal(v)[0] for v in THERMAL_VARIANTS}
    made.update({f'gauge_{s}.png': gauge(s) for s in GAUGE_VALUES})
    for name, im in made.items():
        im.save(out / name)
        if a.print_dir:
            p = pathlib.Path(a.print_dir)
            p.mkdir(parents=True, exist_ok=True)
            im.resize((1280, 960), Image.BICUBIC).save(p / name, dpi=(300, 300))
    print(f'{len(made)}장 → {out}' + (f' (인쇄용 → {a.print_dir})' if a.print_dir else ''))


if __name__ == '__main__':
    main()
