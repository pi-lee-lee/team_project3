import { useEffect, useState } from 'react';
import type { Criteria } from '../../api/types';
import { ErrorBox, useAction, useApi } from '../../util';

/** A4 분석 기준 */
export default function AnalysisCriteria() {
  const api = useApi();
  const [c, setC] = useState<Criteria | null>(null);
  const act = useAction();
  const [saved, setSaved] = useState(false);

  useEffect(() => { act.run(async () => setC(await api.criteria())); }, []); // eslint-disable-line

  if (!c) return <section><h2>분석 기준</h2><ErrorBox msg={act.error} /></section>;
  const roi = c.roi;
  const setRoi = (i: number, v: string) => setC({ ...c, roi: roi.map((r, k) => (k === i ? Number(v) : r)) });

  return (
    <section>
      <h2>분석 기준</h2>
      <div className="row top">
        <div className="card grow">
          <label>밝기 최소 (0~255)<input type="number" value={c.minBrightness} onChange={(e) => setC({ ...c, minBrightness: Number(e.target.value) })} /></label>
          <label>밝기 최대 (0~255)<input type="number" value={c.maxBrightness} onChange={(e) => setC({ ...c, maxBrightness: Number(e.target.value) })} /></label>
          <label>선명도 최소 (라플라시안 분산)<input type="number" value={c.minSharpness} onChange={(e) => setC({ ...c, minSharpness: Number(e.target.value) })} /></label>
          <label>관심 영역 (비율 x0, y0, x1, y1)
            <div className="row">{roi.map((v, i) => <input key={i} type="number" step="0.05" value={v} onChange={(e) => setRoi(i, e.target.value)} size={4} />)}</div>
          </label>
          <ErrorBox msg={act.error} />
          {saved && <div className="ok">저장했습니다. 이후 들어오는 관측부터 적용됩니다.</div>}
          <button className="primary" disabled={act.busy}
            onClick={() => act.run(async () => { setC(await api.saveCriteria(c)); setSaved(true); })}>저장</button>
        </div>
        <div className="roi-preview">
          <div className="roi" style={{ left: `${roi[0] * 100}%`, top: `${roi[1] * 100}%`, width: `${(roi[2] - roi[0]) * 100}%`, height: `${(roi[3] - roi[1]) * 100}%` }}>ROI</div>
        </div>
      </div>
      <p className="muted">관심 영역의 평균 밝기와 선명도가 기준을 벗어나면 그 사진은 "재촬영 후보"로 표시됩니다.</p>
    </section>
  );
}
