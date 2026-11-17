// 점검 계획(= 예약, inspection_schedule) 화면 공통 문구.
import type { Schedule, ScheduleKind, ScheduleOutcome } from '../../../api/types';
import { Tag } from '../../../ui';

export const KIND_LABEL: Record<ScheduleKind, string> = {
  MANUAL: '수동', ONCE: '한 번', INTERVAL: '간격', DAILY: '매일', WEEKLY: '요일',
};
export const DAYS = ['월', '화', '수', '목', '금', '토', '일']; // 1=월 … 7=일

export const OUTCOME_LABEL: Record<ScheduleOutcome | 'QUEUED', string> = {
  CREATED: '작업 생성', SKIPPED_BUSY: '건너뜀 · 로봇 사용 중', SKIPPED_OFFLINE: '건너뜀 · 연결 안 됨',
  MISSED: '놓침 · 서버 중지', FAILED: '실패', CANCELLED: '대기 취소', QUEUED: '대기 중',
};
export const OUTCOME_CLASS: Record<ScheduleOutcome, string> = {
  CREATED: 'st-COMPLETED', SKIPPED_BUSY: 'st-CANCEL_REQUESTED', SKIPPED_OFFLINE: 'st-CANCEL_REQUESTED',
  MISSED: 'st-CANCEL_REQUESTED', FAILED: 'st-FAILED', CANCELLED: '',
};

export function Outcome({ o }: { o: ScheduleOutcome | null }) {
  return o ? <span className={`badge ${OUTCOME_CLASS[o]}`}>{OUTCOME_LABEL[o]}</span> : null;
}

/** 실행 방식을 한 줄로: "매일 09:00", "월·수·금 1시간마다 (09:00~18:00)", "실행할 때만" */
export function ruleText(s: Pick<Schedule, 'kind' | 'run_at_local' | 'time_of_day' | 'days_of_week' | 'interval_minutes' | 'window_start' | 'window_end'>) {
  const days = (d: number[] | null) => (d && d.length && d.length < 7 ? d.map((x) => DAYS[x - 1]).join('·') + ' ' : '');
  switch (s.kind) {
    case 'MANUAL': return '실행할 때만';
    case 'ONCE': return `${s.run_at_local?.replace('T', ' ')} 한 번`;
    case 'DAILY': return `매일 ${s.time_of_day}`;
    case 'WEEKLY': return `${days(s.days_of_week)}${s.time_of_day}`;
    case 'INTERVAL': {
      const m = s.interval_minutes ?? 0;
      const every = m % 60 === 0 ? `${m / 60}시간` : `${m}분`;
      const win = s.window_start ? ` (${s.window_start}~${s.window_end})` : '';
      return `${days(s.days_of_week)}${every}마다${win}`;
    }
  }
}

export function KindTag({ kind, enabled }: { kind: ScheduleKind; enabled: boolean }) {
  if (kind === 'MANUAL') return <Tag tone="indigo" icon="hand.raised.fill">수동</Tag>;
  return enabled ? <Tag tone="orange" icon="calendar.badge.clock">예약</Tag> : <Tag tone="gray">예약 꺼짐</Tag>;
}
