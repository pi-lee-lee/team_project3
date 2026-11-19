// 화면이 기대하는 데이터 모양과 API 인터페이스.
// 화면은 이 인터페이스에만 의존하고, 실제 구현(http.ts)은 게이트웨이 REST API 를 호출한다.
// 로봇이 시뮬레이션이든 실제든 화면 코드는 바뀌지 않는다(차이는 robot-service 의 어댑터가 흡수).

export type Role = 'ADMIN' | 'SUPERVISOR' | 'MANAGER' | 'USER' | 'DASHBOARD';

export interface Me {
  userId: number;
  loginId: string;
  name: string;
  roleId: number;
  role: Role;
  roleName: string;
  status: string;
}

export interface UserRow extends Me {
  createdAt?: string;
  lastLoginAt?: string | null;
}

export interface RoleInfo {
  roleId: number;
  code: Role;
  name: string;
}

export interface AuditRow {
  audit_id: number;
  occurred_at: string | number;
  login_id: string | null;
  role_code: string | null;
  action: string;
  target: string;
  status: number | null;
}

export interface Pose { x: number; y: number; yaw: number }

export interface ControlLease { kind: 'USER' | 'MISSION'; userId: number; login: string; since: string }

export interface RobotSummary {
  robotId: number;
  code: string;
  name: string;
  adapterType: 'ROSBRIDGE' | 'MOCK';
  enabled: boolean;
  connected: boolean;
  control: ControlLease | null;
  mission: { missionId: number; currentPointId: number | null; cancelRequested: boolean } | null;
  config?: Record<string, unknown>;
}

export interface RobotStatus extends RobotSummary {
  pose?: Pose | null;
  batteryPercent?: number | null;
  frontObstacleM?: number | null;
  ageMs?: Record<string, number | null>;
  capabilities?: Record<string, string>;
  /** 지도 위 위치(지도 좌표). pose 는 주행계(odom) 기준이다 */
  mapPose?: Pose | null;
  /** 투척 기구 상태. 기구가 없거나 응답이 없으면 null. remaining -1 = 모름 */
  launcher?: { ready: boolean; remaining: number; fault: string } | null;
}

export interface Point {
  point_id: number;
  code: string;
  name: string;
  description: string | null;
  x: number;
  y: number;
  yaw_deg: number;
  active: boolean;
}

export type TaskStatus =
  | 'REQUESTED' | 'DISPATCHED' | 'RUNNING' | 'CANCEL_REQUESTED'
  | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'INTERRUPTED';

export interface TaskRow {
  task_id: number;
  robot_id: number;
  robot_code: string;
  requester_login: string;
  note: string | null;
  recheck_of: number | null;
  schedule_id?: number | null;
  /** INSPECTION(점검) / RESPONSE(화재 출동) */
  kind?: 'INSPECTION' | 'RESPONSE';
  incident_id?: number | null;
  status: TaskStatus;
  status_reason: string | null;
  created_at: string | number;
  points: string;
  observations: number;
}

export interface TaskEvent {
  event_id: number;
  source: 'USER' | 'ROBOT' | 'SYSTEM';
  type: string;
  detail: Record<string, unknown>;
  actor: string | null;
  occurred_at: string | number;
}

export interface Review {
  review_id: number;
  result: 'NORMAL' | 'ABNORMAL' | 'UNABLE';
  comment: string | null;
  reviewer_login: string;
  reviewed_at: string | number;
}

export interface Observation {
  observation_id: number;
  task_id: number;
  point_id: number;
  point_code: string;
  point_name: string;
  seq: number;
  status: 'CAPTURED' | 'UNABLE';
  reason: string | null;
  reason_code: string | null;
  has_image: boolean;
  captured_at: string | number;
  recheck_of: number | null;
  requester_login: string;
  brightness: number | null;
  sharpness: number | null;
  verdict: 'OK' | 'RETAKE' | null;
  analysis_reasons: string | null;
  review_result: Review['result'] | null;
  review_comment: string | null;
  reviewer_login: string | null;
  reviews?: Review[];
}

