// 로봇 지도 좌표(m) ↔ 화면 좌표(CSS px) 변환. 관제 지도와 지점 지정 지도가 같은 식을 쓰게 한 곳에 둔다.
//
// 지도(OccupancyGrid)는 width×height 칸, 한 칸 = resolution m, 원점(originX, originY) = 0번 칸의 왼쪽 아래 모서리.
// 서버가 그리는 지도 PNG(robot-service MapRenderer)는 칸 하나를 SCALE×SCALE 픽셀로 키우고 행을 뒤집는다
// (그림 맨 위 줄 = 지도 맨 위 행 = y 가 가장 큰 쪽). 화면에는 그 PNG 를 정확히 width×s, height×s (CSS px) 로 그린다.
// 그러면 칸 경계가 화면 픽셀 경계와 일치하므로, 연속 좌표에 대해 아래 식이 정확히 맞는다:
//   화면 x = (x - originX) / resolution × s
//   화면 y = (height - (y - originY) / resolution) × s
// (칸의 가운데가 아니라 모서리를 기준으로 한 선형 변환 — 반 칸 어긋남이 생기지 않는다)
import type { MapInfo } from './api/types';

export type MapGeo = {
  /** 지도 1칸 = 화면 몇 CSS px */
  scale: number;
  /** 지도 전체를 그릴 화면 크기(CSS px) */
  cw: number;
  ch: number;
  toPx: (x: number) => number;
  toPy: (y: number) => number;
  toWorld: (cx: number, cy: number) => { x: number; y: number };
};

export function mapGeo(m: MapInfo, scale: number): MapGeo {
  return {
    scale,
    cw: m.width * scale,
    ch: m.height * scale,
    toPx: (x) => ((x - m.originX) / m.resolution) * scale,
    toPy: (y) => (m.height - (y - m.originY) / m.resolution) * scale,
    toWorld: (cx, cy) => ({
      x: m.originX + (cx / scale) * m.resolution,
      y: m.originY + (m.height - cy / scale) * m.resolution,
    }),
  };
}

/** 화면 위 방향(오른쪽=0°, 반시계=+, 화면 y 는 아래로 자라므로 부호를 뒤집는다) → 지도 방향(도, -180~180) */
export function screenAngleDeg(dx: number, dy: number) {
  return (Math.atan2(-dy, dx) * 180) / Math.PI;
}

/**
 * 금지구역 그리기: 붉은 직사각형 + 빗금. 관제 지도와 대시보드 지도가 함께 쓴다.
 * rect 는 지도 좌표(m). selected 면 굵은 테두리, draft(끄는 중)면 점선 테두리.
 */
export function drawZone(
  g: CanvasRenderingContext2D, toPx: (x: number) => number, toPy: (y: number) => number,
  rect: { xMin: number; yMin: number; xMax: number; yMax: number }, opt: { selected?: boolean; draft?: boolean; label?: string } = {},
) {
  const x = toPx(rect.xMin), y = toPy(rect.yMax), w = toPx(rect.xMax) - x, h = toPy(rect.yMin) - y;
  g.save();
  g.fillStyle = 'rgba(255, 59, 48, 0.12)';
  g.fillRect(x, y, w, h);
  g.beginPath(); g.rect(x, y, w, h); g.clip();
  g.strokeStyle = 'rgba(255, 59, 48, 0.75)'; g.lineWidth = 1.5; g.setLineDash([]);
  g.beginPath();
  for (let d = -h; d < w; d += 9) { g.moveTo(x + d, y + h); g.lineTo(x + d + h, y); }
  g.stroke();
  g.restore();
  g.save();
  g.strokeStyle = '#ff3b30'; g.lineWidth = opt.selected ? 4 : 2.5;
  g.setLineDash(opt.draft ? [7, 5] : []);
  g.strokeRect(x, y, w, h);
  if (opt.label) {
    g.font = '600 11px -apple-system, system-ui, sans-serif'; g.textAlign = 'left'; g.textBaseline = 'top';
    const tw = g.measureText(opt.label).width;
    g.fillStyle = '#ff3b30'; g.fillRect(x, y, tw + 10, 17);
    g.fillStyle = '#fff'; g.fillText(opt.label, x + 5, y + 3);
  }
  g.restore();
}
