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

const get = <T,>(u: string) => call<T>('GET', u);
const post = <T,>(u: string, b?: unknown) => call<T>('POST', u, b ?? {});

const wsBase = () => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

/** 게이트웨이 REST API 구현. */
export const httpApi: Api = {
  login: (loginId, password) => post('/api/auth/login', { loginId, password }),
  logout: () => post('/api/auth/logout'),
  me: () => get('/api/auth/me'),

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

  criteria: () => get('/api/admin/analysis/criteria'),
  saveCriteria: (c) => call('PUT', '/api/admin/analysis/criteria', c),
  system: () => get('/api/admin/system'),
};
