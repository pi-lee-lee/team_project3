import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { homeOf } from '../../App';
import { useAuth } from '../../util';
import { Icon } from '../../Icon';
import { setTheme } from '../../theme';
import { playTransition } from '../../PixelFx';
import { clearFrame, composite, createFrame, createFx, smallExplosion } from '../../pixelfx/index.js';
import type { FxFrame, FxInstance } from '../../pixelfx/index.js';
import { EmergencyDialog } from '../../EmergencyDialog';
import { LaunchDialog } from '../../LaunchDialog';
import './duel.css';

/**
 * 포격전(이스터 에그): 픽셀 모드에서 대시보드를 열면 관제 화면 대신 뜨는 2인 대전.
 * 왼쪽 전차는 sup1, 오른쪽 전차는 ADMIN 계정이 몬다(다른 계정은 구경). 번갈아 각도 · 세기를 정해 쏜다.
 *
 * 판정은 서버(inspection-service DuelController)가 한다. 화면은 0.4초마다 상태를 받아
 * 서버가 계산해 준 궤적을 그대로 그리고, 포탄이 닿은 뒤에 새 땅 · 체력으로 바꾼다.
 * 폭발은 pixelfx 의 explosions/small-explosion 을 맞은 자리에 겹쳐 그린다.
 * 비상 · 투척 승인 팝업은 게임 중에도 그대로 뜬다(실제 화재를 놓치면 안 된다).
 */
interface Tank { x: number; hp: number; angle: number; power: number; login: string | null; online: boolean }
interface Shot { seq: number; by: number; path: number[]; hit: boolean; x: number; y: number; damage: number[] }
interface DuelState {
  gameId: number; seat: number; w: number; h: number; seq: number; turn: number; winner: number;
  wind: number; windMax: number; ground: number[]; tanks: Tank[]; shot: Shot | null;
}
interface Boom { x: number; y: number; inst: FxInstance; frame: FxFrame; img: ImageData; canvas: HTMLCanvasElement }

const API = '/api/dashboard/duel';
const TANK_COLOR = ['#4aa8ff', '#ff5a4d'];
const TANK_DARK = ['#1f5f9e', '#9e2a22'];
const SEAT_NAME = ['왼쪽 전차', '오른쪽 전차'];
const FLY_SPEED = 42;   // 궤적 점(1/30초 간격)을 1초에 몇 개 지나갈지

