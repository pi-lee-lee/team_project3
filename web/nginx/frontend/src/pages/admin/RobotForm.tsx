import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { RobotSummary } from '../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Empty, Field, Group, Page, Picker, Switch } from '../../ui';
import './admin.css';

/** 새 로봇의 기본 연결 설정(시뮬레이션) */
const SIM_CONFIG = {
  rosbridgeUrl: 'ws://sim:9090',
  videoUrl: 'http://sim:8080',
  imageTransport: 'compressed', // 카메라 영상은 압축 토픽(<image>/compressed)으로 받는다. 'raw' 로 두면 원본
  topics: {
    odom: '/odom', scan: '/scan', camera: '/camera/camera_info', image: '/camera/image_raw',
    battery: '/battery_state', teleop: '/cmd_vel_teleop', goal: '/inspection/goal',
    goalCancel: '/inspection/goal_cancel', goalStatus: '/inspection/goal_status', bridge: '/inspection/bridge_status',
  },
};

/** A2-1 로봇 등록 · 연결 설정. 시뮬레이션 → 실제 로봇 교체는 주소·토픽만 바꾼다. */
export default function RobotForm() {
  const { id } = useParams<{ id: string }>();
  const robotId = id ? Number(id) : undefined;
  const api = useApi();
  const nav = useNavigate();
  const robots = usePoll(() => (robotId ? api.adminRobots() : Promise.resolve(null)), 0, [robotId]);
  const act = useAction();
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [adapterType, setAdapterType] = useState<RobotSummary['adapterType']>('ROSBRIDGE');
  const [enabled, setEnabled] = useState(true);
  const [config, setConfig] = useState(JSON.stringify(SIM_CONFIG, null, 2));
  const [loaded, setLoaded] = useState(!robotId);

  const robot = robotId ? robots.data?.find((r) => r.robotId === robotId) : undefined;
  useEffect(() => {
    if (!robot || loaded) return;
    setCode(robot.code);
    setName(robot.name);
    setAdapterType(robot.adapterType);
    setEnabled(robot.enabled);
    setConfig(JSON.stringify(robot.config ?? {}, null, 2));
    setLoaded(true);
  }, [robot, loaded]);

  const back = robotId ? { to: `/admin/robots/${robotId}`, label: robot?.code ?? '로봇' } : { to: '/admin/robots', label: '로봇' };
  const title = robotId ? '연결 설정' : '로봇 등록';

  const save = () => act.run(async () => {
    let cfg: unknown;
    try { cfg = JSON.parse(config); } catch { throw new Error('연결 설정이 올바른 JSON 이 아닙니다'); }
    const saved = await api.saveRobot({ robotId, code: robotId ? undefined : code, name, adapterType, config: cfg, enabled });
    nav(robotId ? `/admin/robots/${robotId}` : saved?.robotId ? `/admin/robots/${saved.robotId}` : '/admin/robots');
  });

  if (robotId && !loaded) {
    return (
      <Page title={title} width="narrow" back={back}>
        <ErrorBox msg={robots.error} />
        {robots.data && !robot && <Empty icon="cpu" title="로봇을 찾을 수 없습니다" />}
      </Page>
    );
  }

  return (
    <Page title={title} sub={robotId ? `${code} · ${name}` : undefined} width="narrow" back={back}>
      <Group>
        {!robotId && (
          <Field label="코드"><input value={code} placeholder="tb3-real" autoComplete="off" onChange={(e) => setCode(e.target.value)} /></Field>
        )}
        <Field label="이름"><input value={name} placeholder="필수" onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="어댑터">
          <Picker<RobotSummary['adapterType']> variant="field" label="어댑터" value={adapterType} onChange={setAdapterType}
            options={[
              { value: 'ROSBRIDGE', label: 'ROSBRIDGE', sub: '시뮬레이션·실제 TurtleBot3' },
              { value: 'MOCK', label: 'MOCK', sub: 'ROS 없이 시험' },
            ]} />
        </Field>
        <Field label="사용"><Switch label="사용" checked={enabled} onChange={setEnabled} /></Field>
      </Group>

      <Group footer="실제 로봇: rosbridgeUrl 을 ws://로봇IP:9090, videoUrl 을 http://로봇IP:8080 으로 바꾸고 로봇에서 rosbridge·web_video_server·목표 브리지를 실행합니다. 카메라는 압축 토픽(compressed_image_transport)을 발행해야 합니다.">
        <Field stack label="연결 설정 (rosbridge 주소, 영상 주소, 토픽 이름)">
          <textarea rows={14} value={config} spellCheck={false} className="mono" onChange={(e) => setConfig(e.target.value)} />
        </Field>
      </Group>

      <ErrorBox msg={act.error} />
      <ActionBar>
        <button type="button" onClick={() => nav(back.to)}>취소</button>
        <button type="button" className="primary" disabled={act.busy || !name || (!robotId && !code)} onClick={save}>저장·재연결</button>
      </ActionBar>
    </Page>
  );
}
