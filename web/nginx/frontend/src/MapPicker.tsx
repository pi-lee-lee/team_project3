import { useEffect, useRef, useState } from 'react';
import type { MapInfo, Point } from './api/types';
import { useApi, usePoll } from './util';
import { mapGeo, screenAngleDeg } from './mapGeo';
import { Icon } from './Icon';

export type PickValue = { x: number; y: number; yawDeg: number };

const round2 = (v: number) => Math.round(v * 100) / 100;
const normDeg = (d: number) => { let a = Math.round(d) % 360; if (a > 180) a -= 360; if (a <= -180) a += 360; return a; };

/**
 * 지도에서 점검 지점 고르기.
 *  - 누르면 그 자리가 지점 위치(x, y), 누른 채 끌면 끈 방향이 로봇이 촬영할 때 바라볼 방향.
 *  - 좌표 변환은 관제 지도와 같은 mapGeo 를 쓴다. 지도 그림을 지도 칸 수 × 축척 그대로 그리므로 화면과 좌표가 어긋나지 않는다.
 *  - 저장되는 값(0.01m, 1° 단위로 반올림)을 그대로 다시 그려, 표시와 저장 값이 같다.
 */
export function MapPicker({ robotId, value, onChange, others, code }: {
  robotId: number;
  value: PickValue | null;
  onChange: (v: PickValue) => void;
  /** 이미 있는 다른 지점(겹치지 않게 참고로 표시) */
  others: Point[];
  /** 지금 고치는 지점 코드(표시용) */
  code?: string;
}) {
  const api = useApi();
  const info = usePoll<MapInfo | null>(() => api.mapInfo(robotId).catch(() => null), 15000, [robotId]);
  const view = usePoll(() => api.mapView(robotId).catch(() => null), 1000, [robotId]);
  const m = info.data;
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const press = useRef<{ cx: number; cy: number; dragging: boolean } | null>(null);

  useEffect(() => {
    if (!m) return;
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = api.mapImageUrl(robotId, m.version);
  }, [m?.version, robotId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  // 축척: 상자 폭에 맞추되 너무 길어지지 않게(세로 최대 560px)
  useEffect(() => {
    const el = wrap.current;
    if (!el || !m) return;
    const fit = () => setScale(Math.min(el.clientWidth / m.width, 560 / m.height));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [m]);

  const geo = m ? mapGeo(m, scale) : null;

  // 그리기
  useEffect(() => {
    const c = canvas.current;
    if (!c || !geo || !img || !m) return;
    const dpr = window.devicePixelRatio || 1;
    c.style.width = `${geo.cw}px`;
    c.style.height = `${geo.ch}px`;
    c.width = Math.round(geo.cw * dpr);
    c.height = Math.round(geo.ch * dpr);
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.imageSmoothingEnabled = true;
    g.drawImage(img, 0, 0, geo.cw, geo.ch);
    const label = (text: string, x: number, y: number, color: string) => {
      g.font = '600 11px -apple-system, system-ui, sans-serif'; g.textAlign = 'center';
      g.lineWidth = 3; g.strokeStyle = 'rgba(255,255,255,.9)'; g.strokeText(text, x, y);
      g.fillStyle = color; g.fillText(text, x, y);
    };
    const arrow = (x: number, y: number, deg: number, color: string, len: number) => {
      const a = (deg * Math.PI) / 180, ex = x + Math.cos(a) * len, ey = y - Math.sin(a) * len;
      g.strokeStyle = color; g.lineWidth = 2.5; g.lineCap = 'round';
      g.beginPath(); g.moveTo(x, y); g.lineTo(ex, ey); g.stroke();
      const h = 6, back = a + Math.PI;
      g.fillStyle = color; g.beginPath();
      g.moveTo(ex, ey);
      g.lineTo(ex + Math.cos(back - 0.5) * h, ey - Math.sin(back - 0.5) * h);
      g.lineTo(ex + Math.cos(back + 0.5) * h, ey - Math.sin(back + 0.5) * h);
      g.closePath(); g.fill();
    };
    // 다른 지점: 청록 점 + 코드
    others.forEach((p) => {
      const px = geo.toPx(p.x), py = geo.toPy(p.y);
      arrow(px, py, p.yaw_deg, 'rgba(48,176,199,.6)', 14);
      g.fillStyle = '#fff'; g.strokeStyle = '#30b0c7'; g.lineWidth = 2;
      g.beginPath(); g.arc(px, py, 5, 0, Math.PI * 2); g.fill(); g.stroke();
      label(p.code, px, py - 9, '#30b0c7');
    });
    // 로봇 현재 위치(참고): 파란 점 + 방향
    const pose = view.data?.pose;
    if (pose) {
      const rx = geo.toPx(pose.x), ry = geo.toPy(pose.y);
      arrow(rx, ry, (pose.yaw * 180) / Math.PI, 'rgba(0,122,255,.8)', 12);
      g.fillStyle = '#007aff'; g.beginPath(); g.arc(rx, ry, 4, 0, Math.PI * 2); g.fill();
    }
    // 고른 지점: 보라 원 + 방향 화살표 + 정확한 위치 십자
    if (value) {
      const vx = geo.toPx(value.x), vy = geo.toPy(value.y);
      arrow(vx, vy, value.yawDeg, '#af52de', 26);
      g.fillStyle = 'rgba(175,82,222,.18)'; g.strokeStyle = '#af52de'; g.lineWidth = 2;
      g.beginPath(); g.arc(vx, vy, 9, 0, Math.PI * 2); g.fill(); g.stroke();
      g.strokeStyle = '#af52de'; g.lineWidth = 1;
      g.beginPath(); g.moveTo(vx - 4, vy); g.lineTo(vx + 4, vy); g.moveTo(vx, vy - 4); g.lineTo(vx, vy + 4); g.stroke();
      label(code || '새 지점', vx, vy - 14, '#af52de');
    }
  }, [geo?.cw, geo?.ch, img, value, others, view.data, code]); // eslint-disable-line react-hooks/exhaustive-deps

  const local = (e: React.PointerEvent) => {
    const r = canvas.current!.getBoundingClientRect();
    return { cx: e.clientX - r.left, cy: e.clientY - r.top };
  };
  const down = (e: React.PointerEvent) => {
    if (!geo) return;
    const { cx, cy } = local(e);
    canvas.current!.setPointerCapture(e.pointerId);
    press.current = { cx, cy, dragging: false };
    const w = geo.toWorld(cx, cy);
    onChange({ x: round2(w.x), y: round2(w.y), yawDeg: value?.yawDeg ?? 0 });
  };
  const move = (e: React.PointerEvent) => {
    if (!geo) return;
    const { cx, cy } = local(e);
    setHover(geo.toWorld(cx, cy));
    const p = press.current;
    if (!p) return;
    const dx = cx - p.cx, dy = cy - p.cy;
    if (!p.dragging && Math.hypot(dx, dy) < 8) return;   // 조금 흔들린 것은 클릭으로 본다
    p.dragging = true;
    const w = geo.toWorld(p.cx, p.cy);
    onChange({ x: round2(w.x), y: round2(w.y), yawDeg: normDeg(screenAngleDeg(dx, dy)) });
  };
  const up = () => { press.current = null; };

  const pose = view.data?.pose;
  return (
    <div className="map-picker">
      <div className="map-picker-canvas" ref={wrap}>
        {m && img ? (
          <canvas ref={canvas} className="clickable" onPointerDown={down} onPointerMove={move} onPointerUp={up}
            onPointerCancel={up} onPointerLeave={() => setHover(null)} aria-label="지도에서 지점 위치 고르기" />
        ) : (
          <div className="novideo map-empty">지도를 불러오는 중… (로봇이 지도를 보내야 표시됩니다)</div>
        )}
      </div>
      <div className="map-picker-bar">
        <span className="meta"><Icon name="location.fill" size={15} />
          {hover ? `커서 x ${hover.x.toFixed(2)} · y ${hover.y.toFixed(2)}` : '지도를 눌러 위치, 누른 채 끌어 방향'}
        </span>
        {m && <span className="meta muted">1칸 {Math.round(m.resolution * 1000) / 1000} m</span>}
        <button type="button" className="pill-btn" disabled={!pose}
          onClick={() => pose && onChange({ x: round2(pose.x), y: round2(pose.y), yawDeg: normDeg((pose.yaw * 180) / Math.PI) })}>
          <Icon name="cpu" size={14} />로봇 현재 위치로
        </button>
      </div>
    </div>
  );
}
