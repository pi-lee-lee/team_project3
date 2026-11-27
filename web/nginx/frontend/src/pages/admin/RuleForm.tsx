import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { CheckResponse, CheckerInfo, RuleInput, SchemaProp } from '../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Field, Group, Notice, Page, Picker, Row, Switch } from '../../ui';
import { CHECKER_LABEL, GradeTag, PhotoOverlay, valueText } from '../user/scenarioText';
import './admin.css';

/** 등급 기준 예시: 종류를 고르면 값의 모양(이름/숫자)에 맞는 것을 채워 준다. 실제 기준은 대상에 맞게 고친다.
 *  규칙 판독은 경고까지다(비상은 화재 사건만 — 기준에 비상을 넣어도 서버가 경고로 낮춘다) */
function gradingExample(c: CheckerInfo): Record<string, unknown> {
  if (c.valueType === 'number') {
    return c.kind === 'THERMAL'
      ? { type: 'ranges', ranges: [{ max: 0.002, grade: 'NORMAL' }], default: 'WARNING' }
      : { type: 'ranges', ranges: [{ min: 0.0, max: 0.6, grade: 'NORMAL' }], default: 'WARNING' };
  }
  if (c.kind === 'OBJECT') return { type: 'map', map: { IN_REGION: 'NORMAL', OUT_OF_REGION: 'WARNING', MISSING: 'WARNING' }, default: 'UNKNOWN' };
  if (c.kind === 'LAMP') return { type: 'map', map: { green: 'NORMAL', yellow: 'WARNING', red: 'WARNING', off: 'WARNING' }, default: 'UNKNOWN' };
  return { type: 'map', map: Object.fromEntries(c.labels.map((l) => [l, 'NORMAL'])), default: 'UNKNOWN' };
}

const isJsonProp = (p: SchemaProp) => p.type === 'object' || p.type === 'array';
const pretty = (v: unknown) => JSON.stringify(v ?? {}, null, 2);
const numOrNull = (s: string) => (s.trim() === '' || isNaN(Number(s)) ? null : Number(s));

/**
 * A3-3 규칙 추가 · 수정.
 * 입력 칸은 판독기가 알려 주는 설정 모양(paramsSchema)으로 그린다 — 판독기 종류가 늘어도 이 화면은 고치지 않는다.
 * 아래 "규칙 시험"으로 저장 전에 사진 한 장에 대어 볼 수 있다.
 */
