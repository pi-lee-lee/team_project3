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
