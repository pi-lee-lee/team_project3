import { useEffect, useRef } from 'react';
import type { DemoStatus } from '../../api/types';
import { ErrorBox, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { Group, Notice, Page, Tag } from '../../ui';
import './admin.css';

const STATE: Record<string, [string, 'blue' | 'green' | 'red' | 'orange']> = {
  RUNNING: ['실행 중', 'blue'], DONE: ['끝남', 'green'], FAILED: ['실패', 'red'], STOPPED: ['중지됨', 'orange'],
};
const LEVEL_ICON: Record<string, string> = {
  step: 'play.fill', wait: 'clock', info: 'chevron.right', ok: 'checkmark.circle.fill',
  warn: 'exclamationmark.triangle.fill', error: 'xmark.circle.fill',
};

/**
 * 시연: 시나리오를 단추 하나로 실행한다(시뮬레이션 전용).
 * 단추를 누르면 서버(DemoService)가 시뮬레이션 대상 바꾸기 · 설정 · 점검 시작 · 기다리기를 차례로 하고, 진행 기록을 여기에 보여 준다.
 * 같은 일을 터미널에서는 scripts/demo.py 로 한다.
 */
export default function Demo() {
  const api = useApi();
  const q = usePoll<DemoStatus>(() => api.demo(), 1500);
  const act = useAction();
  const run = q.data?.run ?? null;
  const running = run?.state === 'RUNNING';
  const logEnd = useRef<HTMLDivElement>(null);
  useEffect(() => { logEnd.current?.scrollIntoView({ block: 'nearest' }); }, [run?.log.length]);

  const start = (key: string, name: string) => {
    if (!window.confirm(`'${name}' 시나리오를 실행합니다. 시뮬레이션의 로봇이 실제로 움직입니다.`)) return;
    act.run(async () => { q.setData(await api.runDemo(key)); });
  };
  const groups = [...new Set((q.data?.scenarios ?? []).map((s) => s.group))];

  return (
    <Page title="시연" sub="시나리오를 단추 하나로 실행합니다 (시뮬레이션 전용)">
      <Notice tone="info">
        단추를 누르면 시뮬레이션의 대상(열화상 인쇄물 · 소화기 · 표시등 · 계기판)을 바꾸고 점검 · 화재 대응을 자동으로 진행합니다.
        비상 팝업과 투척 승인 팝업은 <b>사용자 화면</b>(user1 등)이나 <b>대시보드</b>(dash1)를 다른 창에 띄워 두고 보세요. 한 번에 하나만 실행됩니다.
      </Notice>
      <ErrorBox msg={act.error ?? q.error} />
      {groups.map((g) => (
        <Group key={g} header={g}>
          {q.data!.scenarios.filter((s) => s.group === g).map((s) => (
            <div key={s.key} className="demo-row">
              <div className="demo-text">
                <b>{s.name}</b>{run?.key === s.key && <Tag tone={STATE[run.state][1]}>{STATE[run.state][0]}</Tag>}
                <p>{s.description}</p>
              </div>
              <button className="primary" disabled={running || act.busy} onClick={() => start(s.key, s.name)}>
                <Icon name="play.fill" size={16} />실행
              </button>
            </div>
          ))}
        </Group>
      ))}
      <Group header={run ? `진행 기록 — ${run.name} · ${STATE[run.state][0]} · ${run.by} · ${fmtTime(run.startedAt, false)} 시작` : '진행 기록'}>
        {!run ? <p className="muted demo-empty">아직 실행한 시나리오가 없습니다</p> : (
          <div className="demo-log" role="log" aria-live="polite">
            {run.log.map((l, i) => (
              <div key={i} className={`demo-line lv-${l.level}`}>
                <span className="mono">{fmtTime(l.at, false)}</span>
                <Icon name={LEVEL_ICON[l.level] ?? 'chevron.right'} size={16} />
                <span>{l.text}</span>
              </div>
            ))}
            {running && <div className="demo-line lv-wait"><span className="mono" /><Icon name="clock" size={16} /><span>진행 중…</span></div>}
            <div ref={logEnd} />
          </div>
        )}
        {running && (
          <div className="demo-foot">
            <button className="danger" disabled={act.busy} onClick={() => act.run(async () => { q.setData(await api.stopDemo()); })}>
              <Icon name="stop.fill" size={16} />중지
            </button>
            <span className="muted small">중지해도 이미 시작된 로봇 동작은 계속됩니다. 정리는 '초기화' 시나리오로 합니다.</span>
          </div>
        )}
      </Group>
    </Page>
  );
}
