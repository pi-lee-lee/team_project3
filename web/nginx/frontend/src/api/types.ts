// 화면이 기대하는 데이터 모양과 API 인터페이스.
// 화면은 이 인터페이스에만 의존하고, 실제 구현(http.ts)은 게이트웨이 REST API 를 호출한다.
// 로봇이 시뮬레이션이든 실제든 화면 코드는 바뀌지 않는다(차이는 robot-service 의 어댑터가 흡수).

export type Role = 'ADMIN' | 'SUPERVISOR' | 'MANAGER' | 'USER';

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
  manualGoal: ManualGoal | null;
  mission: { missionId: number; currentPointId: number | null } | null;
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

export interface Api {
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
