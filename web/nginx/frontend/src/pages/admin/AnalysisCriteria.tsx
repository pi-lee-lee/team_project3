import { useEffect, useState } from 'react';
import type { Criteria } from '../../api/types';
import { ErrorBox, useAction, useApi } from '../../util';
import { ActionBar, Field, Group, Notice, Page } from '../../ui';
import './admin.css';

const ROI_LABEL = ['x0 (왼쪽)', 'y0 (위)', 'x1 (오른쪽)', 'y1 (아래)'];

/** A4 분석 기준: 관측 사진의 밝기·선명도 기준과 관심 영역(ROI) */
export default function AnalysisCriteria() {
  const api = useApi();
  const [c, setC] = useState<Criteria | null>(null);
  const act = useAction();
  const [saved, setSaved] = useState(false);

  useEffect(() => { act.run(async () => setC(await api.criteria())); }, []); // eslint-disable-line

  if (!c) return <Page title="분석 기준" width="narrow"><ErrorBox msg={act.error} /></Page>;
  const roi = c.roi;
  const edit = (patch: Partial<Criteria>) => { setSaved(false); setC({ ...c, ...patch }); };
  const setRoi = (i: number, v: string) => edit({ roi: roi.map((r, k) => (k === i ? Number(v) : r)) });

  return (
    <Page title="분석 기준" width="narrow">
      <Group header="밝기 (0~255)">
        <Field label="최소"><input type="number" value={c.minBrightness} onChange={(e) => edit({ minBrightness: Number(e.target.value) })} /></Field>
        <Field label="최대"><input type="number" value={c.maxBrightness} onChange={(e) => edit({ maxBrightness: Number(e.target.value) })} /></Field>
      </Group>

      <Group header="선명도">
        <Field label="최소" hint="라플라시안 분산"><input type="number" value={c.minSharpness} onChange={(e) => edit({ minSharpness: Number(e.target.value) })} /></Field>
      </Group>

      <Group header="관심 영역 (사진 크기 대비 비율 0~1)"
        footer={'관심 영역의 평균 밝기와 선명도가 기준을 벗어나면 그 사진은 "재촬영 후보"로 표시됩니다.'}>
        {roi.map((v, i) => (
          <Field key={i} label={ROI_LABEL[i]}>
            <input type="number" step="0.05" min="0" max="1" value={v} onChange={(e) => setRoi(i, e.target.value)} />
          </Field>
        ))}
        <div className="cell cell-pad">
          <div className="roi-box">
            <div className="roi" style={{
              left: `${roi[0] * 100}%`, top: `${roi[1] * 100}%`,
              width: `${(roi[2] - roi[0]) * 100}%`, height: `${(roi[3] - roi[1]) * 100}%`,
            }}>ROI</div>
          </div>
        </div>
      </Group>

      <ErrorBox msg={act.error} />
      {saved && <Notice tone="ok">저장했습니다. 이후 들어오는 관측부터 적용됩니다.</Notice>}
      <ActionBar>
        <button type="button" className="primary" disabled={act.busy}
          onClick={() => act.run(async () => { setC(await api.saveCriteria(c)); setSaved(true); })}>저장</button>
      </ActionBar>
    </Page>
  );
}
