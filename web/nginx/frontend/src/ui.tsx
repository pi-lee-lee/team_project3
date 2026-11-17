// 화면 공통 부품 (Apple Human Interface Guidelines 형식).
// 화면은 "한 화면 = 한 가지 일" 로 나눈다: 목록 → 상세 → 편집(폼). 같은 화면이 스마트폰·태블릿·PC 에서 그대로 쓰인다.
//  - Page      : 큰 제목 + 뒤로(상위 화면) + 오른쪽 동작 버튼 (iOS 내비게이션 바)
//  - Group     : 그룹형 목록(inset grouped) — 머리말·꼬리말 포함
//  - Row       : 목록 칸. to 가 있으면 칸 전체가 링크이고 오른쪽에 › 가 붙는다
//  - Field     : 폼 칸(왼쪽 이름표, 오른쪽 입력). 좁은 화면에서는 위아래로 쌓인다
//  - Switch / Segmented / Picker / ActionBar / Empty
//  - 목록 칸 안 정보: Tag(색 꼬리표) · PointBadge(지점 코드) · RouteChips(방문 순서) · RobotChip · Meta(아이콘+글) · MetaLine · Avatar
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from './Icon';

export function Page({ title, back, actions, children, width = 'normal', sub }: {
  title: ReactNode;
  back?: { to: string; label: string };
  actions?: ReactNode;
  children: ReactNode;
  /** narrow: 폼·상세(680px) / normal: 목록(900px) / wide: 관제·대시보드(제한 없음) */
  width?: 'narrow' | 'normal' | 'wide';
  sub?: ReactNode;
}) {
  return (
    <section className={`page page-${width}`}>
      <div className="navbar">
        {back ? (
          <Link className="back" to={back.to}><Icon name="chevron.left" size={22} />{back.label}</Link>
        ) : <span />}
        <div className="nav-actions">{actions}</div>
      </div>
      <h2 className="large-title">{title}</h2>
      {sub && <div className="page-sub">{sub}</div>}
      {children}
    </section>
  );
}

export function Group({ header, footer, children, className = '' }: {
  header?: ReactNode; footer?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <div className={`group-wrap ${className}`}>
      {header && <div className="group-header">{header}</div>}
      <div className="group">{children}</div>
      {footer && <div className="group-footer">{footer}</div>}
    </div>
  );
}

export function Row({ to, onClick, icon, iconColor, title, subtitle, detail, right, destructive, rich, className = '' }: {
  to?: string;
  onClick?: () => void;
  icon?: string;
  iconColor?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  detail?: ReactNode;
  right?: ReactNode;
  destructive?: boolean;
  /** 여러 줄 정보 칸: 아이콘·제목을 위쪽에 맞추고 줄 사이를 띄운다 */
  rich?: boolean;
  className?: string;
}) {
  const body = (
    <>
      {icon && <span className="cell-icon" style={iconColor ? { background: iconColor } : undefined}><Icon name={icon} size={18} /></span>}
      <span className="cell-main">
        <span className="cell-title">{title}</span>
        {subtitle && <span className="cell-sub">{subtitle}</span>}
      </span>
      {detail !== undefined && <span className="cell-detail">{detail}</span>}
      {right}
      {to && <Icon name="chevron.right" size={20} className="chev" />}
    </>
  );
  const cls = `cell ${to || onClick ? 'tappable' : ''} ${destructive ? 'destructive' : ''} ${rich ? 'rich' : ''} ${className}`;
  if (to) return <Link className={cls} to={to}>{body}</Link>;
  if (onClick) return <button type="button" className={cls} onClick={onClick}>{body}</button>;
  return <div className={cls}>{body}</div>;
}

export function Field({ label, children, stack, hint }: { label: ReactNode; children: ReactNode; stack?: boolean; hint?: ReactNode }) {
  return (
    <label className={`cell field ${stack ? 'stack' : ''}`}>
      <span className="field-label">{label}</span>
      <span className="field-control">{children}{hint && <span className="field-hint">{hint}</span>}</span>
    </label>
  );
}

export function Switch({ checked, onChange, disabled, label }: {
  checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: string;
}) {
  return (
    <input type="checkbox" role="switch" className="switch" aria-label={label} checked={checked} disabled={disabled}
      onChange={(e) => onChange(e.target.checked)} onClick={(e) => e.stopPropagation()} />
  );
}