export interface TaskDetail extends Omit<TaskRow, 'points' | 'observations'> {
  points: { seq: number; point_id: number; code: string; name: string }[];
  events: TaskEvent[];
  observations: Observation[];
}

export interface MapInfo { width: number; height: number; resolution: number; originX: number; originY: number; version: number }

export interface ManualGoal { goalId: string; x: number; y: number; yaw: number; state: string; reason: string; code?: string }

export interface MapView {
  pose: Pose | null;
  scan: [number, number][];
  path: [number, number][];
  /** 제어기가 지금 내는 속도 명령과 그 명령으로 갈 예상 호(지도 좌표). 주행 중이 아니면 null */
  control?: { v: number; w: number; traj: [number, number][] } | null;
  manualGoal: ManualGoal | null;
  mission: { missionId: number; currentPointId: number | null } | null;
}

/** 금지구역: 관리자가 지도에 그린 직사각형(지도 좌표, m). 로봇은 이 안으로 가지 않는다 */
export interface KeepoutZone {
  zoneId: number;
  name: string;
  xMin: number; yMin: number; xMax: number; yMax: number;
  createdBy: string;
  createdAt: string;
}

export type ScheduleKind = 'MANUAL' | 'ONCE' | 'INTERVAL' | 'DAILY' | 'WEEKLY';
export type ScheduleOutcome = 'CREATED' | 'SKIPPED_BUSY' | 'SKIPPED_OFFLINE' | 'MISSED' | 'FAILED' | 'CANCELLED';

/** 실행 버퍼에서 기다리는(지연된) 예약 회차 */
export interface PendingRun {
  key: number;
  scheduleId: number;
  name: string;
  points: string | null;
  robotId: number;
  plannedAt: string;
  queuedAt: string;
  delaySec: number;
  waitReason: string | null;
  manualBy: string | null;
}

/** 예약 점검. 시각 문자열은 서버의 예약 기준 시간대(기본 Asia/Seoul)로 해석한다. */
export interface Schedule {
  schedule_id: number;
  name: string;
  robot_id: number;
  point_ids: number[];
  points: string | null;
  note: string | null;
  kind: ScheduleKind;
  run_at: string | number | null;
  run_at_local: string | null;     // 'YYYY-MM-DDTHH:mm'
  interval_minutes: number | null;
  time_of_day: string | null;      // 'HH:mm'
  days_of_week: number[] | null;   // 1=월 … 7=일
  window_start: string | null;
  window_end: string | null;
  enabled: boolean;
  next_run_at: string | number | null;
  created_by: number;
  creator_login: string;
  last_outcome: ScheduleOutcome | null;
  last_ran_at: string | number | null;
  last_task_id: number | null;
  last_reason: string | null;
  last_delay_sec: number | null;
  runs?: ScheduleRun[];
}

/** 로봇별 밀린 예약: 지금 하는 작업 + 실행 버퍼에 쌓인 회차(실행 순서) */
export interface Backlog {
  total: number;
  robots: {
    robotId: number;
    robotCode: string | null;
    waitReason: string | null;
    count: number;
    maxDelaySec: number;
    current: {
      taskId: number;
      status?: TaskStatus;
      requester?: string;
      note?: string | null;
      scheduleId?: number | null;
      createdAt?: string | null;
      points?: string;
      currentPoint?: string | null;
      progress?: string | null;
      elapsedSec?: number | null;
    } | null;
    queue: (PendingRun & { order: number })[];
  }[];
}

export interface ScheduleRun {
  run_id: number;
  planned_at: string | number;
  ran_at: string | number;
  outcome: ScheduleOutcome;
  task_id: number | null;
  task_status: TaskStatus | null;
  reason: string | null;
  delay_sec: number | null;
}

export interface ScheduleInput {
  name: string;
  robotId: number;
  pointIds: number[];
  note: string;
  kind: ScheduleKind;
  runAt?: string | null;
  intervalMinutes?: number | null;
  timeOfDay?: string | null;
  daysOfWeek?: number[];
  windowStart?: string | null;
  windowEnd?: string | null;
  enabled: boolean;
}