export default function RuleForm() {
  const { id, ruleId: rid } = useParams<{ id: string; ruleId: string }>();
  const pointId = Number(id);
  const ruleId = rid ? Number(rid) : undefined;
  const api = useApi();
  const nav = useNavigate();
  const checkers = usePoll(() => api.checkers(), 0);
  const rules = usePoll(() => api.pointRules(pointId), 0, [pointId]);
  const act = useAction();
  const del = useAction();

  const [name, setName] = useState('');
  const [kind, setKind] = useState('');
  const [enabled, setEnabled] = useState(true);
  /** 판독기 설정: 값 그대로(숫자·글자·참거짓). 객체형 속성은 글자(JSON)로 들고 있다가 저장할 때 읽는다 */
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [paramText, setParamText] = useState<Record<string, string>>({});
  const [region, setRegion] = useState(['', '', '', '']);
  const [grading, setGrading] = useState('');
  const [target, setTarget] = useState({ x: '', y: '', yaw: '', sizeM: '', useAsReference: false });
  const [otherRegions, setOtherRegions] = useState<Record<string, number[]>>({});
  const [loaded, setLoaded] = useState(!ruleId);

  const checker = checkers.data?.find((c) => c.kind === kind);
  const props = useMemo(() => Object.entries(checker?.paramsSchema?.properties ?? {}), [checker]);

  /** 판독기 종류를 바꾸면 그 종류의 기본값과 등급 예시로 채운다 */
  const chooseKind = (k: string) => {
    const c = checkers.data?.find((x) => x.kind === k);
    setKind(k);
    if (!c) return;
    const p: Record<string, unknown> = {}, t: Record<string, string> = {};
    Object.entries(c.paramsSchema?.properties ?? {}).forEach(([key, sp]) => {
      if (isJsonProp(sp)) t[key] = pretty(sp.default); else p[key] = sp.default ?? (sp.type === 'boolean' ? false : '');
    });
    setParams(p); setParamText(t); setGrading(pretty(gradingExample(c)));
  };

  // 수정: 저장된 규칙을 폼에 싣는다(판독기 목록이 와야 객체형 속성을 가를 수 있다)
  useEffect(() => {
    if (loaded || !ruleId || !rules.data || !checkers.data) return;
    const r = rules.data.find((x) => x.ruleId === ruleId);
    if (!r) return;
    const c = checkers.data.find((x) => x.kind === r.kind);
    const p: Record<string, unknown> = {}, t: Record<string, string> = {};
    const schema = c?.paramsSchema?.properties ?? {};
    Object.entries(schema).forEach(([key, sp]) => {
      const v = r.params?.[key] ?? sp.default;
      if (isJsonProp(sp)) t[key] = pretty(v); else p[key] = v ?? '';
    });
    // 판독기가 모르는 속성도 잃지 않게 그대로 둔다
    Object.entries(r.params ?? {}).forEach(([key, v]) => { if (!(key in schema)) p[key] = v; });
    setName(r.name); setKind(r.kind); setEnabled(r.enabled); setParams(p); setParamText(t);
    const ins = r.regions?.INSPECTOR;
    setRegion(Array.isArray(ins) && ins.length === 4 ? ins.map(String) : ['', '', '', '']);
    const rest = { ...(r.regions ?? {}) };
    delete rest.INSPECTOR;
    setOtherRegions(rest);
    setGrading(pretty(r.grading));
    setTarget({
      x: r.target?.x == null ? '' : String(r.target.x), y: r.target?.y == null ? '' : String(r.target.y),
      yaw: r.target?.yaw == null ? '' : String(r.target.yaw), sizeM: r.target?.sizeM == null ? '' : String(r.target.sizeM),
      useAsReference: !!r.target?.useAsReference,
    });
    setLoaded(true);
  }, [loaded, ruleId, rules.data, checkers.data]);

  /** 폼 → 서버에 보낼 규칙. 잘못 적힌 곳이 있으면 그 이유를 던진다 */
  const build = (): RuleInput => {
    const p: Record<string, unknown> = { ...params };
    props.forEach(([key, sp]) => {
      if (isJsonProp(sp)) {
        try { p[key] = JSON.parse(paramText[key] || 'null'); } catch { throw new Error(`"${sp.title ?? key}" 칸이 올바른 JSON 이 아닙니다`); }
      } else if ((sp.type === 'number' || sp.type === 'integer') && typeof p[key] === 'string') {
        p[key] = (p[key] as string).trim() === '' ? undefined : Number(p[key]);
      }
    });
    let g: Record<string, unknown>;
    try { g = JSON.parse(grading); } catch { throw new Error('등급 기준이 올바른 JSON 이 아닙니다'); }
    const regions: Record<string, number[]> = { ...otherRegions };
    if (region.some((v) => v.trim() !== '')) {
      const nums = region.map(Number);
      if (region.some((v) => v.trim() === '') || nums.some((n) => isNaN(n) || n < 0 || n > 1) || nums[0] >= nums[2] || nums[1] >= nums[3]) {
        throw new Error('기대 영역은 0~1 사이 네 숫자이고, 왼쪽 위(x0, y0)가 오른쪽 아래(x1, y1)보다 작아야 합니다');
      }
      regions.INSPECTOR = nums;
    }
    return {
      name: name.trim(), kind, enabled, params: p, regions, grading: g,
      target: { x: numOrNull(target.x), y: numOrNull(target.y), yaw: numOrNull(target.yaw), sizeM: numOrNull(target.sizeM), useAsReference: target.useAsReference },
    };
  };

  const back = { to: `/admin/points/${pointId}/rules`, label: '점검 규칙' };
  const save = () => act.run(async () => { await api.saveRule(pointId, build(), ruleId); nav(back.to); });
  const remove = () => {
    if (!ruleId || del.busy || !window.confirm('이 규칙을 지울까요? 지난 판독 결과는 남습니다.')) return;
    del.run(async () => { await api.deleteRule(ruleId); nav(back.to); });
  };

  if (ruleId && !loaded) {
    return (
      <Page title="규칙 수정" back={back} width="narrow">
        <ErrorBox msg={rules.error || checkers.error} />
        {rules.data && !rules.data.find((x) => x.ruleId === ruleId) && <Notice tone="warn">규칙을 찾을 수 없습니다.</Notice>}
      </Page>
    );
  }

  return (
    <Page title={ruleId ? '규칙 수정' : '규칙 추가'} back={back} width="narrow">
      <div className="has-action-bar">
        <ErrorBox msg={act.error || del.error || checkers.error} />
        <Group>
          <Field label="이름"><input value={name} placeholder="예: 소화기 비치" onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="판독기 종류">
            <Picker variant="field" label="판독기 종류" value={kind || null} onChange={chooseKind} placeholder="고르기"
              options={(checkers.data ?? []).map((c) => ({ value: c.kind, label: CHECKER_LABEL[c.kind] ?? c.kind, sub: c.kind }))} />
          </Field>
          <Field label="사용"><Switch checked={enabled} onChange={setEnabled} label="사용" /></Field>
        </Group>

        {checker && (
          <Group header="판독기 설정" footer="값의 뜻은 판독기가 정합니다. 대상(색 · 눈금)이 바뀌면 여기만 고칩니다.">
            {props.length === 0 && <Row title={<span className="muted">설정할 것이 없습니다</span>} />}
            {props.map(([key, sp]) => (
              <Field key={key} label={sp.title ?? key} stack={isJsonProp(sp)} hint={sp.description}>
                {isJsonProp(sp) ? (
                  <textarea rows={Math.min(8, (paramText[key] ?? '').split('\n').length + 1)} className="mono" spellCheck={false}
                    value={paramText[key] ?? ''} onChange={(e) => setParamText({ ...paramText, [key]: e.target.value })} />
                ) : sp.type === 'boolean' ? (
                  <Switch checked={!!params[key]} onChange={(v) => setParams({ ...params, [key]: v })} label={sp.title ?? key} />
                ) : sp.enum ? (
                  <Picker variant="field" label={sp.title ?? key} value={String(params[key] ?? '')}
                    onChange={(v) => setParams({ ...params, [key]: v })}
                    options={sp.enum.map((v) => ({ value: String(v), label: String(v) }))} />
                ) : (
                  <input type={sp.type === 'number' || sp.type === 'integer' ? 'number' : 'text'} step="any"
                    value={String(params[key] ?? '')} onChange={(e) => setParams({ ...params, [key]: e.target.value })} />
                )}
              </Field>
            ))}
          </Group>
        )}

        <Group header="기대 영역 (터틀봇 사진 기준)"
          footer="사진의 왼쪽 위가 (0, 0), 오른쪽 아래가 (1, 1) 입니다. 네 칸을 모두 비우면 사진 전체에서 찾습니다. 아래 규칙 시험의 사진에 파란 점선으로 보입니다.">
          <div className="cell region-grid">
            {(['x0 (왼쪽)', 'y0 (위)', 'x1 (오른쪽)', 'y1 (아래)'] as const).map((label, i) => (
              <label key={label}>{label}
                <input type="number" step="0.01" min={0} max={1} value={region[i]}
                  onChange={(e) => setRegion(region.map((v, k) => (k === i ? e.target.value : v)))} />
              </label>
            ))}
          </div>
        </Group>

        <Group header="등급 기준"
          footer={checker?.valueType === 'number'
            ? '숫자 값: ranges 를 위에서부터 보고 처음 맞는 구간(min 이상 max 미만)의 등급을 씁니다. 어디에도 안 맞으면 default.'
            : `이름 값: map 에서 읽은 값에 해당하는 등급을 씁니다. 없으면 default.${checker?.labels.length ? ` 나올 수 있는 값: ${checker.labels.join(', ')}` : ''}`}>
          <Field label="등급(grading)" stack hint="등급: NORMAL(정상) · WARNING(경고) · UNKNOWN(판독 불가). 규칙 판독은 경고까지이며 EMERGENCY 를 넣어도 경고로 낮춘다(비상은 화재만)">
            <textarea rows={9} className="mono" spellCheck={false} value={grading} onChange={(e) => setGrading(e.target.value)} />
          </Field>
        </Group>

        <Group header="대상의 지도 좌표 (선택)" footer="대상이 지도에서 어디에 있는지 적어 두면 경고가 지도 위에 찍힙니다. 위치 기준은 벽에 고정된 대상(계기판 · 표시등)에만 켭니다 — 옮겨질 수 있는 물체에는 켜지 마세요.">
          <Field label="x (m)"><input type="number" step="0.01" value={target.x} onChange={(e) => setTarget({ ...target, x: e.target.value })} /></Field>
          <Field label="y (m)"><input type="number" step="0.01" value={target.y} onChange={(e) => setTarget({ ...target, y: e.target.value })} /></Field>
          <Field label="방향 (rad)"><input type="number" step="0.01" value={target.yaw} onChange={(e) => setTarget({ ...target, yaw: e.target.value })} /></Field>
          <Field label="실제 크기 (m)"><input type="number" step="0.01" value={target.sizeM} onChange={(e) => setTarget({ ...target, sizeM: e.target.value })} /></Field>
          <Field label="위치 기준으로 사용"><Switch checked={target.useAsReference} onChange={(v) => setTarget({ ...target, useAsReference: v })} label="위치 기준으로 사용" /></Field>
        </Group>

        {kind && <RuleTest pointId={pointId} build={build} />}

        {ruleId && <Group><Row destructive title={del.busy ? '지우는 중…' : '규칙 지우기'} onClick={remove} /></Group>}
        <ActionBar>
          <button className="primary" disabled={act.busy || !name.trim() || !kind} onClick={save}>{act.busy ? '저장 중…' : '저장'}</button>
        </ActionBar>
      </div>
    </Page>
  );
}