async function call(method: 'GET' | 'POST', path = '', body?: unknown): Promise<DuelState> {
  const res = await fetch(API + path, {
    method, credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) window.dispatchEvent(new Event('auth:expired'));
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).message || msg; } catch { /* 본문 없음 */ }
    throw new Error(msg);
  }
  return res.json();
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export default function Duel() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hud, setHud] = useState<DuelState | null>(null);   // 화면에 보이는 상태(포탄이 나는 동안에는 쏘기 전 상태)
  const [aim, setAim] = useState({ angle: 60, power: 55 });
  const [flying, setFlying] = useState(false);
  const [error, setError] = useState('');
  const shown = useRef<DuelState | null>(null);
  const anim = useRef<{ shot: Shot; next: DuelState; i: number } | null>(null);
  const booms = useRef<Boom[]>([]);
  const aimRef = useRef(aim);
  aimRef.current = aim;

  // 서버 상태를 받아들인다: 새 발사가 있으면 궤적부터 그리고, 끝난 뒤에 바꾼다
  const accept = useCallback((s: DuelState) => {
    const adopt = (resetAim: boolean) => {
      anim.current = null;
      shown.current = s;
      setHud(s);
      setFlying(false);
      if (resetAim && s.seat >= 0) setAim({ angle: s.tanks[s.seat].angle, power: s.tanks[s.seat].power });
    };
    const cur = shown.current;
    if (!cur || cur.gameId !== s.gameId) { booms.current = []; adopt(true); return; }
    if (anim.current) { anim.current.next = s; return; }
    if (s.shot && s.seq > cur.seq) {
      anim.current = { shot: s.shot, next: s, i: 0 };
      setFlying(true);
      return;
    }
    adopt(false);
  }, []);

  useEffect(() => {
    let busy = false, alive = true;
    const poll = () => {
      if (busy) return;
      busy = true;
      call('GET').then((s) => { if (alive) { accept(s); setError(''); } }, (e: Error) => alive && setError(e.message))
        .finally(() => { busy = false; });
    };
    poll();
    const id = window.setInterval(poll, 400);
    return () => { alive = false; window.clearInterval(id); };
  }, [accept]);

  const seat = hud?.seat ?? -1;
  const myTurn = !!hud && seat >= 0 && hud.turn === seat && hud.winner < 0 && !flying;

  // 조준 값을 상대 화면에도 보이게 알린다(0.25초에 한 번)
  useEffect(() => {
    if (seat < 0) return;
    const id = window.setTimeout(() => { call('POST', '/aim', aim).catch(() => {}); }, 250);
    return () => window.clearTimeout(id);
  }, [aim, seat]);

  const fire = useCallback(() => {
    call('POST', '/fire', aimRef.current).then(accept, (e: Error) => setError(e.message));
  }, [accept]);
  const reset = () => { call('POST', '/reset').then(accept, (e: Error) => setError(e.message)); };
  const turnBy = (dAngle: number, dPower: number) => setAim((a) => ({
    angle: clamp(a.angle + dAngle, 0, 180), power: clamp(a.power + dPower, 5, 100),
  }));

  // 자판: ← → 각도, ↑ ↓ 세기(Shift 는 5씩), 스페이스 발사
  const keys = useRef({ myTurn, fire });
  keys.current = { myTurn, fire };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (seat < 0 || (e.target as HTMLElement).tagName === 'INPUT') return;
      const n = e.shiftKey ? 5 : 1;
      if (e.key === 'ArrowLeft') turnBy(n, 0);
      else if (e.key === 'ArrowRight') turnBy(-n, 0);
      else if (e.key === 'ArrowUp') turnBy(0, n);
      else if (e.key === 'ArrowDown') turnBy(0, -n);
      else if (e.key === ' ' || e.key === 'Enter') { if (keys.current.myTurn && !e.repeat) keys.current.fire(); }
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [seat]);

  // 그리기
  const ready = !!hud;
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    ctx.imageSmoothingEnabled = false;
    let raf = 0, last = 0;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = last ? Math.min((now - last) / 1000, 0.1) : 0;
      last = now;
      const a = anim.current;
      if (a) {
        a.i += dt * FLY_SPEED;
        if (a.i >= a.shot.path.length / 2 - 1) {
          if (a.shot.hit) booms.current.push(makeBoom(a.shot.x, a.shot.y, a.shot.seq));
          anim.current = null;
          shown.current = a.next;
          setHud(a.next);
          setFlying(false);
        }
      }
      const s = shown.current;
      if (s) draw(ctx, s, anim.current, aimRef.current, booms.current, dt);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [ready]);   // 캔버스는 첫 상태를 받은 뒤에야 생긴다

  const leave = () => playTransition({
    onCovered: () => {
      // 대시보드 전용 계정은 갈 곳이 대시보드뿐이라 모드를 끈다
      if (me?.role === 'DASHBOARD') setTheme('default');
      else if (me) navigate(homeOf(me.role));
    },
  });
  const canAct = !!me && me.role !== 'DASHBOARD';

  if (!hud) return <div className="center muted">{error || '불러오는 중…'}</div>;
  const shot = hud.shot;
  const wind = Math.round(hud.wind);
  const status = hud.winner === 2 ? '비겼습니다'
    : hud.winner >= 0 ? `${hud.tanks[hud.winner].login ?? SEAT_NAME[hud.winner]} 승리!`
      : flying ? '포탄이 날아가는 중…'
        : seat === hud.turn ? '내 차례입니다' : `${hud.tanks[hud.turn].login ?? SEAT_NAME[hud.turn]} 차례`;
  const lastLine = !shot || flying ? '' : !shot.hit ? '지난 포탄: 화면 밖으로 빗나감'
    : shot.damage.some((d) => d > 0)
      ? `지난 포탄: ${shot.damage.map((d, i) => (d > 0 ? `${hud.tanks[i].login ?? SEAT_NAME[i]} -${d}` : '')).filter(Boolean).join(', ')}`
      : '지난 포탄: 땅에 떨어짐';

  return (
    <div className="duel">
      <header className="duel-top">
        <Side tank={hud.tanks[0]} i={0} me={seat === 0} turn={hud.turn === 0 && hud.winner < 0} />
        <div className="duel-mid">
          <b>{status}</b>
          <span>바람 {wind === 0 ? '없음' : `${wind < 0 ? '←' : '→'} ${Math.abs(wind)}`}</span>
        </div>
        <Side tank={hud.tanks[1]} i={1} me={seat === 1} turn={hud.turn === 1 && hud.winner < 0} />
      </header>
      <div className="duel-field">
        <canvas ref={canvasRef} width={hud.w} height={hud.h} className="pixelfx" />
      </div>
      <footer className="duel-bottom">
        {seat >= 0 ? (
          <div className="duel-controls">
            <span className="duel-dial">각도
              <button onClick={() => turnBy(1, 0)} aria-label="각도 왼쪽으로">◀</button>
              <b>{Math.round(aim.angle)}°</b>
              <button onClick={() => turnBy(-1, 0)} aria-label="각도 오른쪽으로">▶</button>
            </span>
            <span className="duel-dial">세기
              <button onClick={() => turnBy(0, -1)} aria-label="세기 줄이기">▼</button>
              <b>{Math.round(aim.power)}</b>
              <button onClick={() => turnBy(0, 1)} aria-label="세기 올리기">▲</button>
            </span>
            <button className="primary duel-fire" disabled={!myTurn} onClick={fire}>발사</button>
          </div>
        ) : <span className="muted">구경 중 — 전차는 sup1 과 ADMIN 계정이 몹니다</span>}
        <span className="muted small duel-hint">{error || lastLine || (seat >= 0 ? '← → 각도 · ↑ ↓ 세기(Shift 5씩) · 스페이스 발사' : '')}</span>
        <span className="duel-buttons">
          {seat >= 0 && <button onClick={reset}><Icon name="arrow.triangle.2.circlepath" size={16} />새 판</button>}
          <button onClick={leave}><Icon name="rectangle.portrait.and.arrow.right" size={16} />나가기</button>
        </span>
      </footer>
      <LaunchDialog canDismiss={canAct} onOpen={(id) => canAct && navigate(`/app/incidents/${id}`)} />
      <EmergencyDialog canAck={canAct} onOpen={(a) => canAct && navigate(
        a.ref_kind === 'incident' ? `/app/incidents/${a.ref_id}`
          : a.ref_kind === 'observation' && a.task_id ? `/app/tasks/${a.task_id}/observations/${a.ref_id}`
            : '/app/alerts')} />
    </div>
  );
}

