// 작업·관측 화면이 함께 쓰는 표시 문구 (진행 기록 이름, 판정 이름, 품질 요약).
import type { Observation, TaskEvent } from '../../api/types';
import { ReasonBadge } from '../../util';
import { Tag } from '../../ui';

export const EVENT_LABEL: Record<string, string> = {
  REQUESTED: '요청됨', ACCEPTED: '로봇 접수', DISPATCH_FAILED: '로봇 전달 실패', DISPATCH_UNKNOWN: '전달 결과 불명',
  PREFLIGHT_OK: '출발 전 검사 통과', PREFLIGHT_FAILED: '출발 전 검사 실패', STARTED: '출발', MOVING: '이동 시작',
  ARRIVED: '도착', ARRIVAL_FAILED: '도착 실패', ARRIVAL_BLOCKED: '진입 불가 (경로 없음)', OBSERVATION_SAVED: '촬영 저장', OBSERVATION_UNABLE: '확인 불가',
  COMPLETED: '완료', CANCEL_REQUESTED: '취소 요청', CANCELLED: '취소됨', CANCEL_NOT_APPLIED: '취소 미적용',
  CANCEL_SEND_FAILED: '취소 전달 실패', MISSION_FAILED: '실패', MISSION_INTERRUPTED: '중단(상태 불명)',
  EMERGENCY_STOP: '비상 정지', REVIEWED: '사람 판정',
  // 시나리오: 규칙 판독 · 화재 출동
  RULES_CHECKED: '규칙 판독', PREEMPTED: '화재 출동으로 중단', HOLDING: '투척 위치 도착 · 대기',
  ACTUATED: '투척 완료', ACTUATE_FAILED: '투척 실패',
};

/** 규칙 등급 이름 */
const GRADE_KO: Record<string, string> = { NORMAL: '정상', WARNING: '경고', EMERGENCY: '비상', UNKNOWN: '판독 불가' };

export const SOURCE: Record<TaskEvent['source'], string> = { USER: '사용자', ROBOT: '로봇', SYSTEM: '시스템' };

/** 사람 판정: [이름, 글자색 class] */
export const RESULT: Record<string, [string, string]> = { NORMAL: ['정상', 'ok'], ABNORMAL: ['이상', 'warn-t'], UNABLE: ['확인 불가', 'warn-t'] };   // '이상'도 경고 색. 빨강은 비상(화재)만

export function eventText(e: TaskEvent) {
  const d = e.detail || {};
  const parts: string[] = [];
  if (d.code || d.pointCode) parts.push(String(d.code ?? d.pointCode));
  if (Array.isArray(d.points)) parts.push((d.points as string[]).join(', '));
  if (d.result) parts.push(RESULT[String(d.result)]?.[0] ?? String(d.result));
  if (d.grade) parts.push(GRADE_KO[String(d.grade)] ?? String(d.grade));
  if (typeof d.launched === 'number') parts.push(`${d.launched}발`);
  if (d.reason) parts.push(String(d.reason));
  if (d.recoveries) parts.push(`복구 동작 ${d.recoveries}회`);
  if (Array.isArray(d.reasons)) parts.push((d.reasons as string[]).join(', '));
  if (d.robotState) parts.push(`로봇 상태 ${d.robotState}`);
  if (d.captured !== undefined) parts.push(`촬영 ${d.captured} · 확인 불가 ${d.unable}`);
  return parts.join(' · ');
}

export function ResultText({ result }: { result: string | null | undefined }) {
  if (!result) return <span className="muted">판정 없음</span>;
  const [label, cls] = RESULT[result] ?? [result, ''];
  return <span className={cls}>{label}</span>;
}

/** 관측 한 줄 요약: 확인 불가 사유 또는 품질 분석 결과 + 사람 판정 */
export function ObservationSummary({ o }: { o: Observation }) {
  return (
    <>
      {o.status === 'UNABLE'
        ? <span className="warn-t"><ReasonBadge code={o.reason_code} />{o.reason ?? '확인 불가'}</span>
        : o.verdict === 'OK' ? <span className="ok">품질 양호</span>
          : o.verdict === 'RETAKE' ? <span className="warn-t">재촬영 후보</span>
            : <span>품질 분석 중…</span>}
      {' · '}<ResultText result={o.review_result} />
    </>
  );
}

const REVIEW_TAG: Record<string, [string, 'green' | 'red' | 'orange']> = { NORMAL: ['정상', 'green'], ABNORMAL: ['이상', 'orange'], UNABLE: ['확인 불가', 'orange'] };   // 빨강은 비상(화재)만

/** 관측 꼬리표: 촬영·품질(양호/재촬영 후보/분석 중/확인 불가) + 사람 판정 */
export function ObservationTags({ o }: { o: Observation }) {
  const r = o.review_result ? REVIEW_TAG[o.review_result] : null;
  return (
    <>
      {o.status === 'UNABLE'
        ? <Tag tone="orange" icon="exclamationmark.triangle.fill">확인 불가</Tag>
        : o.verdict === 'OK' ? <Tag tone="green" icon="photo">품질 양호</Tag>
          : o.verdict === 'RETAKE' ? <Tag tone="orange" icon="photo">재촬영 후보</Tag>
            : <Tag tone="gray" icon="photo">분석 중</Tag>}
      {r ? <Tag tone={r[1]} icon="checkmark.circle.fill">판정 {r[0]}</Tag> : <Tag tone="gray">판정 없음</Tag>}
      {o.recheck_of && <Tag tone="purple" icon="arrow.uturn.backward">재점검</Tag>}
    </>
  );
}