export interface Criteria { minBrightness: number; maxBrightness: number; minSharpness: number; roi: number[] }

export interface SystemStatus {
  services: { name: string; status: string }[];
  robots: { code: string; enabled: boolean; connected: boolean; ageMs: Record<string, number | null>; outboxPending: number }[];
}

// ------------------------------------------------------------------ 시나리오: 규칙 · 경고 · 사건 · 설정 (docs/design/INTERFACES.md)
export type Grade = 'NORMAL' | 'WARNING' | 'EMERGENCY' | 'UNKNOWN';
export type LaunchMode = 'APPROVAL' | 'AUTO';

/** 판독기 종류(analysis-service GET /checkers). paramsSchema 로 규칙 입력 폼을 그린다 */
export interface SchemaProp {
  type?: string; title?: string; description?: string; default?: unknown; enum?: unknown[];
  minimum?: number; maximum?: number;
}
export interface CheckerInfo {
  kind: string; version: string; valueType: 'number' | 'label';
  paramsSchema: { properties?: Record<string, SchemaProp> }; labels: string[];
}

export interface RuleTarget { x: number | null; y: number | null; yaw: number | null; sizeM: number | null; useAsReference: boolean }
export interface RuleInput {
  ruleId?: number;
  name: string; kind: string; enabled: boolean;
  params: Record<string, unknown>;
  /** 로봇 종류별 기대 영역 [x0, y0, x1, y1] (사진 크기 대비 비율) */
  regions: Record<string, number[]>;
  grading: Record<string, unknown>;
  target: RuleTarget;
}
export interface Rule extends RuleInput {
  ruleId: number; pointId: number; pointCode?: string; pointName?: string; updatedAt?: string | number;
  latest?: RuleResult | null;
}
export interface RuleResult {
  resultId?: number; observationId?: number; ruleId: number; kind?: string;
  grade: Grade; value: number | string | null; unit: string | null; confidence: number | null;
  located: { bbox?: number[]; relative?: { bearing: number; distance: number } } | null;
  evidence: Record<string, unknown> | null; reason: string | null;
  checkerVersion?: string | null; analyzedAt?: string | number;
  /** 판독 당시의 규칙 */
  rule?: Rule | null;
}
export interface CheckResponse {
  quality: { brightness: number; sharpness: number; verdict: 'OK' | 'RETAKE'; reasons: string };
  results: RuleResult[];
}

export interface AlertRow {
  alert_id: number; type: string; grade: 'WARNING' | 'EMERGENCY'; state: 'OPEN' | 'ACKED' | 'RESOLVED';
  title: string; detail: string | null;
  point_id: number | null; point_code: string | null; point_name: string | null; x: number | null; y: number | null;
  ref_kind: string; ref_id: number; task_id: number | null; evidence: Record<string, unknown> | null;
  opened_at: string | number; updated_at: string | number;
  acked_by: string | null; acked_at: string | number | null;
  resolved_by: string | null; resolved_at: string | number | null; comment: string | null;
}

export type IncidentState =
  | 'DETECTED' | 'DISPATCHED' | 'ARRIVED' | 'AWAITING_APPROVAL' | 'LAUNCHING' | 'LAUNCHED' | 'MONITORING'
  | 'RESOLVED' | 'DISMISSED' | 'FAILED';
/** 도착 후 · 투척 후 로봇 카메라로 다시 본 결과 */
export interface IncidentCheck {
  grade?: Grade; value?: number; reason?: string; bearingDeg?: number; aimed?: boolean; attempt?: number; at?: string; bbox?: number[];
}
export interface IncidentEvent {
  event_id: number; source: 'USER' | 'ROBOT' | 'SYSTEM'; type: string; detail: Record<string, unknown>;
  actor: string | null; occurred_at: string | number;
}
export interface Incident {
  incidentId: number; type: string; state: IncidentState; grade: Grade;
  x: number; y: number; poseQuality: number | null; detectedBy: number;
  launchMode: LaunchMode; responderId: number | null; taskId: number | null;
  standoff: { x: number; y: number; yaw: number }[] | null;
  recheck: IncidentCheck | null; afterCheck: IncidentCheck | null;
  images: { detection: boolean; recheck: boolean; after: boolean };
  approvedBy: string | null; approvedAt: string | number | null;
  closedBy: string | null; closedAt: string | number | null; closeReason: string | null;
  createdAt: string | number; updatedAt: string | number;
  events?: IncidentEvent[];
}
export type IncidentImageKind = 'detection' | 'recheck' | 'after';
export type Settings = Record<string, unknown>;

