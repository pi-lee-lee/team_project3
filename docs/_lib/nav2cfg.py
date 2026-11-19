"""nav2_params.yaml 읽기(설명서 그림이 현재 설정값을 그대로 쓰게 한다). PyYAML 없이 들여쓰기만으로 읽는다.

쓰는 법: cfg = load(); cfg['controller_server']['ros__parameters']['FollowPath']['batch_size']
목록(- 항목, 여러 줄 [ ... ])은 읽지 않는다. 숫자는 float, true/false 는 bool, 나머지는 문자열.
"""
import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / 'ros/sim/src/config/nav2_params.yaml'
_LINE = re.compile(r'^( *)([A-Za-z_][\w.]*):\s*(.*)$')


def _value(s):
    s = s.split(' #')[0].strip().strip('"\'')
    if s.lower() in ('true', 'false'):
        return s.lower() == 'true'
    try:
        return float(s)
    except ValueError:
        return s


def load(path=PATH):
    root = {}
    stack = [(-1, root)]                     # (들여쓰기, 그 깊이의 dict)
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = _LINE.match(line)
        if not m or line.lstrip().startswith('#'):
            continue
        ind, key, val = len(m.group(1)), m.group(2), m.group(3).split(' #')[0].strip()
        if val.startswith('#'):
            val = ''
        while stack[-1][0] >= ind:
            stack.pop()
        if val == '':
            node = {}
            stack[-1][1][key] = node
            stack.append((ind, node))
        else:
            stack[-1][1][key] = _value(val)
    return root


def num(v):
    """표시용: 0.5 → '0.5', 30.0 → '30'."""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else f'{v:g}'
    return str(v)
