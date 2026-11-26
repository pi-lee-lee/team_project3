#!/usr/bin/env python3
"""build_stereo_depth.py — 카메라 두 대로 거리를 재는 원리 설명서 6장 (거리 식 → P 행렬 → 평행화 → R · T → K · D → 순서).

    python3 docs/camera/build_stereo_depth.py        (numpy · opencv-python 필요)

젯봇 카메라 2대는 아직 보정 전이라, 숫자는 IMX219 사양으로 계산한 값과 가정값이다(아래 SPEC).
보정이 끝나면 SPEC 을 보정 결과로 바꾸고 다시 생성한다. K · D · R · T 를 넣으면 평행화 값(R1 R2 P1 P2)은
cv2.stereoRectify 로 이 스크립트가 직접 계산한다.

  stereo_depth_1_formula.svg   Z = f'B/d: 위에서 본 그림 · P 를 광축 위로 옮긴 직각삼각형 · 평행화된 두 영상의 xL, xR
  stereo_depth_2_values.svg    f' · B · cx' · cy' 가 P 행렬의 어느 칸인가, d -> Z 표와 1 px 오차, 직선거리
  stereo_depth_3_rectify.svg   평행화가 왜 필요한가: 원본(다른 행, 넓은 검색) vs 평행화 뒤(같은 행)
  stereo_depth_4_rt.svg        R · T: 같은 순간에 찍은 보드 쌍, |T| = B
  stereo_depth_5_camera.svg    카메라 한 대: K (fx fy cx cy), D (k1 k2 p1 p2 k3), calibrateCamera
  stereo_depth_6_chain.svg     거꾸로 따라간 사슬과 실제 순서
"""
import math
import os

import cv2
import numpy as np

OUTDIR = os.path.dirname(os.path.abspath(__file__))

FONT = "-apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif"
MONO = "Menlo, Consolas, monospace"
INK, GRAY, LINE, BG = "#1c1c1e", "#636366", "#d1d1d6", "#f2f2f7"
BLUE, ORANGE, ORANGE_D, GREEN, PURPLE, RED, MUTE = "#007aff", "#ff9500", "#b25000", "#248a3d", "#8944ab", "#e5352b", "#8e8e93"
TEAL = "#0a7c8c"

