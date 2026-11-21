import { useSyncExternalStore } from 'react';
import { Icon } from './Icon';
import { playTransition } from './PixelFx';

/**
 * 화면 모드: 기본(Apple HIG) / 픽셀. 픽셀 모드는 숨은 기능(이스터 에그)이다.
 *  - 켜는 단추는 로그인 화면에서 로고를 3초 안에 10번 눌러야 나온다(Login.tsx). 그 사실은 어디에도 저장하지 않는다
 *  - 고른 모드는 이 창(탭)에서만 유지한다(sessionStorage): 새로고침에는 남고, 창을 새로 띄우면 기본 모드다
 * 픽셀 모드는 <html data-theme="pixel"> 하나로 켜지고, 모양은 pixel.css 가 맡는다.
 * 픽셀 모드에서 /dashboard 는 관제 대시보드 대신 포격전(pages/dashboard/Duel.tsx)을 띄운다.
 */
export type Theme = 'default' | 'pixel';

const KEY = 'ui.theme';
const listeners = new Set<() => void>();

function read(): Theme {
  try {
    localStorage.removeItem(KEY);   // 예전 시제품이 브라우저에 남긴 값은 지운다
    return sessionStorage.getItem(KEY) === 'pixel' ? 'pixel' : 'default';
  } catch { return 'default'; }
}
let theme: Theme = read();

/** 고른 모드를 <html> 에 반영한다 */
export function applyTheme() {
  if (theme === 'pixel') document.documentElement.dataset.theme = 'pixel';
  else delete document.documentElement.dataset.theme;
}

export function setTheme(next: Theme) {
  theme = next;
  try { sessionStorage.setItem(KEY, next); } catch { /* 저장 안 됨: 새로고침 전까지만 유지 */ }
  applyTheme();
  listeners.forEach((fn) => fn());
}

export const getTheme = () => theme;

export function useTheme(): Theme {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, getTheme);
}

/** 모드 전환 단추. 전환 연출이 화면을 다 덮은 순간에 모드를 바꾼다 */
export function ThemeToggle({ className = 'link' }: { className?: string }) {
  const now = useTheme();
  const next: Theme = now === 'pixel' ? 'default' : 'pixel';
  return (
    <button type="button" className={`theme-toggle ${className}`} onClick={() => playTransition({ onCovered: () => setTheme(next) })}>
      <Icon name="gamecontroller.fill" size={16} />{now === 'pixel' ? '기본 모드' : '픽셀 모드'}
    </button>
  );
}