function Side({ tank, i, me, turn }: { tank: Tank; i: number; me: boolean; turn: boolean }) {
  return (
    <div className={`duel-side s${i} ${turn ? 'turn' : ''}`}>
      <div className="duel-name">
        <b style={{ color: TANK_COLOR[i] }}>{tank.login ?? SEAT_NAME[i]}</b>{me && <span className="tag">나</span>}
        <span className="muted small">{tank.online ? '접속 중' : '기다리는 중'}</span>
      </div>
      <div className="duel-hp" role="img" aria-label={`체력 ${tank.hp}`}>
        <i style={{ width: `${tank.hp}%`, background: tank.hp > 50 ? 'var(--green)' : tank.hp > 20 ? 'var(--orange)' : 'var(--red)' }} />
        <span>{tank.hp}</span>
      </div>
    </div>
  );
}

function makeBoom(x: number, y: number, seed: number): Boom {
  const [w, h] = smallExplosion.meta.size;
  const [ox, oy] = smallExplosion.meta.origin;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  return {
    x: x - ox, y: y - oy, canvas,
    inst: createFx(smallExplosion, { x: ox, y: oy, seed, size: 0.7 }),
    frame: createFrame(w, h),
    img: new ImageData(w, h),
  };
}

/** 한 장면 그리기. 경기장 좌표(640×360) 그대로 그리고 확대는 CSS 가 한다 */
function draw(ctx: CanvasRenderingContext2D, s: DuelState, a: { shot: Shot; i: number } | null,
              aim: { angle: number; power: number }, booms: Boom[], dt: number) {
  const { w, h, ground } = s;
  // 하늘: 띠 네 겹 + 별
  const sky = ['#14121f', '#1b1730', '#241e40', '#2f2752'];
  sky.forEach((c, i) => { ctx.fillStyle = c; ctx.fillRect(0, (h * i) / 5, w, h); });
  ctx.fillStyle = '#b8b2cc';
  let r = s.gameId % 2147483647;
  for (let i = 0; i < 48; i++) {
    r = (r * 48271) % 2147483647;
    const x = r % w;
    r = (r * 48271) % 2147483647;
    ctx.fillRect(x, r % 150, 1, 1);
  }
  // 땅: 흙 → 깊은 흙 → 풀
  ctx.fillStyle = '#6b4a3a';
  for (let x = 0; x < w; x++) ctx.fillRect(x, ground[x], 1, h - ground[x]);
  ctx.fillStyle = '#4a3229';
  for (let x = 0; x < w; x++) ctx.fillRect(x, ground[x] + 14 + ((x * 7) % 5), 1, h);
  ctx.fillStyle = '#5ee06a';
  for (let x = 0; x < w; x++) ctx.fillRect(x, ground[x], 1, 2);
  ctx.fillStyle = '#2f9e3c';
  for (let x = 0; x < w; x++) ctx.fillRect(x, ground[x] + 2, 1, 1 + (x % 3 === 0 ? 1 : 0));

  // 전차
  s.tanks.forEach((t, i) => {
    const gy = ground[t.x];
    const dead = t.hp <= 0;
    const angle = i === s.seat ? aim.angle : t.angle;
    const rad = (angle * Math.PI) / 180;
    ctx.fillStyle = dead ? '#3a3352' : '#d8d2c0';   // 포신
    for (let k = 3; k <= 13; k++) ctx.fillRect(Math.round(t.x + Math.cos(rad) * k) - 1, Math.round(gy - 8 - Math.sin(rad) * k) - 1, 2, 2);
    ctx.fillStyle = '#000';
    ctx.fillRect(t.x - 9, gy - 6, 18, 6);
    ctx.fillRect(t.x - 5, gy - 10, 10, 5);
    ctx.fillStyle = dead ? '#3a3352' : TANK_COLOR[i];
    ctx.fillRect(t.x - 8, gy - 5, 16, 3);
    ctx.fillRect(t.x - 4, gy - 9, 8, 4);
    ctx.fillStyle = dead ? '#211c33' : TANK_DARK[i];   // 바퀴
    ctx.fillRect(t.x - 8, gy - 2, 16, 2);
    // 내 차례 조준선: 세기만큼 긴 점선
    if (i === s.seat && s.turn === i && s.winner < 0 && !a) {
      ctx.fillStyle = '#f4f0e0';
      for (let k = 18; k < 18 + aim.power * 0.6; k += 5) ctx.fillRect(Math.round(t.x + Math.cos(rad) * k), Math.round(gy - 8 - Math.sin(rad) * k), 1, 1);
    }
    // 차례 표시: 전차 위 세모
    if (s.turn === i && s.winner < 0 && !a) {
      ctx.fillStyle = TANK_COLOR[i];
      for (let k = 0; k < 4; k++) ctx.fillRect(t.x - 3 + k, gy - 30 + k, 7 - k * 2, 1);
    }
  });

  // 날아가는 포탄 + 꼬리
  if (a) {
    const p = a.shot.path, n = p.length / 2;
    const at = Math.min(n - 1, Math.floor(a.i));
    for (let k = Math.max(0, at - 10); k <= at; k++) {
      ctx.fillStyle = k === at ? '#ffffff' : k > at - 4 ? '#ffe26b' : '#ff8a2a';
      const size = k === at ? 3 : 1;
      ctx.fillRect(p[k * 2] - (size >> 1), p[k * 2 + 1] - (size >> 1), size, size);
    }
  }

  // 폭발(pixelfx): 작은 캔버스에 그려 맞은 자리에 겹친다
  for (let i = booms.length - 1; i >= 0; i--) {
    const b = booms[i];
    b.inst.update(dt);
    if (b.inst.done()) { booms.splice(i, 1); continue; }
    clearFrame(b.frame);
    b.inst.draw(b.frame);
    composite(b.frame, b.img.data, null);
    b.canvas.getContext('2d')?.putImageData(b.img, 0, 0);
    ctx.drawImage(b.canvas, b.x, b.y);
  }
}
