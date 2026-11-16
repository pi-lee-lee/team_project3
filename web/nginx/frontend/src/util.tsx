import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { Api, Me } from './api/types';
import { httpApi } from './api/http';

export const ApiContext = createContext<Api>(httpApi);
export const useApi = () => useContext(ApiContext);

export const AuthContext = createContext<{ me: Me | null; setMe: (m: Me | null) => void }>({
  me: null,
  setMe: () => {},
});
export const useAuth = () => useContext(AuthContext);

export const ROLE_LABEL: Record<string, string> = {
  ADMIN: 'ADMIN', SUPERVISOR: '1 관리자', MANAGER: '2 매니저', USER: '3 사용자',
};

export const STATUS_LABEL: Record<string, string> = {
  REQUESTED: '요청됨', DISPATCHED: '접수됨', RUNNING: '진행 중', CANCEL_REQUESTED: '취소 요청',
  COMPLETED: '완료', FAILED: '실패', CANCELLED: '취소됨', INTERRUPTED: '중단(상태 불명)',
};

/** 확인 불가 사유 분류 (로봇·서버가 붙이는 코드) */
export const REASON_LABEL: Record<string, string> = {
  BLOCKED_NO_PATH: '통로 막힘 · 진입 불가', NAV_FAILED: '주행 실패', NO_PROGRESS: '진행 불가',
  NAV_UNAVAILABLE: '주행 시스템 준비 안 됨', PREFLIGHT_FAILED: '출발 전 검사 실패', CAPTURE_FAILED: '촬영 실패',
  TIMEOUT: '시간 초과',
};

export function ReasonBadge({ code }: { code: string | null | undefined }) {
  if (!code) return null;
  return <span className={`reason rc-${code}`}>{REASON_LABEL[code] ?? code}</span>;
}

export const TERMINAL = ['COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'];

export function fmtTime(v: string | number | null | undefined, withDate = true) {
  if (v === null || v === undefined) return '-';
  const d = new Date(v);
  if (isNaN(d.getTime())) return String(v);
  const t = d.toLocaleTimeString('ko-KR', { hour12: false });
  return withDate ? `${d.getMonth() + 1}/${d.getDate()} ${t}` : t;
}

export function ago(v: string | number | null | undefined) {
  if (!v) return '-';
  const s = (Date.now() - new Date(v).getTime()) / 1000;
  if (s < 60) return `${Math.max(0, Math.round(s))}초 전`;
  if (s < 3600) return `${Math.round(s / 60)}분 전`;
  if (s < 86400) return `${Math.round(s / 3600)}시간 전`;
  return `${Math.round(s / 86400)}일 전`;
}

/** 주기적으로 불러오는 데이터. */
export function usePoll<T>(load: () => Promise<T>, ms: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef(load);
  ref.current = load;
  const reload = () =>
    ref.current().then(
      (d) => { setData(d); setError(null); },
      (e) => setError(e.message),
    );
  useEffect(() => {
    reload();
    if (!ms) return;
    const h = setInterval(reload, ms);
    return () => clearInterval(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, reload, setData };
}

export function Badge({ status }: { status: string }) {
  return <span className={`badge st-${status}`}>{STATUS_LABEL[status] ?? status}</span>;
}

export function ErrorBox({ msg }: { msg: string | null | undefined }) {
  return msg ? <div className="error">{msg}</div> : null;
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, run, setError };
}