/** 관제 대시보드 요약(inspection-service DashboardController) */
export interface DashPoint {
  point_id: number; code: string; name: string; x: number; y: number; yaw_deg: number;
  observation_id: number | null; task_id: number | null; status: 'CAPTURED' | 'UNABLE' | null;
  reason_code: string | null; captured_at: string | number | null; has_image: boolean | null;
  verdict: 'OK' | 'RETAKE' | null; review_result: Review['result'] | null;
  /** 규칙 등급: 3 비상 · 2 경고 · 1 판독 불가 · 0 정상 · null 규칙/결과 없음 */
  grade_rank?: number | null;
}
/** 주의할 일 한 줄. ref_kind 가 어떤 상세 창을 열지 정한다. */
export interface DashAlert {
  type: string; severity: 'CRITICAL' | 'WARNING';
  at: string | number | null; ref_kind: string; ref_id: number | null; task_id: number | null;
  detail: string | null; point_code: string | null; point_name: string | null;
  /** 경고 표에서 온 것만: 제목 · 번호 · 상태 · 위치 */
  title?: string | null; alert_id?: number | null; state?: 'OPEN' | 'ACKED' | null; x?: number | null; y?: number | null;
}
export interface DashEvent extends TaskEvent { task_id: number; robot_code: string | null; task_status: TaskStatus }
export interface DashOverview {
  hours: number;
  today: {
    tasks: { total: number; active: number; completed: number; failed: number; cancelled: number };
    observations: { total: number; unable: number; normal: number; abnormal: number; unreviewed: number; retake: number };
  };
  points: DashPoint[];
  alerts: DashAlert[];
  events: DashEvent[];
  /** 열린 사건(화재 대응) */
  incidents?: Incident[];
  launchMode?: LaunchMode;
}

/** 시연 시나리오 실행(관리자 "시연" 화면) */
export interface DemoStatus {
  scenarios: { key: string; name: string; description: string; group: string }[];
  run: {
    key: string; name: string; by: string; state: 'RUNNING' | 'DONE' | 'FAILED' | 'STOPPED';
    startedAt: string; endedAt: string | null;
    log: { at: string; level: 'step' | 'wait' | 'info' | 'ok' | 'warn' | 'error'; text: string }[];
  } | null;
}

