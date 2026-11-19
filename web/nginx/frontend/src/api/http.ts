import type { Api } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && !url.endsWith('/login')) {
    window.dispatchEvent(new Event('auth:expired'));
  }
  if (!res.ok) {
    let msg = res.statusText || `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j.message || j.detail || msg;
    } catch {
      /* 본문 없음 */
    }
    if (res.status === 403) msg = '권한이 없습니다';
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** 파일을 함께 보내는 요청(multipart). 오류 처리는 call 과 같다. */
async function upload<T>(url: string, form: FormData): Promise<T> {
  const res = await fetch(url, { method: 'POST', credentials: 'same-origin', body: form });
  if (res.status === 401) window.dispatchEvent(new Event('auth:expired'));
  if (!res.ok) {
    let msg = res.statusText || `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = j.message || j.detail || msg;
    } catch {
      /* 본문 없음 */
    }
    if (res.status === 403) msg = '권한이 없습니다';
    throw new ApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

const get = <T,>(u: string) => call<T>('GET', u);
const post = <T,>(u: string, b?: unknown) => call<T>('POST', u, b ?? {});

const wsBase = () => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

/** 게이트웨이 REST API 구현. */
export const httpApi: Api = {
  login: (loginId, password) => post('/api/auth/login', { loginId, password }),
  logout: () => post('/api/auth/logout'),
  me: () => get('/api/auth/me'),

  dashboard: () => get('/api/dashboard/overview'),
  demo: () => get('/api/admin/demo'),
  runDemo: (key) => post(`/api/admin/demo/${key}/run`),
  stopDemo: () => post('/api/admin/demo/stop'),

  settings: () => get('/api/settings'),
  saveSetting: (key, value) => call('PUT', `/api/settings/${encodeURIComponent(key)}`, { value }),
  alerts: (state = 'OPEN,ACKED') => get(`/api/alerts?state=${state}`),
  ackAlert: (id, comment) => post(`/api/alerts/${id}/ack`, { comment }),
  resolveAlert: (id, comment) => post(`/api/alerts/${id}/resolve`, { comment }),
  pointRules: (pointId) => get(`/api/points/${pointId}/rules`),
  checkers: () => get('/api/admin/checkers'),
  saveRule: (pointId, r, ruleId) =>
    ruleId ? call('PUT', `/api/admin/rules/${ruleId}`, r) : post(`/api/admin/points/${pointId}/rules`, r),
  deleteRule: (ruleId) => call('DELETE', `/api/admin/rules/${ruleId}`),
  testRule: (image, r) => {
    const form = new FormData();
    form.append('image', image, 'test.jpg');
    form.append('rule', new Blob([JSON.stringify({ ruleId: 0, ...r })], { type: 'application/json' }));
    return upload('/api/admin/rules/test', form);
  },
  observationResults: (id) => get(`/api/observations/${id}/results`),
  incidents: (openOnly) => get(`/api/incidents?state=${openOnly ? 'open' : 'all'}`),
  incident: (id) => get(`/api/incidents/${id}`),
  incidentImageUrl: (id, kind, version) => `/api/incidents/${id}/image?kind=${kind}${version ? `&v=${encodeURIComponent(String(version))}` : ''}`,
  approveIncident: (id) => post(`/api/incidents/${id}/approve`),
  launchIncident: (id) => post(`/api/incidents/${id}/launch`),
  dismissIncident: (id, comment) => post(`/api/incidents/${id}/dismiss`, { comment }),
  resolveIncident: (id, comment) => post(`/api/incidents/${id}/resolve`, { comment }),

  roles: () => get('/api/admin/roles'),
  users: () => get('/api/admin/users'),
  createUser: (u) => post('/api/admin/users', u),
  updateUser: (id, patch) => call('PATCH', `/api/admin/users/${id}`, patch),
  resetPassword: (id, password) => post(`/api/admin/users/${id}/password`, { password }),
  revokeSessions: (id) => post(`/api/admin/users/${id}/revoke-sessions`),
  audit: (limit = 300) => get(`/api/admin/audit?limit=${limit}`),

  robots: () => get('/api/robots'),
  robotStatus: (id) => get(`/api/robots/${id}/status`),
  streamUrl: (id) => `/api/robots/${id}/stream`,
  teleopUrl: (id) => `${wsBase()}/ws/robots/${id}/teleop`,
  acquireControl: (id) => post(`/api/robots/${id}/control/acquire`),
  releaseControl: (id) => post(`/api/robots/${id}/control/release`),
  estop: (id) => post(`/api/robots/${id}/estop`),
  adminRobots: () => get('/api/admin/robots'),
  saveRobot: (r) =>
    r.robotId
      ? call('PUT', `/api/admin/robots/${r.robotId}`, r)
      : post('/api/admin/robots', r),
  revokeControl: (id) => post(`/api/admin/robots/${id}/revoke-control`),
  mapInfo: (id) => get(`/api/robots/${id}/map`),
  mapImageUrl: (id, version) => `/api/robots/${id}/map.png?v=${version}`,
  mapView: (id) => get(`/api/robots/${id}/mapview`),
  goTo: (id, x, y, yaw) => post(`/api/robots/${id}/goto`, { x, y, yaw }),
  zones: (id) => get(`/api/robots/${id}/zones`),
  addZone: (id, z) => post(`/api/robots/${id}/zones`, z),
  deleteZone: (id, zoneId) => call('DELETE', `/api/robots/${id}/zones/${zoneId}`),
  cancelGoTo: (id) => post(`/api/robots/${id}/goto/cancel`),

  points: () => get('/api/points'),
  adminPoints: () => get('/api/admin/points'),
  savePoint: (p) =>
    p.point_id ? call('PUT', `/api/admin/points/${p.point_id}`, p) : post('/api/admin/points', p),
  pointHistory: (id) => get(`/api/points/${id}/history`),

  tasks: (group) => get(`/api/inspections${group ? `?group=${group}` : ''}`),
  createTask: (robotId, pointIds, note) => post('/api/inspections', { robotId, pointIds, note }),
  task: (id) => get(`/api/inspections/${id}`),
  cancelTask: (id) => post(`/api/inspections/${id}/cancel`),
  imageUrl: (id) => `/api/observations/${id}/image`,
  review: (id, result, comment) => post(`/api/observations/${id}/reviews`, { result, comment }),
  recheck: (id) => post(`/api/observations/${id}/recheck`),

  schedules: () => get('/api/inspections/schedules'),
  schedule: (id) => get(`/api/inspections/schedules/${id}`),
  saveSchedule: (s, id) =>
    id ? call('PUT', `/api/inspections/schedules/${id}`, s) : post('/api/inspections/schedules', s),
  setScheduleEnabled: (id, enabled) => post(`/api/inspections/schedules/${id}/enabled`, { enabled }),
  runSchedule: (id) => post(`/api/inspections/schedules/${id}/run`),
  deleteSchedule: (id) => call('DELETE', `/api/inspections/schedules/${id}`),
  pendingRuns: () => get('/api/inspections/schedules/pending'),
  scheduleBacklog: () => get('/api/inspections/schedules/backlog'),
  cancelPendingRun: (key) => call('DELETE', `/api/inspections/schedules/pending/${key}`),

  criteria: () => get('/api/admin/analysis/criteria'),
  saveCriteria: (c) => call('PUT', '/api/admin/analysis/criteria', c),
  system: () => get('/api/admin/system'),
  serverTime: () => get('/api/time'),
};