/** 규칙 시험: 사진 한 장을 지금 폼 값으로 판독해 본다(저장하지 않는다). */
function RuleTest({ pointId, build }: { pointId: number; build: () => RuleInput }) {
  const api = useApi();
  const act = useAction();
  const [photo, setPhoto] = useState<{ blob: Blob; url: string; from: string } | null>(null);
  const [result, setResult] = useState<{ res: CheckResponse; region?: number[] } | null>(null);

  // 사진 주소는 쓰고 나면 풀어 준다
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);

  const use = (blob: Blob, from: string) => { setPhoto({ blob, url: URL.createObjectURL(blob), from }); setResult(null); };
  const recent = () => act.run(async () => {
    const h = await api.pointHistory(pointId);
    const o = h.observations.find((x) => x.status === 'CAPTURED' && x.has_image);
    if (!o) throw new Error('이 지점에서 찍은 사진이 아직 없습니다. 점검을 한 번 실행하거나 사진 파일을 고르세요.');
    const res = await fetch(api.imageUrl(o.observation_id), { credentials: 'same-origin' });
    if (!res.ok) throw new Error('사진을 불러오지 못했습니다');
    use(await res.blob(), `관측 #${o.observation_id}`);
  });
  const run = () => act.run(async () => {
    const rule = build();
    setResult({ res: await api.testRule(photo!.blob, rule), region: rule.regions.INSPECTOR });
  });

  const r = result?.res.results[0];
  const draft = (() => { try { return build().regions.INSPECTOR; } catch { return undefined; } })();
  return (
    <Group header="규칙 시험" footer="저장하지 않고, 지금 폼에 적힌 값으로 사진 한 장을 판독해 봅니다.">
      <div className="cell rule-test-tools">
        <label className="file-btn">사진 파일 고르기
          <input type="file" accept="image/jpeg,image/png" onChange={(e) => { const f = e.target.files?.[0]; if (f) use(f, f.name); e.target.value = ''; }} />
        </label>
        <button type="button" disabled={act.busy} onClick={recent}>이 지점의 최근 사진 쓰기</button>
        <span className="grow" />
        <button type="button" className="primary" disabled={!photo || act.busy} onClick={run}>{act.busy ? '판독 중…' : '시험'}</button>
      </div>
      {act.error && <div className="cell"><span className="bad">{act.error}</span></div>}
      {photo && (
        <div className="cell rule-test-photo">
          <PhotoOverlay src={photo.url} alt="시험 사진" boxes={[
            { box: result ? result.region : draft, kind: 'expected' },
            { box: r?.located?.bbox, kind: 'found' },
          ]} />
          <div className="ov-legend"><span><i />찾은 자리</span><span><i className="expected" />기대 영역</span><span className="muted">{photo.from}</span></div>
        </div>
      )}
      {result && r && <>
        <Row title="등급" right={<GradeTag grade={r.grade} />} />
        <Row title="읽은 값" detail={valueText(r.value, r.unit)} />
        {r.confidence != null && <Row title="확신도" detail={r.confidence.toFixed(2)} />}
        {r.reason && <Row title="사유" detail={r.reason} />}
        <Row title="사진 품질" detail={result.res.quality.verdict === 'OK' ? '양호' : `재촬영 후보 · ${result.res.quality.reasons}`} />
      </>}
      {result && !r && <Row title={<span className="muted">판독 결과가 없습니다</span>} />}
    </Group>
  );
}