# ---------------------------------------------------------------------------------------------- 값
# IMX219: 초점거리 2.96 mm, 픽셀 1.12 um, 3280 x 2464. 640 x 360 으로 줄여 쓴다고 가정(가로 3280 -> 640, 5.125 배)
SPEC = dict(
    size=(640, 360),
    focal_mm=2.96, pixel_um=1.12, scale=3280 / 640,
    baseline_m=0.060,                   # 가정: 두 카메라 렌즈 중심 간격 (실측 뒤 교체)
    rot_deg=(-1.0, 0.8, 0.2),           # 가정: 두 카메라 사이 회전 (회전 벡터, 도)
)
W_IMG, H_IMG = SIZE = SPEC['size']
_f = SPEC['focal_mm'] / (SPEC['pixel_um'] / 1000 * SPEC['scale'])
KL = np.array([[_f, 0, W_IMG / 2], [0, _f, H_IMG / 2], [0, 0, 1]], dtype=float)
KR = KL.copy()
DL = np.zeros(5)                        # 보정 전이라 왜곡 계수를 모른다 -> 0
DR = np.zeros(5)
R_LR = cv2.Rodrigues(np.radians(np.array(SPEC['rot_deg'])))[0]
T_LR = R_LR @ np.array([-SPEC['baseline_m'], 0.0, 0.0])   # X_R = R X_L + T, 오른쪽 카메라 중심 = (B, 0, 0)
RL1, RR2, PL, PR, _Q, _, _ = cv2.stereoRectify(KL, DL, KR, DR, SIZE, R_LR, T_LR,
                                               flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
F = PL[0, 0]                       # rectified focal length f' (same in P_left and P_right)
CXP, CYP = PL[0, 2], PL[1, 2]      # rectified principal point cx', cy'
FB = -PR[0, 3]                     # f' * B
B = FB / F                         # baseline [m]
assert abs(PR[0, 0] - F) < 1e-9 and abs(PR[0, 2] - CXP) < 1e-9 and abs(PL[0, 3]) < 1e-12

# worked example: one point in front of the bar
EX_X, EX_Y, EX_Z = 0.040, 0.050, 0.600
XL = CXP + F * EX_X / EX_Z
XR = CXP + F * (EX_X - B) / EX_Z
V = CYP + F * EX_Y / EX_Z
DISP = XL - XR
assert abs(FB / DISP - EX_Z) < 1e-9
assert abs((XL - CXP) * EX_Z / F - EX_X) < 1e-9 and abs((V - CYP) * EX_Z / F - EX_Y) < 1e-9
EX_DIST = math.sqrt(EX_X ** 2 + EX_Y ** 2 + EX_Z ** 2)
print(f"f'={F:.2f} cx'={CXP:.2f} cy'={CYP:.2f} f'B={FB:.3f} B={B * 1000:.1f} mm  "
      f"xL={XL:.1f} xR={XR:.1f} d={DISP:.2f} v={V:.1f}  dist={EX_DIST:.3f}")


# ----------------------------------------------------------------------------------------------- svg
class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.o = w, h, []
        self.add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                 f'font-family="{FONT}" xml:space="preserve">')
        self.add("<defs>")
        for c in (INK, BLUE, ORANGE_D, GREEN, RED, MUTE, PURPLE, TEAL):
            self.add(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                     f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
        self.add("</defs>")
        self.rect(0, 0, w, h, BG, "none", 0, 0)

    def add(self, s):
        self.o.append(s)

    def text(self, x, y, t, size=14, weight=400, fill=INK, anchor="start", mono=False, italic=False):
        t = str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        fam = f' font-family="{MONO}"' if mono else ""
        it = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                 f'text-anchor="{anchor}"{fam}{it}>{t}</text>')

    def lines(self, x, y, rows, size=14, gap=None, **kw):
        gap = gap or size * 1.5
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, size, **kw)

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, sw=1.0, rx=10, dash=None, op=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' fill-opacity="{op}"' if op is not None else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{o} '
                 f'stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None, arrow=False, both=False):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#a{stroke[1:]})"' if arrow or both else ""
        m += f' marker-start="url(#a{stroke[1:]})"' if both else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{da}{m}/>')

    def path(self, d, stroke=INK, sw=1.4, fill="none", dash=None, arrow=False):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#a{stroke[1:]})"' if arrow else ""
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}{m}/>')

    def poly(self, pts, fill="none", stroke=INK, sw=1.0, closed=True, op=None, dash=None):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        o = f' fill-opacity="{op}"' if op is not None else ""
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<{tag} points="{p}" fill="{fill}"{o} stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def circle(self, x, y, r, fill=INK, stroke="none", sw=1.0, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def title(self, x, y, t, sub=None):
        self.text(x, y, t, 19, 700)
        if sub:
            self.text(x, y + 24, sub, 13.5, 400, GRAY)

    def save(self, name):
        with open(os.path.join(OUTDIR, name), "w") as fp:
            fp.write("\n".join(self.o + ["</svg>"]))
        print("wrote", name)


def camera_top(s, x, y, label, color, side=0):
    """Camera seen from above: body below the lens centre, lens centre = optical centre O."""
    s.rect(x - 26, y + 6, 52, 30, "#fff", color, 1.6, 4)
    s.poly([(x - 12, y + 6), (x + 12, y + 6), (x + 7, y), (x - 7, y)], "#fff", color, 1.6)
    s.circle(x, y, 4, color)
    s.text(x, y + 56, label, 13.5, 700, color, "middle") if side == 0 else \
        s.text(x + side * 34, y + 28, label, 13.5, 700, color, "end" if side < 0 else "start")


def image_frame(s, x0, y0, sc, title, color):
    """A 640 x 360 image drawn at scale sc with its own u (column) and v (row) axes."""
    w, h = W_IMG * sc, H_IMG * sc
    s.rect(x0, y0, w, h, "#fff", color, 1.8, 2)
    s.text(x0, y0 - 34, title, 14.5, 700, color)
    # u axis along the top edge, v axis along the left edge
    s.line(x0, y0 - 12, x0 + w + 18, y0 - 12, GRAY, 1.0, arrow=True)
    s.text(x0 + w + 22, y0 - 8, "u", 13, 700, GRAY, italic=True)
    for u in (0, 160, 320, 480, 640):
        s.line(x0 + u * sc, y0 - 15, x0 + u * sc, y0 - 9, GRAY, 1.0)
        s.text(x0 + u * sc, y0 - 19, u, 10.5, fill=GRAY, anchor="middle")
    s.line(x0 - 12, y0, x0 - 12, y0 + h + 18, GRAY, 1.0, arrow=True)
    s.text(x0 - 20, y0 + h + 18, "v", 13, 700, GRAY, "end", italic=True)
    for v in (0, 180, 360):
        s.line(x0 - 15, y0 + v * sc, x0 - 9, y0 + v * sc, GRAY, 1.0)
        s.text(x0 - 19, y0 + v * sc + 4, v, 10.5, fill=GRAY, anchor="end")
    return w, h


# ------------------------------------------------------------------------------------ 1. the formula
def right_angle(s, x, y, sx, sy, c, k=9):
    """Right-angle mark at (x, y); sx/sy = +1/-1 choose the quadrant (sy=+1 = below)."""
    s.poly([(x + sx * k, y), (x + sx * k, y + sy * k), (x, y + sy * k)], "none", c, 1.0, closed=False)


def fig_formula():
    W, H = 1120, 2066
    s = Svg(W, H)
    s.title(30, 38, "① 목표: 좌우 위치차 d 로 거리 Z 를 계산한다   Z = f′ · B / d",
            f"값은 젯봇 IMX219 사양으로 계산한 값 (640 × 360, 간격 B · 회전은 가정 — 보정 뒤 교체). "
            f"예: 점 P 가 X = {EX_X} m, Y = {EX_Y} m, Z = {EX_Z} m 에 있을 때")
    s.text(W - 30, 38, "② ~ ⑥ 그림 = 같은 폴더 stereo_depth_2 ~ 6_*.svg", 12, 700, GRAY, "end")

    # ---- (a) top view: schematic, not to scale (drawing shifted right inside a full-width panel)
    yb, ol, orr = 500, 200, 440          # baseline y, optical centres O_L, O_R (local drawing coordinates)
    fd, zd, xd = 110, 330, 100           # drawn f', Z, X
    yi = yb - fd                         # virtual image plane (drawn in front of the lens)
    py, px = yb - zd, ol + xd
    pl = ol + xd * fd / zd               # where the ray P -> O_L crosses the image plane
    pr = orr + (px - orr) * fd / zd
    prs = orr + (ol - orr) * fd / zd     # same for P* (P moved onto the left axis)

    def base(dy):
        """Axes, image planes, cameras and cx' marks shared by (a) and (b)."""
        for x in (ol, orr):
            s.line(x, yb, x, 140, MUTE, 1.0, "4 4")
        s.text(ol - 6, 150, "왼쪽 광축", 11.5, fill=MUTE, anchor="end")
        s.text(orr + 6, 150, "오른쪽 광축", 11.5, fill=MUTE)
        for x, c in ((ol, BLUE), (orr, ORANGE_D)):
            s.line(x - 85, yi, x + 85, yi, c, 3.0)
        s.text(ol - 88, yi - 8, "왼쪽 영상면", 11.5, 700, BLUE, "end")
        s.text(orr + 88, yi + 22, "오른쪽 영상면", 11.5, 700, ORANGE_D, "end")
        for x in (ol, orr):
            s.circle(x, yi, 3.5, INK)
        camera_top(s, ol, yb, "왼쪽 카메라 O_L", BLUE, -1)
        camera_top(s, orr, yb, "오른쪽 카메라 O_R", ORANGE_D, 1)

    s.rect(20, 80, 1080, 520, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "(가) 위에서 내려다본 그림 — 개략도, 축척 아님", 14.5, 700)
    s.lines(36, 136, ["점 P 에서 나온 빛이 두 렌즈 중심으로 간다.",
                      "그 직선이 영상면을 지나는 자리가",
                      "xL (왼쪽) · xR (오른쪽)이다.",
                      "",
                      "cx′ = 광축이 영상면을 지나는 자리"], 12.5, gap=21, fill=GRAY)
    s.add('<g transform="translate(220,0)">')
    base(0)
    s.line(ol + 55, yi + 12, ol + 85, yi + 12, GRAY, 1.0, arrow=True)
    s.text(ol + 89, yi + 16, "u", 12, 700, GRAY, italic=True)
    s.line(px, py, ol, yb, BLUE, 1.4)
    s.line(px, py, orr, yb, ORANGE_D, 1.4)
    s.circle(px, py, 6, RED)
    s.text(px, py - 14, "점 P (X, Y, Z)", 13.5, 700, RED, "middle")
    s.circle(pl, yi, 5.5, BLUE)
    s.circle(pr, yi, 5.5, ORANGE_D)
    s.text(ol, yi + 22, "cx′", 12, 700, INK, "middle")
    s.text(orr, yi + 22, "cx′", 12, 700, INK, "middle")
    s.line(ol, yi - 16, pl, yi - 16, BLUE, 1.6, arrow=True)
    s.text(ol - 4, yi - 30, "xL − cx′  (＋)", 12, 700, BLUE, "start")
    s.line(orr, yi - 16, pr, yi - 16, ORANGE_D, 1.6, arrow=True)
    s.text(orr - 6, yi - 30, "(－)  xR − cx′", 12, 700, ORANGE_D, "end")
    s.text(pl + 8, yi + 22, "xL", 13, 700, BLUE)
    s.text(pr - 8, yi + 22, "xR", 13, 700, ORANGE_D, "end")
    s.line(ol, yb + 72, orr, yb + 72, INK, 1.4, both=True)
    s.text((ol + orr) / 2, yb + 66, f"B = {B * 1000:.1f} mm  (두 렌즈 중심 사이, 기준선)", 12.5, 700, INK, "middle")
    s.line(ol - 110, yi, ol - 110, yb, PURPLE, 1.4, both=True)
    s.line(ol - 118, yi, ol - 85, yi, PURPLE, 0.8, "2 2")
    s.line(ol - 118, yb, ol - 26, yb, PURPLE, 0.8, "2 2")
    s.text(ol - 104, (yi + yb) / 2 + 5, "f′", 15, 700, PURPLE)
    zx = 590
    s.line(px, py, zx + 8, py, GREEN, 0.8, "2 2")
    s.line(orr + 26, yb, zx + 8, yb, GREEN, 0.8, "2 2")
    s.line(zx, py, zx, yb, GREEN, 1.6, both=True)
    s.text(zx + 8, (py + yb) / 2 - 8, "Z", 16, 700, GREEN)
    s.text(zx + 8, (py + yb) / 2 + 10, "기준선에", 11, fill=GREEN)
    s.text(zx + 8, (py + yb) / 2 + 24, "수직", 11, fill=GREEN)
    s.line(ol, py - 40, px, py - 40, TEAL, 1.4, both=True)
    s.line(px, py - 46, px, py - 6, TEAL, 0.8, "2 2")
    s.text((ol + px) / 2, py - 47, "X", 14, 700, TEAL, "middle")
    s.add('</g>')
    s.text(36, 588, "영상면은 렌즈 앞 f′ 위치에 그렸다 (실제 센서는 렌즈 뒤에 있고 상이 뒤집혀 찍힌다 — 계산은 같다)",
           11, fill=GRAY)

    # ---- (b) same top view, P moved sideways onto the left axis -> one right triangle at O_L
    XLS, XRS = CXP, CXP - DISP           # image columns after the move (X = 0)
    s.rect(20, 616, 1080, 530, "#fff", LINE, 1.0, 12)
    s.text(36, 642, "(나) 같은 그림에서 점 P 를 깊이 Z 그대로 왼쪽 광축(O_L – cx′ 선) 위로 옮기면 O_L 에서 직각인 삼각형이 생긴다",
           14.5, 700)
    s.lines(36, 680, ["P* = P 를 수평으로 옮겨 왼쪽 광축 위에",
                      "     놓은 점 (깊이 Z 는 그대로)",
                      "",
                      "옮기면 xL 과 xR 이 같은 만큼 움직여",
                      "d 는 바뀌지 않는다:"], 12.5, gap=21, fill=GRAY)
    s.text(36, 800, "", 12)
    for i, (lab, a_, b_, c_) in enumerate((("옮기기 전", XL, XR, XL - XR), ("옮긴 뒤", XLS, XRS, XLS - XRS))):
        y = 796 + i * 22
        s.text(36, y, lab, 12, 700, INK)
        s.text(104, y, f"xL {a_:.1f}  xR {b_:.1f}  d {c_:.2f}", 12, 700, RED if i else INK, mono=True)
    s.lines(36, 860, ["옮긴 뒤 xL = cx′ (광축 위의 점은",
                      "cx′ 에 찍힌다)",
                      "→ 거리 계산은 P* 로 해도 같다"], 12.5, gap=21, fill=GRAY)
    s.add('<g transform="translate(220,536)">')
    base(0)
    # big right triangle O_L - P* - O_R and the small one at the right camera
    s.poly([(ol, yb), (ol, py), (orr, yb)], GREEN, "none", op=0.10)
    s.poly([(orr, yb), (orr, yi), (prs, yi)], GREEN, "none", op=0.35)
    # the original P and its rays, faded
    s.line(px, py, ol, yb, BLUE, 1.0, "3 4")
    s.line(px, py, orr, yb, ORANGE_D, 1.0, "3 4")
    s.circle(px, py, 6, "none", RED, 1.4, "2 2")
    s.text(px + 10, py - 10, "원래 P", 12, fill=RED)
    s.circle(pl, yi, 4.5, "none", BLUE, 1.2, "2 2")
    s.circle(pr, yi, 4.5, "none", ORANGE_D, 1.2, "2 2")
    # move arrow P -> P*
    s.line(px - 8, py, ol + 10, py, RED, 1.6, arrow=True)
    s.text((ol + px) / 2, py - 10, "옮김 (Z 그대로)", 11.5, 700, RED, "middle")
    # new rays from P*
    s.line(ol, py, ol, yb, BLUE, 2.2)
    s.line(ol, py, orr, yb, ORANGE_D, 2.2)
    s.circle(ol, py, 6.5, RED)
    s.text(ol - 10, py + 22, "P*", 15, 700, RED, "end")
    # image points after the move and their shift
    s.circle(ol, yi, 5.5, BLUE)
    s.text(ol + 8, yi + 22, "xL = cx′", 12.5, 700, BLUE)
    s.line(pl, yi - 14, ol + 3, yi - 14, BLUE, 1.0, arrow=True)
    s.circle(prs, yi, 5.5, ORANGE_D)
    s.text(prs - 6, yi + 22, "xR", 13, 700, ORANGE_D, "end")
    s.line(pr, yi - 14, prs + 3, yi - 14, ORANGE_D, 1.0, arrow=True)
    s.text(orr + 6, yi - 8, "cx′", 12, 700, INK)
    # leg labels: small triangle (d, f'), big triangle (B, Z)
    s.line(orr, yi - 42, prs, yi - 42, RED, 2.0, both=True)
    s.line(prs, yi - 50, prs, yi - 6, RED, 0.8, "2 2")
    s.line(orr, yi - 50, orr, yi - 6, RED, 0.8, "2 2")
    s.text((orr + prs) / 2, yi - 50, "d", 16, 700, RED, "middle")
    s.line(orr + 100, yi, orr + 100, yb, PURPLE, 1.4, both=True)
    s.line(orr + 26, yi, orr + 108, yi, PURPLE, 0.8, "2 2")
    s.line(orr + 26, yb, orr + 108, yb, PURPLE, 0.8, "2 2")
    s.text(orr + 108, (yi + yb) / 2 + 5, "f′", 15, 700, PURPLE)
    s.line(ol - 40, py, ol - 40, yb, GREEN, 1.6, both=True)
    s.line(ol - 48, py, ol - 6, py, GREEN, 0.8, "2 2")
    s.text(ol - 48, (py + yb) / 2 - 30, "Z", 16, 700, GREEN, "end")
    s.line(ol, yb + 14, orr, yb + 14, INK, 2.0)
    s.text((ol + orr) / 2, yb + 32, "B (밑변)", 14, 700, INK, "middle")
    right_angle(s, ol, yb, 1, -1, GREEN, 12)
    right_angle(s, orr, yi, -1, 1, GREEN, 9)
    s.add('</g>')
    # equations on the right
    ex = 800
    s.text(ex, 690, "큰 직각삼각형  O_L · P* · O_R", 13, 700, GREEN)
    s.text(ex, 712, "  세로 Z,  밑변 B (두 카메라 간격)", 12.5)
    s.text(ex, 744, "작은 직각삼각형  cx′ · xR · O_R", 13, 700, GREEN)
    s.text(ex, 766, "  세로 f′,  밑변 d", 12.5)
    s.lines(ex, 798, ["두 빗변이 같은 직선 P* → O_R 위에 있고",
                      "세로끼리 · 밑변끼리 평행 → 모양이 같다"], 12, gap=20, fill=GRAY)
    s.rect(ex - 4, 842, 286, 36, "#fff", RED, 1.2, 6)
    s.text(ex + 10, 866, "d / f′  =  B / Z", 16, 700, RED, mono=True)
    s.text(ex, 900, "Z 에 대해 정리하면", 12, fill=GRAY)
    s.rect(ex - 4, 910, 286, 40, "#eaf6ec", GREEN, 1.6, 6)
    s.text(ex + 10, 937, "Z  =  f′ · B / d", 18, 700, GREEN, mono=True)
    s.text(ex, 978, "이 예의 값:", 12, fill=GRAY)
    s.text(ex, 1000, f"d / f′ = {DISP:.2f} / {F:.2f} = {DISP / F:.4f}", 12, mono=True)
    s.text(ex, 1020, f"B / Z  = {B:.4f} / {EX_Z:.3f} = {B / EX_Z:.4f}", 12, mono=True)
    s.text(ex, 1040, f"Z = {FB:.2f} / {DISP:.2f} = {FB / DISP:.3f} m", 12, 700, GREEN, mono=True)
    s.lines(ex, 1072, ["B 가 비율의 밑변 기준값이다:",
                       "간격 B 가 길수록 같은 Z 에서 d 가 커진다."], 12, gap=20, fill=GRAY)

    # ---- (c) the same result by subtracting the two triangle equations of (a)
    s.rect(20, 1162, 1080, 148, "#fff", LINE, 1.0, 12)
    s.text(36, 1188, "(다) 식으로 확인 — P 를 옮기지 않고 (가) 의 두 카메라 식을 빼도 같은 식이 나온다", 14.5, 700)
    s.text(52, 1224, "xL − cx′ = f′·X/Z", 13.5, 700, BLUE, mono=True)
    s.text(226, 1224, "−", 16, 700, INK, mono=True)
    s.text(250, 1224, "xR − cx′ = f′·(X − B)/Z", 13.5, 700, ORANGE_D, mono=True)
    s.text(470, 1224, "⇒", 16, 700, INK)
    s.rect(496, 1204, 250, 30, "#fff", RED, 1.2, 6)
    s.text(508, 1224, "d = xL − xR = f′·B/Z", 13.5, 700, RED, mono=True)
    s.text(760, 1224, "⇒", 16, 700, INK)
    s.rect(786, 1200, 210, 38, "#eaf6ec", GREEN, 1.6, 6)
    s.text(800, 1226, "Z = f′ · B / d", 17, 700, GREEN, mono=True)
    s.text(52, 1266, "왼쪽 식: (가) 에서 O_L · cx′ · xL 과 O_L · (광축 위 깊이 Z) · P 가 같은 모양. 오른쪽 식도 O_R 쪽에서 같다 (X − B 는 음수).",
           12, fill=GRAY)
    s.text(52, 1290, "빼면 cx′ 와 X 가 지워진다 — X 가 지워지는 것이 (나) 에서 P 를 옆으로 옮겨도 d 가 그대로인 이유다. "
                     "cx′ 가 좌우 같은 이유는 (라) 의 평행화.", 12, fill=GRAY)

    s.add('<g transform="translate(0,696)">')
    # ---- (c) the two rectified images
    s.rect(20, 620, 1080, 480, "#fff", LINE, 1.0, 12)
    s.text(36, 646, "(라) 평행화된 두 영상에서 xL · xR 의 위치 — 각 영상의 왼쪽 끝이 u = 0, 위쪽 끝이 v = 0", 14.5, 700)
    sc = 0.65
    lx0, rx0, y0 = 90, 610, 740
    w, h = image_frame(s, lx0, y0, sc, "왼쪽 영상 (평행화 뒤, 640 × 360)", BLUE)
    image_frame(s, rx0, y0, sc, "오른쪽 영상 (평행화 뒤, 640 × 360)", ORANGE_D)
    for x0 in (lx0, rx0):
        cx = x0 + CXP * sc
        s.line(cx, y0, cx, y0 + h, INK, 1.1, "5 4")
        s.text(cx + 4, y0 + 16, f"cx′ = {CXP:.1f}", 11.5, 700, INK)
    # common row v across both frames
    vy = y0 + V * sc
    s.line(lx0 - 4, vy, rx0 + w + 4, vy, GREEN, 1.0, "3 3")
    s.text(lx0 + w - 6, vy - 6, f"같은 행 v = {V:.1f}", 12, 700, GREEN, "end")
    s.text(rx0 + 6, vy - 6, f"v = {V:.1f}", 12, 700, GREEN)
    # left point and offset
    xl = lx0 + XL * sc
    s.circle(xl, vy, 6, BLUE)
    s.line(lx0 + CXP * sc, vy + 22, xl, vy + 22, BLUE, 1.6, arrow=True)
    s.text(xl + 6, vy + 40, f"xL − cx′ = +{XL - CXP:.1f}", 12, 700, BLUE)
    s.line(xl, vy - 28, xl, vy - 9, BLUE, 1.2, arrow=True)
    s.text(xl + 4, vy - 32, f"xL = {XL:.1f}", 13, 700, BLUE, "start")
    # left: distance from the left edge
    s.line(lx0, y0 + h + 26, xl, y0 + h + 26, BLUE, 1.2, both=True)
    s.text((lx0 + xl) / 2, y0 + h + 44, "xL = 왼쪽 영상의 왼쪽 끝(u = 0)부터 센 열 번호", 11.5, fill=BLUE, anchor="middle")
    # right point, ghost of xL, offset and d
    xr = rx0 + XR * sc
    gx = rx0 + XL * sc
    s.circle(gx, vy, 6, "none", BLUE, 1.4, "2 2")
    s.text(gx + 8, vy - 34, f"u = {XL:.1f} (xL 자리)", 11.5, fill=BLUE)
    s.circle(xr, vy, 6, ORANGE_D)
    s.line(xr, vy - 28, xr, vy - 9, ORANGE_D, 1.2, arrow=True)
    s.text(xr - 4, vy - 32, f"xR = {XR:.1f}", 13, 700, ORANGE_D, "end")
    s.line(rx0 + CXP * sc, vy + 22, xr, vy + 22, ORANGE_D, 1.6, arrow=True)
    s.text(xr - 6, vy + 40, f"xR − cx′ = {XR - CXP:.1f}", 12, 700, ORANGE_D, "end")
    s.line(gx, vy + 58, xr, vy + 58, RED, 2.0, arrow=True)
    s.text(gx + 6, vy + 63, f"d = xL − xR = {DISP:.2f} px", 13.5, 700, RED)
    s.line(rx0, y0 + h + 26, xr, y0 + h + 26, ORANGE_D, 1.2, both=True)
    s.text((rx0 + xr) / 2, y0 + h + 44, "xR = 오른쪽 영상의 왼쪽 끝(u = 0)부터 센 열 번호", 11.5, fill=ORANGE_D,
           anchor="middle")
    s.text(36, 1056, "같은 점 P 가 오른쪽 영상에서는 xL 보다 왼쪽(작은 u)에 찍힌다. 그 차이가 좌우 위치차 d. "
                    "가까운 점일수록 d 가 크다.", 12.5, fill=GRAY)
    s.text(36, 670, "(가) · (나) · (다) 의 계산이 수행되려면 먼저 두 영상을 평행화해야 한다 — 좌우 cx′ 가 같고, 같은 점이 두 영상의 같은 행에 있어야 식이 성립한다. "
                     "원본 영상은 평행하지 않다 (③ 그림 = stereo_depth_3_rectify.svg).", 12.5, 700, RED)
    s.text(36, 1078, f"평행화 = 촬영한 원본 영상을 매 프레임 계산으로 회전 · 왜곡 보정해, 두 카메라가 정확히 평행하게 찍은 영상으로 바꾸는 작업. "
                     f"이 그림은 두 카메라가 약 {abs(RVEC_DEG[0]):.1f}° · {abs(RVEC_DEG[1]):.1f}° 틀어져 있다고 가정했다 (③ 그림 = stereo_depth_3_rectify.svg).", 11.5, fill=RED)

    # ---- (d) variable table
    s.rect(20, 1118, 1080, 238, "#fff", LINE, 1.0, 12)
    cols = [36, 124, 520, 590, 900]
    heads = ["기호", "뜻", "단위", "어디서 얻는가", "이 예의 값"]
    for x, t in zip(cols, heads):
        s.text(x, 1144, t, 12.5, 700, GRAY)
    rows = [
        ("Z", GREEN, "깊이: 기준선에서 점까지, 광축 방향 거리", "m", "계산 결과", f"{EX_Z:.3f}"),
        ("d", RED, "좌우 위치차 = xL − xR", "px", "SGBM 이 같은 행을 훑어 찾음", f"{DISP:.2f}"),
        ("xL", BLUE, "왼쪽 영상에서 점이 찍힌 열 (u, 왼쪽 끝 = 0)", "px", "평행화된 왼쪽 영상", f"{XL:.1f}"),
        ("xR", ORANGE_D, "오른쪽 영상에서 같은 점이 찍힌 열", "px", "평행화된 오른쪽 영상", f"{XR:.1f}"),
        ("f′", PURPLE, "평행화된 영상의 초점거리 (K 의 fx 와 다름)", "px", "P[0,0] — ② 그림", f"{F:.2f}"),
        ("B", INK, "두 렌즈 중심 사이 거리 (기준선)", "m", "−P_right[0,3] / f′ — ② 그림", f"{B:.4f}"),
        ("cx′", INK, "광축이 영상에 닿는 열 (좌우 같음)", "px", "P[0,2] — ② 그림", f"{CXP:.2f}"),
        ("X · Y · v", TEAL, "점의 가로 · 세로 위치, 점이 찍힌 행 (좌우 같음)", "m · m · px", "직선거리 계산 — ② 그림 아래", f"{EX_X} · {EX_Y} · {V:.1f}"),
    ]
    for i, (sym, c, mean, unit, src, val) in enumerate(rows):
        y = 1170 + i * 23
        s.text(cols[0], y, sym, 13.5, 700, c, mono=True)
        s.text(cols[1], y, mean, 12.5)
        s.text(cols[2], y, unit, 12.5, fill=GRAY)
        s.text(cols[3], y, src, 12.5, fill=GRAY)
        s.text(cols[4], y, val, 12.5, 700, mono=True)
    s.add('</g>')
    s.save("stereo_depth_1_formula.svg")


# ----------------------------------------------------------------------------- derived real values
# rectified-left frame -> each raw camera frame:  X_rectL = R1 X_L,  X_rectR = R2 X_R = X_rectL - (B, 0, 0)
EX_P = np.array([EX_X, EX_Y, EX_Z])
P_CAML = RL1.T @ EX_P
P_CAMR = RR2.T @ (EX_P - np.array([B, 0.0, 0.0]))


def project_raw(pc, K, D):
    uv, _ = cv2.projectPoints(pc.reshape(1, 1, 3), np.zeros(3), np.zeros(3), K, D)
    return uv.ravel()


RAW_L = project_raw(P_CAML, KL, DL)
RAW_R = project_raw(P_CAMR, KR, DR)
# going back through undistortPoints with R and P must land on xL / xR on row v
_bl = cv2.undistortPoints(RAW_L.reshape(1, 1, 2), KL, DL, R=RL1, P=PL).ravel()
_br = cv2.undistortPoints(RAW_R.reshape(1, 1, 2), KR, DR, R=RR2, P=PR).ravel()
assert abs(_bl[0] - XL) < 0.05 and abs(_bl[1] - V) < 0.05 and abs(_br[0] - XR) < 0.05 and abs(_br[1] - V) < 0.05
RVEC_DEG = np.degrees(cv2.Rodrigues(R_LR)[0].ravel())
assert abs(np.linalg.norm(T_LR) - B) < 1e-6
print(f"raw L {RAW_L.round(1)}  raw R {RAW_R.round(1)}  R deg {RVEC_DEG.round(3)}  T {T_LR.round(5)}")


def matrix(s, x, y, rows, cw, title, color, marks=None, size=13):
    """Draw a matrix with brackets; marks = {(r, c): (colour, label)} highlights cells."""
    marks = marks or {}
    nr, nc = len(rows), len(rows[0])
    rh = 26
    s.text(x, y - 10, title, 13.5, 700, color)
    s.path(f"M{x + 8},{y} L{x},{y} L{x},{y + nr * rh + 6} L{x + 8},{y + nr * rh + 6}", INK, 1.4)
    xe = x + 14 + nc * cw
    s.path(f"M{xe - 8},{y} L{xe},{y} L{xe},{y + nr * rh + 6} L{xe - 8},{y + nr * rh + 6}", INK, 1.4)
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            cx = x + 8 + c * cw + cw / 2
            cy = y + 20 + r * rh
            if (r, c) in marks:
                col, _lab = marks[(r, c)]
                s.rect(cx - cw / 2 + 3, cy - 16, cw - 6, 22, col, col, 1.2, 4, op=0.14)
                s.text(cx, cy, v, size, 700, col, "middle", mono=True)
            else:
                s.text(cx, cy, v, size, 400, GRAY, "middle", mono=True)
    return xe, y + nr * rh + 6


def fmt(v):
    return "0" if abs(v) < 1e-12 else ("1" if abs(v - 1) < 1e-12 else f"{v:.2f}")


# --------------------------------------------------------------------- 2. where f', B, cx', cy' live
def fig_values():
    W, H = 1120, 1060
    s = Svg(W, H)
    s.title(30, 38, "② f′ 와 B 는 캘리브레이션 파일의 P 행렬(projection_matrix)에 들어 있다",
            "스테레오 보정 결과(camera_info 의 projection_matrix)에 들어갈 값. 지금은 사양 계산값 + 가정값으로 cv2.stereoRectify 를 돌린 결과")
    s.rect(20, 80, 1080, 400, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "(가) 두 파일의 projection_matrix (3 × 4)", 14.5, 700)
    marks_l = {(0, 0): (PURPLE, "f′"), (1, 1): (PURPLE, "f′"), (0, 2): (INK, "cx′"), (1, 2): (TEAL, "cy′")}
    marks_r = dict(marks_l)
    marks_r[(0, 3)] = (RED, "−f′B")
    xe, ye = matrix(s, 60, 150, [[fmt(v) for v in r] for r in PL], 86, "P_left  (왼쪽 카메라)", BLUE, marks_l)
    matrix(s, 580, 150, [[fmt(v) for v in r] for r in PR], 86, "P_right  (오른쪽 카메라)", ORANGE_D, marks_r)
    # labels below the matrices
    lab = [(PURPLE, f"[0,0] = [1,1] = f′ = {F:.2f} px", "평행화된 영상의 초점거리 (좌우 같음)"),
           (INK, f"[0,2] = cx′ = {CXP:.2f} px", "광축이 닿는 열 (좌우 같음)"),
           (TEAL, f"[1,2] = cy′ = {CYP:.2f} px", "광축이 닿는 행 (좌우 같음)")]
    for i, (c, a, b) in enumerate(lab):
        s.text(60, 270 + i * 26, a, 13, 700, c, mono=True)
        s.text(370, 270 + i * 26, b, 12.5, fill=GRAY)
    s.text(580, 270, f"[0,3] = −f′ · B = {PR[0, 3]:.2f}", 13, 700, RED, mono=True)
    s.text(580, 296, "왼쪽 파일의 [0,3] 은 0 — 왼쪽 카메라가 기준이라서", 12.5, fill=GRAY)
    s.rect(580, 318, 500, 72, "#fdeceb", RED, 1.2, 8)
    s.text(596, 344, f"B = −P_right[0,3] / f′ = {FB:.2f} / {F:.2f}", 14, 700, RED, mono=True)
    s.text(596, 372, f"  = {B:.4f} m = {B * 1000:.1f} mm   ← 자로 잰 렌즈 간격과 비교", 14, 700, RED, mono=True)
    s.rect(36, 404, 1048, 64, "#f7f0fb", PURPLE, 1.0, 8)
    s.text(52, 428, f"K 의 fx(왼쪽 {KL[0, 0]:.2f} · 오른쪽 {KR[0, 0]:.2f})는 원본 영상의 초점거리, P 의 f′({F:.2f})는 평행화된 영상의 초점거리다.",
           13, 700, PURPLE)
    s.text(52, 452, "평행화는 영상을 회전하고, 빈 가장자리가 없도록 확대한다(alpha=0). 좌우 위치차 d 는 평행화된 영상에서 재므로 거리 식에는 f′ 를 쓴다.",
           12.5, fill=INK)

    # (b) d -> Z table and curve
    s.rect(20, 496, 1080, 330, "#fff", LINE, 1.0, 12)
    s.text(36, 522, f"(나) Z = f′ · B / d = {FB:.2f} / d  — 매 프레임 바뀌는 값은 d 하나", 14.5, 700)
    gx0, gy0, gw, gh = 90, 560, 520, 220
    s.line(gx0, gy0 + gh, gx0 + gw + 10, gy0 + gh, INK, 1.2, arrow=True)
    s.line(gx0, gy0 + gh, gx0, gy0 - 10, INK, 1.2, arrow=True)
    s.text(gx0 + gw + 14, gy0 + gh + 4, "d [px]", 12.5, 700, RED)
    s.text(gx0, gy0 - 16, "Z [m]", 12.5, 700, GREEN, "middle")
    dmax, zmax = 110.0, 4.0
    X_ = lambda d: gx0 + d / dmax * gw
    Y_ = lambda z: gy0 + gh - z / zmax * gh
    for d in (0, 20, 40, 60, 80, 100):
        s.line(X_(d), gy0 + gh, X_(d), gy0 + gh + 5, GRAY, 1.0)
        s.text(X_(d), gy0 + gh + 19, d, 11, fill=GRAY, anchor="middle")
    for z in (0, 1, 2, 3, 4):
        s.line(gx0 - 5, Y_(z), gx0, Y_(z), GRAY, 1.0)
        s.text(gx0 - 9, Y_(z) + 4, z, 11, fill=GRAY, anchor="end")
        if z:
            s.line(gx0, Y_(z), gx0 + gw, Y_(z), LINE, 0.6, "2 3")
    pts = [(X_(d), Y_(FB / d)) for d in np.linspace(FB / zmax, dmax, 120)]
    s.poly(pts, "none", GREEN, 2.2, closed=False)
    table = [(0.6, ), (1.0, ), (2.0, ), (4.0, ), (10.0, )]
    for (z,) in table[:4]:
        d = FB / z
        s.circle(X_(d), Y_(z), 4.5, RED)
    tx = 660
    for i, t in enumerate(["거리 Z", "좌우 위치차 d", "d 가 1 px 틀리면 Z 오차"]):
        s.text(tx + [0, 90, 230][i], 566, t, 12.5, 700, GRAY)
    for i, (z,) in enumerate(table):
        d = FB / z
        dz = z * z / FB
        y = 594 + i * 28
        s.text(tx, y, f"{z:.1f} m", 13.5, 700, GREEN, mono=True)
        s.text(tx + 90, y, f"{d:.1f} px", 13.5, 700, RED, mono=True)
        s.text(tx + 230, y, f"약 {dz * 100:.1f} cm" if dz < 1 else f"약 {dz:.2f} m", 13.5, mono=True)
    s.text(tx, 748, "오차 ≈ Z² / (f′ · B)  — 거리가 2 배면 오차는 4 배", 12.5, fill=GRAY)
    s.text(tx, 772, "멀수록 d 가 작아져 1 px 의 무게가 커진다", 12.5, fill=GRAY)
    s.text(36, 812, f"곡선 위 빨간 점 = 오른쪽 표의 0.6 · 1 · 2 · 4 m (10 m 는 그래프 밖).  ① 그림의 예는 d = {DISP:.1f} px, Z = {EX_Z} m 인 점.",
           12, fill=GRAY)

    # (c) Z -> position and straight-line distance
    s.rect(20, 842, 1080, 200, "#fff", LINE, 1.0, 12)
    s.text(36, 868, "(다) Z 는 '광축 방향 깊이'다. 점까지의 직선거리는 X · Y 를 함께 구해서 계산한다", 14.5, 700)
    rows = [
        (TEAL, "X = (xL − cx′) · Z / f′", f"= ({XL:.1f} − {CXP:.1f}) × {EX_Z} / {F:.1f} = {EX_X:.3f} m", "가로 (오른쪽 +)"),
        (TEAL, "Y = (v − cy′) · Z / f′", f"= ({V:.1f} − {CYP:.1f}) × {EX_Z} / {F:.1f} = {EX_Y:.3f} m", "세로 (아래 +)"),
        (GREEN, "직선거리 = √(X² + Y² + Z²)", f"= √({EX_X}² + {EX_Y}² + {EX_Z}²) = {EX_DIST:.3f} m", "왼쪽 카메라에서 점까지"),
    ]
    for i, (c, a, b, n) in enumerate(rows):
        y = 904 + i * 34
        s.text(52, y, a, 14, 700, c, mono=True)
        s.text(380, y, b, 13.5, mono=True)
        s.text(900, y, n, 12.5, fill=GRAY)
    s.text(52, 1022, "v 는 점이 찍힌 행, cy′ 는 광축이 닿는 행 — 둘 다 ① 그림 (다) 와 위 P 행렬에 있다.", 12, fill=GRAY)
    s.save("stereo_depth_2_values.svg")


# --------------------------------------------------------------------------------- 3. rectification
def fig_rectify():
    W, H = 1120, 1150
    s = Svg(W, H)
    s.title(30, 38, "③ 좌우 위치차 d 를 재려면 먼저 평행화한다 — R1 · R2 · P1 · P2",
            "같은 점 P(① 그림의 예)가 원본 영상과 평행화된 영상에서 어디에 찍히는지. 좌표는 위 K · D · R · P 로 계산한 값 (왜곡은 보정 전이라 0)")
    sc = 0.6

    # (a) raw pair
    s.rect(20, 80, 1080, 380, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "(가) 원본 영상 — 렌즈 왜곡이 남아 있고 두 카메라가 조금 비뚤게 붙어 있다", 14.5, 700)
    lx0, rx0, y0 = 90, 610, 176
    w, h = image_frame(s, lx0, y0, sc, "왼쪽 원본 영상", BLUE)
    image_frame(s, rx0, y0, sc, "오른쪽 원본 영상", ORANGE_D)
    ul, vl = RAW_L
    ur, vr = RAW_R
    s.circle(lx0 + ul * sc, y0 + vl * sc, 5.5, BLUE)
    s.text(lx0 + ul * sc + 9, y0 + vl * sc - 8, f"(u, v) = ({ul:.1f}, {vl:.1f})", 12, 700, BLUE)
    s.circle(rx0 + ur * sc, y0 + vr * sc, 5.5, ORANGE_D)
    s.text(rx0 + ur * sc + 9, y0 + vr * sc + 18, f"(u, v) = ({ur:.1f}, {vr:.1f})", 12, 700, ORANGE_D)
    s.line(lx0, y0 + vl * sc, rx0 + w, y0 + vl * sc, BLUE, 0.8, "3 3")
    # 2D search area in the right raw image
    s.rect(rx0 + 20, y0 + vl * sc - 40, ur * sc + 40, 80, ORANGE, ORANGE_D, 1.0, 4, "4 3", op=0.12)
    s.text(rx0 + 26, y0 + vl * sc + 56, "어느 행에 있는지 모르므로 넓은 영역을 뒤져야 한다", 12, 700, ORANGE_D)
    s.text(36, 444, f"같은 점의 행: 왼쪽 v = {vl:.1f}, 오른쪽 v = {vr:.1f} — {abs(vl - vr):.1f} px 어긋난다. "
                    "어긋남은 두 카메라의 비뚤어짐과 렌즈 왜곡에서 온다.", 12.5, fill=GRAY)

    # (b) what happens to one pixel
    s.rect(20, 476, 1080, 230, "#fff", LINE, 1.0, 12)
    s.text(36, 502, "(나) 원본 픽셀 하나가 평행화된 픽셀이 되는 과정 (cv2.undistortPoints · cv2.initUndistortRectifyMap)", 14.5, 700)
    boxes = [("원본 픽셀", "(u, v)", INK),
             ("K, D 로 왜곡을 없애", "방향 (x, y, 1)", PURPLE),
             ("R1 (오른쪽은 R2)", "로 방향을 회전", BLUE),
             ("P1 (오른쪽은 P2)", "로 다시 픽셀로", RED),
             ("평행화된 픽셀", "(xL, v) · (xR, v)", GREEN)]
    bx, bw = 36, 190
    for i, (a, b, c) in enumerate(boxes):
        x = bx + i * (bw + 22)
        s.rect(x, 520, bw, 62, "#fff", c, 1.4, 8)
        s.text(x + bw / 2, 546, a, 13, 700, c, "middle")
        s.text(x + bw / 2, 568, b, 12.5, fill=INK, anchor="middle")
        if i:
            s.line(x - 20, 551, x - 3, 551, INK, 1.4, arrow=True)
    s.text(52, 614, f"왼쪽:  ({ul:.1f}, {vl:.1f})  →  ({XL:.1f}, {V:.1f})", 13.5, 700, BLUE, mono=True)
    s.text(52, 638, f"오른쪽: ({ur:.1f}, {vr:.1f})  →  ({XR:.1f}, {V:.1f})", 13.5, 700, ORANGE_D, mono=True)
    s.text(560, 614, "R1 · R2 · P1 · P2 를 만드는 함수:", 12.5, 700)
    s.text(560, 638, "cv2.stereoRectify(K1, D1, K2, D2, size, R, T)", 12.5, fill=BLUE, mono=True)
    s.text(560, 662, "  → R1, R2, P1, P2  (YAML 의 rectification_matrix", 12.5, mono=True)
    s.text(560, 682, "     · projection_matrix 로 저장)", 12.5, mono=True)
    s.text(52, 682, "입력 K · D 는 ⑤ 그림, R · T 는 ④ 그림에서 온다.", 12.5, fill=GRAY)

    # (c) rectified pair and the 1D search
    s.rect(20, 722, 1080, 412, "#fff", LINE, 1.0, 12)
    s.text(36, 748, "(다) 평행화된 영상 — 같은 점이 같은 행 v 에 온다. 그래서 짝을 그 한 줄에서만 찾는다", 14.5, 700)
    y0 = 820
    image_frame(s, lx0, y0, sc, "왼쪽 (평행화 뒤)", BLUE)
    image_frame(s, rx0, y0, sc, "오른쪽 (평행화 뒤)", ORANGE_D)
    vy = y0 + V * sc
    s.line(lx0, vy, rx0 + w, vy, GREEN, 0.9, "3 3")
    s.text(lx0 + w - 4, vy - 8, f"v = {V:.1f}", 12, 700, GREEN, "end")
    xl, xr, gx = lx0 + XL * sc, rx0 + XR * sc, rx0 + XL * sc
    s.rect(xl - 7, vy - 7, 14, 14, "none", BLUE, 1.6, 2)
    s.circle(xl, vy, 4, BLUE)
    s.text(xl, vy + 26, f"xL = {XL:.1f}", 12.5, 700, BLUE, "middle")
    s.text(xl, vy + 44, "작은 블록", 11.5, fill=BLUE, anchor="middle")
    # search band
    band_l = max(rx0, gx - 100 * sc)
    s.rect(band_l, vy - 7, gx - band_l, 14, GREEN, GREEN, 1.0, 2, op=0.18)
    s.circle(gx, vy, 5, "none", BLUE, 1.3, "2 2")
    s.text(gx + 8, vy - 12, "d = 0 (xL 자리)", 11.5, fill=BLUE)
    s.rect(xr - 7, vy - 7, 14, 14, "none", ORANGE_D, 1.8, 2)
    s.circle(xr, vy, 4, ORANGE_D)
    s.line(gx, vy + 30, xr, vy + 30, RED, 1.8, arrow=True)
    s.text(xr, vy + 50, f"가장 비슷한 블록: xR = {XR:.1f}  →  d = {DISP:.1f}", 12.5, 700, RED)
    s.text(36, 1092, "SGBM: 왼쪽의 작은 블록을 오른쪽 같은 행에서 d = 0, 1, 2, … 만큼 왼쪽으로 옮겨 가며 비교하고, 가장 비슷한 d 를 고른다(초록 띠).",
           12.5, fill=INK)
    s.text(36, 1116, "찾을 수 있는 가장 큰 d 가 가장 가까운 거리를 정한다:  Z 최소 = f′ · B / d 최대.  행이 맞지 않으면 짝을 잘못 찾는다.",
           12.5, fill=GRAY)
    s.save("stereo_depth_3_rectify.svg")


# ------------------------------------------------------------------------------------- 4. R and T
def fig_rt():
    W, H = 1120, 860
    s = Svg(W, H)
    s.title(30, 38, "④ R · T: 두 카메라 사이의 회전과 이동 — 같은 순간에 같은 보드를 찍은 쌍으로 구한다",
            "cv2.stereoCalibrate(..., flags=CALIB_FIX_INTRINSIC): K1 · D1 · K2 · D2 는 고정, R · T 만 푼다")
    # (a) top view
    s.rect(20, 80, 560, 520, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "(가) 위에서 본 그림 — 개략도, 축척 아님", 14.5, 700)
    ol, orr, yb = 170, 410, 470
    # board (tilted) with corners
    b0, b1 = (210, 190), (420, 150)
    s.line(*b0, *b1, INK, 5.0)
    for t in np.linspace(0, 1, 9):
        s.circle(b0[0] + (b1[0] - b0[0]) * t, b0[1] + (b1[1] - b0[1]) * t, 2.6, "#fff", INK, 1.0)
    s.circle(*b0, 6, RED)
    s.text(b0[0] - 8, b0[1] - 14, "보드 원점 (코너 0번)", 12.5, 700, RED, "end")
    s.text(b1[0] + 6, b1[1] - 10, "체커보드", 12.5, 700, INK)
    s.line(b0[0], b0[1], b0[0] + 52, b0[1] - 10, RED, 1.4, arrow=True)
    s.text(b0[0] + 40, b0[1] + 18, "보드 x", 11, fill=RED)
    camera_top(s, ol, yb, "왼쪽 카메라", BLUE, -1)
    camera_top(s, orr, yb, "오른쪽 카메라", ORANGE_D, 1)
    s.line(ol, yb, b0[0] - 3, b0[1] + 6, BLUE, 2.0, arrow=True)
    s.text(150, 320, "R_L, t_L", 14, 700, BLUE, "end", mono=True)
    s.text(150, 340, "왼쪽에서 본 보드 자세", 11.5, fill=BLUE, anchor="end")
    s.line(orr, yb, b0[0] + 5, b0[1] + 6, ORANGE_D, 2.0, arrow=True)
    s.text(330, 330, "R_R, t_R", 14, 700, ORANGE_D, mono=True)
    s.text(330, 350, "오른쪽에서 본 보드 자세", 11.5, fill=ORANGE_D)
    s.line(ol + 8, yb + 62, orr - 8, yb + 62, GREEN, 2.2, arrow=True)
    s.text((ol + orr) / 2, yb + 54, "R, T  (왼쪽 → 오른쪽)", 14, 700, GREEN, "middle", mono=True)
    s.text((ol + orr) / 2, yb + 84, f"|T| = B = {B * 1000:.1f} mm", 13, 700, GREEN, "middle")
    s.text(36, 588, "보드를 움직이면 R_L · t_L · R_R · t_R 는 쌍마다 바뀌지만, R · T 는 바에 고정돼 바뀌지 않는다.", 11.5, fill=GRAY)

    # (b) formulas
    s.rect(596, 80, 504, 520, "#fff", LINE, 1.0, 12)
    s.text(612, 106, "(나) 식", 14.5, 700)
    s.text(612, 138, "보드 위 코너 하나의 보드 좌표 (s = --square, m):", 12.5, fill=GRAY)
    s.text(628, 162, "X_board = (i · s, j · s, 0)", 14, 700, RED, mono=True)
    s.text(612, 196, "그 코너를 왼쪽 · 오른쪽 카메라 좌표로 쓰면:", 12.5, fill=GRAY)
    s.text(628, 220, "X_L = R_L · X_board + t_L", 14, 700, BLUE, mono=True)
    s.text(628, 246, "X_R = R_R · X_board + t_R", 14, 700, ORANGE_D, mono=True)
    s.text(612, 280, "두 카메라 좌표 사이의 관계가 R · T:", 12.5, fill=GRAY)
    s.text(628, 304, "X_R = R · X_L + T", 14, 700, GREEN, mono=True)
    s.text(612, 338, "위 세 식에서 X_board 를 지우면:", 12.5, fill=GRAY)
    s.rect(612, 350, 472, 64, "#eaf6ec", GREEN, 1.4, 8)
    s.text(628, 376, "R = R_R · R_Lᵀ", 15, 700, GREEN, mono=True)
    s.text(628, 402, "T = t_R − R · t_L", 15, 700, GREEN, mono=True)
    s.lines(612, 440, ["쌍 하나로도 식은 풀리지만 검출 오차가 섞인다.",
                       "그래서 쌍 수십 개를 모아, 두 영상의 재투영 오차가",
                       "가장 작아지는 R · T 하나를 찾는다 (stereoCalibrate).",
                       "X_board 가 m 단위라 t 와 T 도 m 단위가 된다.",
                       "s 를 10 % 크게 넣으면 B 도, 모든 거리도 10 % 커진다."], 12.5, gap=22)

    # (c) one pair and the real result
    s.rect(20, 616, 1080, 228, "#fff", LINE, 1.0, 12)
    s.text(36, 642, "(다) 같은 순간 찍은 한 쌍 — 보드가 두 영상에 통째로 들어와야 한다", 14.5, 700)
    sc = 0.3
    for x0, c, shift, lab in ((60, BLUE, 0, "왼쪽 영상"), (300, ORANGE_D, -40, "오른쪽 영상")):
        s.rect(x0, 668, W_IMG * sc, H_IMG * sc, "#fff", c, 1.6, 2)
        s.text(x0, 664 + H_IMG * sc + 24, lab, 12, 700, c)
        bx, by = x0 + 70 + shift * sc * 3, 690
        for i in range(5):
            for j in range(3):
                if (i + j) % 2 == 0:
                    s.rect(bx + i * 12, by + j * 12, 12, 12, INK, "none", 0, 0)
        s.rect(bx, by, 60, 36, "none", INK, 1.0, 0)
    s.text(560, 680, "이 그림에 쓴 값 (가정 — 보정 뒤 교체):", 12.5, 700)
    s.text(560, 708, f"R (회전 벡터, 도) = ({RVEC_DEG[0]:.2f}, {RVEC_DEG[1]:.2f}, {RVEC_DEG[2]:.2f})", 13, mono=True)
    s.text(560, 732, f"T [m] = ({T_LR[0]:.4f}, {T_LR[1]:.4f}, {T_LR[2]:.4f})", 13, mono=True)
    s.text(560, 756, f"|T| = {B * 1000:.1f} mm  → ② 그림의 B", 13, 700, GREEN, mono=True)
    s.text(560, 780, "보정 뒤 stereo RMS 0.5 px 이하면 좋다", 13, mono=True)
    s.text(560, 812, "T 의 x 가 음수: X_R = R·X_L + T 에서 오른쪽 카메라 좌표로 옮기면", 11.5, fill=GRAY)
    s.text(560, 830, "점이 왼쪽으로(−x) 옮겨지기 때문이다.", 11.5, fill=GRAY)
    s.save("stereo_depth_4_rt.svg")


# --------------------------------------------------------------------------------- 5. one camera
def fig_camera():
    W, H = 1120, 1080
    s = Svg(W, H)
    s.title(30, 38, "⑤ K · D: 카메라 한 대의 구조 — 공간의 점이 몇 번 픽셀에 찍히는가",
            f"cv2.calibrateCamera. 값은 IMX219 사양 계산값 (f = 2.96 mm ÷ 픽셀 간격), D 는 보정 전이라 0")
    fx, fy, cx, cy = KL[0, 0], KL[1, 1], KL[0, 2], KL[1, 2]
    # (a) side view
    s.rect(20, 80, 560, 420, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "(가) 옆에서 본 그림 — 개략도", 14.5, 700)
    oz, oy = 120, 330                     # lens centre
    s.line(oz - 40, oy, 540, oy, MUTE, 1.0, "4 4")
    s.text(545, oy + 4, "Z", 13, 700, MUTE)
    s.text(520, oy + 22, "광축", 11, fill=MUTE, anchor="end")
    s.line(oz, oy + 40, oz, 120, MUTE, 1.0, "4 4")
    s.text(oz - 6, 130, "Y", 11, fill=MUTE, anchor="end")
    s.rect(oz - 50, oy - 18, 40, 36, "#fff", INK, 1.4, 4)
    s.poly([(oz - 10, oy - 10), (oz, oy - 16), (oz, oy + 16), (oz - 10, oy + 10)], "#fff", INK, 1.4)
    s.circle(oz, oy, 4, INK)
    s.text(oz - 30, oy + 40, "렌즈 중심", 12, 700, INK, "middle")
    fz = oz + 120                         # image plane at fy (drawn)
    s.line(fz, 150, fz, oy + 60, BLUE, 3.0)
    s.text(fz + 6, oy + 76, "영상면", 12, 700, BLUE)
    pz, py = 500, 170
    s.circle(pz, py, 6, RED)
    s.text(pz, py - 12, "점 (X, Y, Z)", 13, 700, RED, "middle")
    s.line(pz, py, oz, oy, RED, 1.3)
    hy = oy + (py - oy) * (fz - oz) / (pz - oz)
    s.circle(fz, hy, 5, BLUE)
    s.text(fz + 8, hy - 6, "v", 14, 700, BLUE, italic=True)
    s.circle(fz, oy, 3.5, INK)
    s.text(fz + 8, oy + 18, "cy", 12.5, 700, INK)
    s.line(oz, oy + 30, fz, oy + 30, PURPLE, 1.4, both=True)
    s.text((oz + fz) / 2, oy + 48, "fy (px)", 12.5, 700, PURPLE, "middle")
    s.line(pz + 14, py, pz + 14, oy, TEAL, 1.3, both=True)
    s.text(pz + 18, (py + oy) / 2, "Y", 13, 700, TEAL)
    s.line(oz, oy + 96, pz, oy + 96, GREEN, 1.3, both=True)
    s.text((oz + pz) / 2, oy + 90, "Z", 13, 700, GREEN, "middle")
    s.text(36, 486, "위에서 보면 같은 그림에서 Y → X, fy → fx, cy → cx, v → u 가 된다.", 11.5, fill=GRAY)

    # (b) sensor (front view)
    s.rect(596, 80, 504, 420, "#fff", LINE, 1.0, 12)
    s.text(612, 106, "(나) 영상면을 정면에서 본 그림 (640 × 360)", 14.5, 700)
    sc = 0.62
    x0, y0 = 650, 160
    w, h = image_frame(s, x0, y0, sc, "", INK)
    s.line(x0 + cx * sc, y0, x0 + cx * sc, y0 + h, INK, 1.0, "4 4")
    s.line(x0, y0 + cy * sc, x0 + w, y0 + cy * sc, INK, 1.0, "4 4")
    s.circle(x0 + cx * sc, y0 + cy * sc, 4, INK)
    s.text(x0 + cx * sc + 6, y0 + 14, f"cx = {cx:.1f}", 11.5, 700, INK)
    s.text(x0 + 6, y0 + cy * sc - 6, f"cy = {cy:.1f}", 11.5, 700, INK)
    pu, pv = x0 + (cx + 95) * sc, y0 + (cy - 70) * sc
    s.circle(pu, pv, 5.5, BLUE)
    s.text(pu + 8, pv - 6, "(u, v)", 13, 700, BLUE)
    s.lines(612, 430, ["점이 광축 위에 있으면 (cx, cy) 에 찍힌다.",
                       "광축에서 벗어난 만큼 (fx, fy 배) 옮겨 찍힌다."], 12.5, gap=22, fill=GRAY)

    # (c) the projection formulas with every symbol
    s.rect(20, 516, 1080, 270, "#fff", LINE, 1.0, 12)
    s.text(36, 542, "(다) 점 (X, Y, Z) → 픽셀 (u, v) 계산 세 단계", 14.5, 700)
    f_rows = [
        ("1", INK, "x = X / Z ,   y = Y / Z", "Z = 1 인 면으로 옮긴 좌표 (광축에서 벗어난 정도)"),
        ("2", ORANGE_D, "r² = x² + y²", "광축에서 떨어진 거리의 제곱"),
        ("", ORANGE_D, "x_d = x(1 + k1·r² + k2·r⁴ + k3·r⁶) + 2·p1·x·y + p2·(r² + 2x²)", "렌즈 왜곡 D 적용"),
        ("", ORANGE_D, "y_d = y(1 + k1·r² + k2·r⁴ + k3·r⁶) + p1·(r² + 2y²) + 2·p2·x·y", ""),
        ("3", BLUE, "u = fx · x_d + cx ,   v = fy · y_d + cy", "픽셀로 바꾼다 (K 적용)"),
    ]
    for i, (n, c, f, note) in enumerate(f_rows):
        y = 578 + i * 30
        s.text(46, y, n, 14, 700, c)
        s.text(70, y, f, 13.5, 700, c, mono=True)
        s.text(720, y, note, 12, fill=GRAY)
    s.line(36, 732, 1084, 732, LINE, 1.0)
    s.text(46, 756, f"K:  fx = {fx:.2f}   fy = {fy:.2f}   cx = {cx:.2f}   cy = {cy:.2f}   (px)", 13, 700, BLUE, mono=True)
    s.text(46, 776, "D:  k1 = {:.4f}  k2 = {:.4f}  p1 = {:.4f}  p2 = {:.4f}  k3 = {:.4f}".format(*DL[:5]), 13, 700,
           ORANGE_D, mono=True)
    s.text(720, 756, "k1 k2 k3 = 가운데에서 멀수록 휘는 정도", 11.5, fill=GRAY)
    s.text(720, 776, "p1 p2 = 렌즈와 센서가 기울어 생기는 휨", 11.5, fill=GRAY)

    # (d) calibrateCamera loop
    s.rect(20, 802, 1080, 262, "#fff", LINE, 1.0, 12)
    s.text(36, 828, "(라) K · D 를 찾는 방법 — 위치를 아는 점(체커보드 코너)으로 거꾸로 푼다", 14.5, 700)
    steps = [("사진마다 짝", "코너 3D (i·s, j·s, 0)", "↔ 검출 픽셀 (u, v)", INK),
             ("짐작", "K · D (모든 사진 공통)", "+ 사진마다 보드 자세", PURPLE),
             ("투영", "위 (다) 1 · 2 · 3 으로", "코너를 픽셀로 계산", BLUE),
             ("비교", "계산 픽셀 − 검출 픽셀", "= 재투영 오차", RED),
             ("고친다", "오차가 줄도록", "K · D · 자세를 조금씩", GREEN)]
    bw = 190
    for i, (a, b, c2, col) in enumerate(steps):
        x = 36 + i * (bw + 22)
        s.rect(x, 846, bw, 78, "#fff", col, 1.4, 8)
        s.text(x + bw / 2, 870, a, 13.5, 700, col, "middle")
        s.text(x + bw / 2, 892, b, 12, fill=INK, anchor="middle")
        s.text(x + bw / 2, 912, c2, 12, fill=INK, anchor="middle")
        if i:
            s.line(x - 20, 885, x - 3, 885, INK, 1.4, arrow=True)
    s.path(f"M{36 + 4 * (bw + 22) + bw / 2},{924} L{36 + 4 * (bw + 22) + bw / 2},{944} "
           f"L{36 + 2 * (bw + 22) + bw / 2},{944} L{36 + 2 * (bw + 22) + bw / 2},{928}", GREEN, 1.4, arrow=True)
    s.text(36 + 3 * (bw + 22) + bw / 2, 960, "더 줄지 않을 때까지 되풀이", 11.5, fill=GREEN, anchor="middle")
    s.lines(46, 990, ["끝까지 남은 오차의 평균 = RMS 재투영 오차 (0.5 px 이하면 좋다).",
                      "정면 사진만 있으면 '초점거리가 길고 보드가 멀다'와 '짧고 가깝다'를 가를 수 없다 → 보드를 기울이고,",
                      "왜곡은 가장자리에서 드러나므로 화면 구석까지 옮겨 가며 찍는다. 영상 해상도가 바뀌면 K 도 바뀐다 (640 × 360 으로 찍는다)."],
            12.5, gap=22)
    s.save("stereo_depth_5_camera.svg")


# ------------------------------------------------------------------- 6. backward chain + procedure
def fig_chain():
    W, H = 1120, 900
    s = Svg(W, H)
    s.title(30, 38, "⑥ 정리: 거꾸로 따라간 사슬과 실제로 하는 순서",
            "왼쪽은 아래에서 위로 읽는다(필요한 값 → 그 값을 만드는 것). 오른쪽은 위에서 아래로 실제로 하는 일")
    # left: chain, goal on top
    chain = [
        ("① Z = f′ · B / d", "거리", GREEN),
        ("② f′·B = −P_right[0,3]  ·  d = SGBM", "P 행렬 · 평행화된 영상의 같은 행 검색", RED),
        ("③ R1 · R2 · P1 · P2", "cv2.stereoRectify", BLUE),
        ("④ R · T  (|T| = B)", "cv2.stereoCalibrate · 동시 쌍", ORANGE_D),
        ("⑤ K1 · D1 · K2 · D2", "cv2.calibrateCamera · 카메라마다", PURPLE),
        ("체커보드 사진 (코너 3D ↔ 픽셀)", "s = 한 칸 길이 [m]", INK),
    ]
    s.rect(20, 80, 500, 800, "#fff", LINE, 1.0, 12)
    s.text(36, 106, "거꾸로: 무엇이 무엇을 필요로 하나", 14.5, 700)
    for i, (a, b, c) in enumerate(chain):
        y = 130 + i * 122
        s.rect(40, y, 460, 76, "#fff", c, 1.8, 10)
        s.text(56, y + 32, a, 14, 700, c, mono=True)
        s.text(56, y + 58, b, 12.5, fill=GRAY)
        if i < len(chain) - 1:
            s.line(270, y + 76 + 42, 270, y + 80, INK, 1.6, arrow=True)
            s.text(282, y + 104, "아래 상자의 결과가 위 상자의 입력", 11, fill=GRAY)
    # right: procedure
    s.rect(536, 80, 564, 800, "#fff", LINE, 1.0, 12)
    s.text(552, 106, "실제 순서 (함수는 OpenCV)", 14.5, 700)
    steps = [
        ("1", "체커보드를 준비하고 한 칸 길이 s 를 자로 잰다", ["내부 코너 수 (cols · rows)", "s [m] — 틀리면 모든 거리가 같은 비율로 틀린다"], INK),
        ("2", "두 카메라를 동시에 녹화한다 (보드를 여러 자세로)", ["좌 · 우 촬영 시각이 맞는 쌍만 쓴다", "녹화 중 카메라 고정대를 건드리지 않는다"], INK),
        ("3", "카메라마다 K · D 를 구한다  → ⑤", ["cv2.findChessboardCorners · cornerSubPix", "cv2.calibrateCamera"], PURPLE),
        ("4", "동시 쌍으로 R · T, 이어서 R1 R2 P1 P2  → ④ ③ ②", ["cv2.stereoCalibrate (CALIB_FIX_INTRINSIC)", "cv2.stereoRectify → camera_info 두 개에 기록"], ORANGE_D),
        ("5", "검사: 같은 행에 오는가, |T| 가 자와 맞는가", ["평행화 뒤 같은 코너의 행 차이 < 0.5 px", "|T| 와 자로 잰 렌즈 간격 2 % 안"], BLUE),
        ("6", "운용: 매 프레임 평행화 → SGBM 으로 d → Z  → ①", ["cv2.initUndistortRectifyMap (한 번) · cv2.remap", "cv2.StereoSGBM → d → Z = f′·B/d"], GREEN),
    ]
    y = 128
    for n, a, tools, c in steps:
        hgt = 48 + 20 * len(tools)
        s.rect(552, y, 532, hgt, "#fff", c, 1.6, 10)
        s.circle(578, y + 26, 14, c)
        s.text(578, y + 31, n, 14, 700, "#fff", "middle")
        s.text(602, y + 31, a, 13, 700, c)
        for k, t in enumerate(tools):
            s.text(602, y + 56 + k * 20, t, 12, fill=INK, mono=True)
        y += hgt + 14
    s.text(552, 860, "1 ~ 5 는 camera_info 두 개를 채우는 일 — 카메라를 다시 달거나 고정대가 휘지 않으면 한 번이면 된다.", 11.5, fill=GRAY)
    s.save("stereo_depth_6_chain.svg")


if __name__ == "__main__":
    fig_formula()
    fig_values()
    fig_rectify()
    fig_rt()
    fig_camera()
    fig_chain()
