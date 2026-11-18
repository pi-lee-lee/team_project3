import { useEffect, useState } from 'react';
import { useApi } from './util';
import { Icon } from './Icon';

type Sync = { offsetMs: number; rttMs: number; zone: string; utcOffset: string; at: number };

/** 기기 시계와의 차이를 읽기 쉬운 말로 */
function diffText(ms: number) {
  const a = Math.abs(ms);
  if (a < 1000) return '기기 시계와 같음(1초 이내)';
  const s = a / 1000;
  const v = s < 60 ? `${s.toFixed(1)}초` : s < 3600 ? `${Math.floor(s / 60)}분 ${Math.round(s % 60)}초` : `${(s / 3600).toFixed(1)}시간`;
  return `서버가 기기보다 ${v} ${ms > 0 ? '빠름' : '느림'}`;
}

/**
 * 서버 시간 확인 단추(사이드바·모바일 계정 칸의 사용자 영역).
 * 누르면 게이트웨이 /api/time 을 한 번 불러 기기 시계와의 차이(왕복 시간의 절반을 보정)를 구하고,
 * 그 차이를 더해 서버 시간을 1초마다 흘려 보여 준다. 예약 점검은 이 서버 시계·시간대로 돈다.
 */
export function ServerClock() {
  const api = useApi();
  const [open, setOpen] = useState(false);
  const [sync, setSync] = useState<Sync | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [, tick] = useState(0);

  const load = async () => {
    setErr(null);
    try {
      const t0 = performance.now(), d0 = Date.now();
      const r = await api.serverTime();
      const rtt = performance.now() - t0;
      setSync({ offsetMs: r.epochMs + rtt / 2 - (d0 + rtt), rttMs: rtt, zone: r.zone, utcOffset: r.offset, at: Date.now() });
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  useEffect(() => {
    if (!open) return;
    const h = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(h);
  }, [open]);

  const now = sync ? new Date(Date.now() + sync.offsetMs) : null;
  const fmt = (o: Intl.DateTimeFormatOptions) => (now && sync ? new Intl.DateTimeFormat('ko-KR', { timeZone: sync.zone, ...o }).format(now) : '');

  return (
    <div className={`server-clock ${open ? 'open' : ''}`}>
      <button type="button" className="clock-btn" aria-expanded={open}
        onClick={() => { const v = !open; setOpen(v); if (v) load(); }}>
        <Icon name="clock" size={16} />서버 시간
        <Icon name={open ? 'chevron.up.chevron.down' : 'chevron.right'} size={14} className="clock-chev" />
      </button>
      {open && (
        <div className="clock-panel" role="status" aria-live="polite">
          {err ? <div className="bad small">{err}</div> : !sync ? <div className="muted small">불러오는 중…</div> : <>
            <div className="clock-time">{fmt({ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</div>
            <div className="clock-date">{fmt({ year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })}</div>
            <div className="clock-meta">{sync.zone} (UTC{sync.utcOffset === 'Z' ? '+00:00' : sync.utcOffset})</div>
            <div className={`clock-meta ${Math.abs(sync.offsetMs) >= 5000 ? 'warn-t' : ''}`}>{diffText(sync.offsetMs)}</div>
            <button type="button" className="link clock-refresh" onClick={load}><Icon name="arrow.triangle.2.circlepath" size={14} />다시 맞추기</button>
          </>}
        </div>
      )}
    </div>
  );
}