export function Segmented<T extends string>({ value, options, onChange, full }: {
  value: T; options: [T, string][]; onChange: (v: T) => void; full?: boolean;
}) {
  return (
    <div className={`segmented ${full ? 'full' : ''}`} role="tablist">
      {options.map(([v, label]) => (
        <button key={v} type="button" role="tab" aria-selected={value === v} className={value === v ? 'on' : ''}
          onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

/** 폼·상세 화면 아래쪽 동작 버튼. 스마트폰에서는 탭 바 위에 붙어 있다. */
export function ActionBar({ children }: { children: ReactNode }) {
  return <div className="action-bar">{children}</div>;
}

export function Empty({ icon = 'tray', title, children }: { icon?: string; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} size={40} />
      <div className="empty-title">{title}</div>
      {children && <div className="muted small">{children}</div>}
    </div>
  );
}

/** 알림 줄(성공·안내). 오류는 util 의 ErrorBox. */
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'ok' | 'warn' }) {
  return <div className={`notice notice-${tone}`}>{children}</div>;
}

export type PickerOption<T> = { value: T; label: string; sub?: string; disabled?: boolean };

/**
 * 고르기 단추(iOS 풀다운 메뉴 형식). "이름표 | 값 ⌄" 한 덩어리이고, 누르면 목록이 단추 바로 아래에 같은 폭으로 열린다.
 * 브라우저 기본 select 는 macOS 에서 목록이 단추 위에 겹쳐 열려 위치가 어긋나 보이므로 직접 그린다.
 * 키보드: ↑↓ 이동, Enter·Space 선택, Esc 닫기. 바깥을 누르거나 화면을 굴리면 닫힌다.
 * 목록은 화면 기준(position: fixed)으로 띄운다 — 그룹형 목록의 둥근 모서리(overflow: hidden)에 잘리지 않게.
 * 단추 아래에 자리가 모자라면 위로 연다.
 */
export function Picker<T extends string | number>({ label, icon, value, options, onChange, placeholder = '선택', variant = 'pill', disabled }: {
  label?: string; icon?: string; value: T | null; options: PickerOption<T>[]; onChange: (v: T) => void; placeholder?: string;
  /** pill: 이름표 | 값 한 덩어리(관제 상단 등) / field: 폼 칸 오른쪽 값(iOS 설정 앱 형식, 이름표는 Field 가 단다) */
  variant?: 'pill' | 'field';
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState(-1);
  const box = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  const [pos, setPos] = useState<CSSProperties>({ visibility: 'hidden' });
  const current = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const close = (e: Event) => { if (!menu.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', away);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('pointerdown', away);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);

  // 목록 자리 정하기: 단추 바로 아래 6px(모자라면 위), pill 은 단추 왼쪽 끝·같은 폭, field 는 단추 오른쪽 끝에 맞춘다
  useLayoutEffect(() => {
    if (!open || !btn.current || !menu.current) return;
    const b = btn.current.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight, edge = 8, gap = 6;
    const h = menu.current.scrollHeight;
    const below = vh - b.bottom - gap - edge, above = b.top - gap - edge;
    const down = below >= Math.min(h, 320) || below >= above;
    const st: CSSProperties = { position: 'fixed', maxHeight: Math.max(120, Math.min(320, down ? below : above)), maxWidth: vw - 2 * edge };
    if (down) st.top = b.bottom + gap; else st.bottom = vh - b.top + gap;
    if (variant === 'field') {
      st.right = Math.max(edge, vw - b.right);
    } else {
      // 단추 왼쪽 끝에 맞추되, 목록이 화면 오른쪽을 넘으면 그만큼 왼쪽으로 민다
      const w = Math.min(Math.max(menu.current.scrollWidth, b.width), vw - 2 * edge);
      st.left = Math.min(Math.max(edge, b.left), vw - edge - w);
      st.minWidth = Math.min(b.width, vw - 2 * edge);
    }
    setPos(st);
  }, [open, variant]);

  const openMenu = () => { setPos({ visibility: 'hidden' }); setFocus(Math.max(0, options.findIndex((o) => o.value === value))); setOpen(true); };
  const choose = (o: PickerOption<T>) => { if (o.disabled) return; onChange(o.value); setOpen(false); btn.current?.focus(); };
  const key = (e: React.KeyboardEvent) => {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); openMenu(); }
      return;
    }
    if (e.key === 'Escape') { e.preventDefault(); setOpen(false); btn.current?.focus(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setFocus((i) => Math.min(options.length - 1, i + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setFocus((i) => Math.max(0, i - 1)); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (options[focus]) choose(options[focus]); }
    else if (e.key === 'Tab') setOpen(false);
  };

  return (
    <div className={`picker picker-${variant}`} ref={box} onKeyDown={key}>
      {label && variant === 'pill' && <span className="picker-label">{icon && <Icon name={icon} size={16} />}{label}</span>}
      <div className="picker-field">
        <button ref={btn} type="button" className="picker-btn" aria-haspopup="listbox" aria-expanded={open}
          aria-label={label} disabled={disabled} onClick={(e) => { e.preventDefault(); if (open) setOpen(false); else openMenu(); }}>
          <span className="picker-value">{current?.label ?? placeholder}</span>
          <Icon name="chevron.up.chevron.down" size={18} />
        </button>
        {open && (
          <ul ref={menu} className="picker-menu" role="listbox" aria-label={label} style={pos}>
            {options.map((o, i) => (
              <li key={String(o.value)}>
                <button type="button" role="option" aria-selected={o.value === value} disabled={o.disabled}
                  className={`option ${i === focus ? 'focus' : ''}`}
                  onMouseEnter={() => setFocus(i)} onClick={(e) => { e.preventDefault(); choose(o); }}>
                  <span className="check">{o.value === value && <Icon name="checkmark" size={18} />}</span>
                  <span className="opt-label">{o.label}</span>
                  {o.sub && <span className="opt-sub">{o.sub}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 목록 칸 안 정보 부품
export type Tone = 'blue' | 'green' | 'orange' | 'red' | 'teal' | 'indigo' | 'purple' | 'gray';

/** 색 꼬리표(캡슐). 상태·종류·결과처럼 "어느 쪽인지" 를 한눈에 구분할 때 쓴다 */
export function Tag({ tone = 'gray', icon, children, title }: { tone?: Tone; icon?: string; children: ReactNode; title?: string }) {
  return <span className={`tag tone-${tone}`} title={title}>{icon && <Icon name={icon} size={13} />}{children}</span>;
}

/** 지점 코드 배지(지도에서 점검 지점을 그리는 청록색) */
export function PointBadge({ code, name }: { code: string; name?: string }) {
  return <span className="pt" title={name}>{code}</span>;
}

/** 점검 구간: 지점 코드를 배지로 나누고 › 로 이어 방문 순서를 보여 준다. points 는 "P1 → P2" 또는 "P1, P2" 문자열이나 배열 */
export function RouteChips({ points, names }: { points: string | string[] | null | undefined; names?: Record<string, string> }) {
  const codes = Array.isArray(points) ? points : (points ?? '').split(/\s*(?:→|,)\s*/).filter(Boolean);
  if (!codes.length) return null;
  return (
    <span className="route" aria-label={`점검 구간 ${codes.join(', ')}`}>
      {codes.map((c, i) => (
        <span key={`${c}-${i}`} className="route-step">
          {i > 0 && <Icon name="chevron.right" size={14} className="route-sep" />}
          <PointBadge code={c} name={names?.[c]} />
        </span>
      ))}
    </span>
  );
}

/** 로봇 칩: 코드 + 연결 점(초록=연결, 회색=끊김) */
export function RobotChip({ code, online }: { code: string; online?: boolean }) {
  return (
    <span className="chip-robot">
      <Icon name="cpu" size={14} />{code}
      {online !== undefined && <span className={`dot ${online ? 'on' : 'off'}`} aria-label={online ? '연결됨' : '연결 안 됨'} />}
    </span>
  );
}

/** 아이콘 + 짧은 정보(사람·시각·개수 등) */
export function Meta({ icon, children, strong, tone }: { icon: string; children: ReactNode; strong?: boolean; tone?: Tone }) {
  return <span className={`meta ${strong ? 'strong' : ''} ${tone ? `tone-text-${tone}` : ''}`}><Icon name={icon} size={15} />{children}</span>;
}

/** 칸 안 정보 한 줄(줄바꿈 허용) */
export function MetaLine({ children }: { children: ReactNode }) {
  return <span className="meta-line">{children}</span>;
}

/** 이름 첫 글자 원형 아바타(사람 목록) */
export function Avatar({ name, tone = 'blue' }: { name: string; tone?: Tone }) {
  return <span className={`avatar tone-solid-${tone}`} aria-hidden>{(name || '?').trim().slice(0, 1).toUpperCase()}</span>;
}