export interface Api {
  // 시연(시뮬레이션 전용)
  demo(): Promise<DemoStatus>;
  runDemo(key: string): Promise<DemoStatus>;
  stopDemo(): Promise<DemoStatus>;
  // 관제 대시보드
  dashboard(): Promise<DashOverview>;
  // 설정
  settings(): Promise<Settings>;
  saveSetting(key: string, value: unknown): Promise<Settings>;
  // 경고
  alerts(state?: string): Promise<AlertRow[]>;
  ackAlert(id: number, comment?: string): Promise<AlertRow>;
  resolveAlert(id: number, comment?: string): Promise<AlertRow>;
  // 점검 규칙
  pointRules(pointId: number): Promise<Rule[]>;
  checkers(): Promise<CheckerInfo[]>;
  saveRule(pointId: number, r: RuleInput, ruleId?: number): Promise<Rule>;
  deleteRule(ruleId: number): Promise<void>;
  testRule(image: Blob, r: RuleInput): Promise<CheckResponse>;
  observationResults(observationId: number): Promise<RuleResult[]>;
  // 사건(화재 대응)
  incidents(openOnly?: boolean): Promise<Incident[]>;
  incident(id: number): Promise<Incident>;
  incidentImageUrl(id: number, kind: IncidentImageKind, version?: string | number): string;
  approveIncident(id: number): Promise<Incident>;
  launchIncident(id: number): Promise<Incident>;
  dismissIncident(id: number, comment?: string): Promise<Incident>;
  resolveIncident(id: number, comment?: string): Promise<Incident>;
  // 인증
  login(loginId: string, password: string): Promise<Me>;
  logout(): Promise<void>;
  me(): Promise<Me>;
  // A1 사용자
  roles(): Promise<RoleInfo[]>;
  users(): Promise<UserRow[]>;
  createUser(u: { loginId: string; password: string; name: string; roleId: number }): Promise<UserRow>;
  updateUser(id: number, patch: { name?: string; roleId?: number; status?: string }): Promise<UserRow>;
  resetPassword(id: number, password: string): Promise<void>;
  revokeSessions(id: number): Promise<void>;
  audit(limit?: number): Promise<AuditRow[]>;
  // 로봇
  robots(): Promise<RobotSummary[]>;
  robotStatus(id: number): Promise<RobotStatus>;
  streamUrl(id: number): string;
  teleopUrl(id: number): string;
  acquireControl(id: number): Promise<ControlLease>;
  releaseControl(id: number): Promise<void>;
  estop(id: number): Promise<void>;
  adminRobots(): Promise<RobotSummary[]>;
  saveRobot(r: { robotId?: number; code?: string; name: string; adapterType: string; config: unknown; enabled: boolean }): Promise<RobotSummary>;
  revokeControl(id: number): Promise<void>;
  // 관제 지도 모드
  mapInfo(id: number): Promise<MapInfo>;
  mapImageUrl(id: number, version: number): string;
  mapView(id: number): Promise<MapView>;
  goTo(id: number, x: number, y: number, yaw: number): Promise<ManualGoal>;
  zones(id: number): Promise<KeepoutZone[]>;
  /** 끌기 시작한 점(x1, y1)과 놓은 점(x2, y2). ADMIN · 1 관리자만 */
  addZone(id: number, z: { name: string; x1: number; y1: number; x2: number; y2: number }): Promise<KeepoutZone[]>;
  deleteZone(id: number, zoneId: number): Promise<KeepoutZone[]>;
  cancelGoTo(id: number): Promise<void>;
  // 지점
  points(): Promise<Point[]>;
  adminPoints(): Promise<Point[]>;
  savePoint(p: { point_id?: number; code?: string; name: string; description?: string | null; x: number; y: number; yawDeg: number; active?: boolean }): Promise<Point>;
  pointHistory(id: number): Promise<{ point: Point; observations: Observation[] }>;
  // 작업
  tasks(group?: string): Promise<TaskRow[]>;
  createTask(robotId: number, pointIds: number[], note: string): Promise<TaskDetail>;
  task(id: number): Promise<TaskDetail>;
  cancelTask(id: number): Promise<TaskDetail>;
  imageUrl(observationId: number): string;
  review(observationId: number, result: string, comment: string): Promise<Observation>;
  recheck(observationId: number): Promise<TaskDetail>;
  // 예약 점검
  schedules(): Promise<{ zone: string; schedules: Schedule[] }>;
  schedule(id: number): Promise<Schedule>;
  saveSchedule(s: ScheduleInput, id?: number): Promise<Schedule>;
  setScheduleEnabled(id: number, enabled: boolean): Promise<Schedule>;
  runSchedule(id: number): Promise<{ outcome: ScheduleOutcome | 'QUEUED'; taskId: number | null; reason: string | null }>;
  pendingRuns(): Promise<PendingRun[]>;
  scheduleBacklog(): Promise<Backlog>;
  cancelPendingRun(key: number): Promise<void>;
  deleteSchedule(id: number): Promise<void>;
  // A4 분석 · A6 시스템
  criteria(): Promise<Criteria>;
  saveCriteria(c: Criteria): Promise<Criteria>;
  system(): Promise<SystemStatus>;
  // 서버 시간(게이트웨이)
  serverTime(): Promise<{ epochMs: number; zone: string; offset: string; local: string }>;
}
