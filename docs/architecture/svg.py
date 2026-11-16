"""아키텍처 도면 공용 그리기 도구(SVG 문자열 조립)."""
from xml.sax.saxutils import escape

FONT = "-apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif"
MONO = "'SF Mono', Menlo, Consolas, monospace"

# 역할별 색: (진한 선·글자, 연한 채움)
C = {
    'client': ('#007aff', '#eaf3ff'),
    'edge': ('#5856d6', '#efeefc'),
    'spring': ('#248a3d', '#e9f7ee'),
    'py': ('#b25000', '#fff4e5'),
    'data': ('#c93400', '#fff1e8'),
    'bridge': ('#8944ab', '#f5ecfa'),
    'ros': ('#0071a4', '#e6f5fb'),
    'dev': ('#3a3a3c', '#f2f2f7'),
    'gray': ('#8e8e93', '#ffffff'),
}
NET = {'edge': '#5856d6', 'backend': '#248a3d', 'robot': '#8944ab'}


def text_width(s, mono=True, size=12):
    """대략적인 글자 폭(px): 한글은 넓게, 영문·숫자는 좁게."""
    k = size / 12
    return sum((12.2 if ord(ch) > 0x1100 else (7.3 if mono else 6.6)) for ch in s) * k


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.body, self.late = [], []

    def raw(self, s, late=False):
        (self.late if late else self.body).append(s)

    def text(self, x, y, s, size=13, weight=400, color='#1c1c1e', anchor='start', mono=False, late=False):
        f = f' font-family="{MONO}"' if mono else ''
        self.raw(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" '
                 f'text-anchor="{anchor}"{f}>{escape(s)}</text>', late)

    def rect(self, x, y, w, h, fill='#fff', stroke='#d1d1d6', sw=1.0, rx=10, dash=None, opacity=None, late=False):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        o = f' opacity="{opacity}"' if opacity is not None else ''
        self.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}{o}/>', late)

    def chip(self, x, y, label, kind, mono=True, w=None, late=False):
        """클래스·구성 요소 이름표. 너비를 돌려준다."""
        stroke, fill = C[kind]
        cw = w or text_width(label, mono) + 18
        self.rect(x, y, cw, 24, fill='#ffffff', stroke=stroke, sw=1.1, rx=6, late=late)
        self.text(x + cw / 2, y + 16.5, label, 12, 600, stroke, 'middle', mono=mono, late=late)
        return cw

    def pill(self, x, y, label, color):
        w = len(label) * 7 + 14
        self.rect(x, y, w, 18, fill=color, stroke=color, rx=9)
        self.text(x + w / 2, y + 13, label, 10.5, 700, '#ffffff', 'middle')
        return w

    def line(self, pts, color='#8e8e93', sw=1.6, end=True, start=False, dash=None, late=True):
        d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
        mid = color.lstrip('#')
        m = (f' marker-end="url(#a{mid})"' if end else '') + (f' marker-start="url(#a{mid})"' if start else '')
        ds = f' stroke-dasharray="{dash}"' if dash else ''
        self.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{m}{ds}/>', late)
        self._markers.add(color)

    _markers = set()

    def render(self, path):
        defs = ''.join(
            f'<marker id="a{c.lstrip("#")}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in sorted(self._markers))
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}">', f'<defs>{defs}</defs>',
               f'<rect width="{self.w}" height="{self.h}" fill="#f2f2f7"/>', *self.body, *self.late, '</svg>']
        path.write_text('\n'.join(out), encoding='utf-8')
        print(f'wrote {path} ({self.w}x{self.h})')
