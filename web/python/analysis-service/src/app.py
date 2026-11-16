"""analysis-service: 관측 사진의 품질 분석(배치).

- POST /jobs {"observationId": 12}  : 작업을 큐(analysis_job 테이블)에 넣고 NOTIFY 로 워커를 깨운다.
- 워커: LISTEN 으로 깨어나 FOR UPDATE SKIP LOCKED 로 작업을 하나씩 가져가 처리한다.
  사진은 inspection-service 에서 받고, 결과도 inspection-service 로 보낸다.
- GET/PUT /api/admin/analysis/criteria : 판정 기준(밝기·선명도·관심 영역). 게이트웨이가 ADMIN 으로 제한한다.

판정: 관심 영역(ROI)의 평균 밝기와 선명도(라플라시안 분산)가 기준 밖이면 RETAKE(재촬영 후보).
"""
import io
import logging
import os
import threading
import time

import httpx
import numpy as np
import psycopg
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

DB_URL = os.environ.get('DB_URL', 'postgresql://analysis_svc@db:5432/analysisdb')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
INSPECTION_URL = os.environ.get('INSPECTION_SERVICE_URL', 'http://inspection-service:8082')

log = logging.getLogger('analysis')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_job (
    job_id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint      NOT NULL,
    status         varchar(10) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')),
    attempts       integer     NOT NULL DEFAULT 0,
    error          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz
);
CREATE INDEX IF NOT EXISTS idx_job_pending ON analysis_job (job_id) WHERE status = 'PENDING';
CREATE TABLE IF NOT EXISTS analysis_criteria (
    id              smallint PRIMARY KEY CHECK (id = 1),
    min_brightness  double precision NOT NULL,
    max_brightness  double precision NOT NULL,
    min_sharpness   double precision NOT NULL,
    roi             double precision[] NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
INSERT INTO analysis_criteria (id, min_brightness, max_brightness, min_sharpness, roi)
VALUES (1, 60, 200, 80, ARRAY[0.2, 0.2, 0.8, 0.8]) ON CONFLICT (id) DO NOTHING;
"""


def connect(autocommit=True):
    return psycopg.connect(DB_URL, password=DB_PASSWORD, autocommit=autocommit)


def wait_for_db():
    for _ in range(60):
        try:
            with connect() as c:
                c.execute(SCHEMA)
            return
        except psycopg.OperationalError as e:
            log.info('waiting for db: %s', e)
            time.sleep(2)
    raise RuntimeError('db not available')


# ------------------------------------------------------------------ 분석
def load_criteria(conn):
    row = conn.execute('SELECT min_brightness, max_brightness, min_sharpness, roi FROM analysis_criteria WHERE id = 1').fetchone()
    return {'minBrightness': row[0], 'maxBrightness': row[1], 'minSharpness': row[2], 'roi': list(row[3])}


def analyze(jpeg: bytes, c: dict) -> dict:
    img = Image.open(io.BytesIO(jpeg)).convert('L')
    a = np.asarray(img, dtype=np.float64)
    h, w = a.shape
    x0, y0, x1, y1 = c['roi']
    roi = a[int(y0 * h):max(int(y1 * h), int(y0 * h) + 3), int(x0 * w):max(int(x1 * w), int(x0 * w) + 3)]
    brightness = float(roi.mean())
    # 라플라시안(4-이웃) 분산: 값이 작을수록 흐리다
    lap = (-4 * roi[1:-1, 1:-1] + roi[:-2, 1:-1] + roi[2:, 1:-1] + roi[1:-1, :-2] + roi[1:-1, 2:])
    sharpness = float(lap.var())
    reasons = []
    if brightness < c['minBrightness']:
        reasons.append(f'너무 어두움 ({brightness:.0f} < {c["minBrightness"]:.0f})')
    if brightness > c['maxBrightness']:
        reasons.append(f'너무 밝음 ({brightness:.0f} > {c["maxBrightness"]:.0f})')
    if sharpness < c['minSharpness']:
        reasons.append(f'흐림 (선명도 {sharpness:.0f} < {c["minSharpness"]:.0f})')
    return {'brightness': round(brightness, 1), 'sharpness': round(sharpness, 1),
            'verdict': 'RETAKE' if reasons else 'OK', 'reasons': ', '.join(reasons), 'criteria': c}


def process_one(conn, http: httpx.Client) -> bool:
    """작업 하나를 처리했으면 True."""
    with conn.transaction():
        row = conn.execute("""
            SELECT job_id, observation_id FROM analysis_job
            WHERE status = 'PENDING' ORDER BY job_id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
        if not row:
            return False
        job_id, obs_id = row
        conn.execute("UPDATE analysis_job SET status = 'RUNNING', attempts = attempts + 1 WHERE job_id = %s", (job_id,))
    try:
        r = http.get(f'{INSPECTION_URL}/internal/observations/{obs_id}/image')
        r.raise_for_status()
        result = analyze(r.content, load_criteria(conn))
        http.post(f'{INSPECTION_URL}/internal/observations/{obs_id}/analysis', json=result).raise_for_status()
        conn.execute("UPDATE analysis_job SET status = 'DONE', finished_at = now() WHERE job_id = %s", (job_id,))
        log.info('observation %s -> %s %s', obs_id, result['verdict'], result['reasons'])
    except Exception as e:  # noqa: BLE001 - 실패는 기록하고 다음 작업으로
        conn.execute("UPDATE analysis_job SET status = 'FAILED', error = %s, finished_at = now() WHERE job_id = %s",
                     (str(e)[:500], job_id))
        log.warning('observation %s failed: %s', obs_id, e)
    return True


def worker():
    while True:
        try:
            with connect() as listen_conn, connect() as conn, httpx.Client(timeout=10) as http:
                listen_conn.execute('LISTEN analysis_job')
                while True:
                    while process_one(conn, http):
                        pass
                    # 새 작업 알림을 최대 10초 기다린다(알림을 놓쳐도 10초마다 다시 확인)
                    for _ in listen_conn.notifies(timeout=10, stop_after=1):
                        pass
        except Exception as e:  # noqa: BLE001
            log.warning('worker restart: %s', e)
            time.sleep(3)


# ------------------------------------------------------------------ API
app = FastAPI(title='analysis-service')


class Job(BaseModel):
    observationId: int


class Criteria(BaseModel):
    minBrightness: float = Field(ge=0, le=255)
    maxBrightness: float = Field(ge=0, le=255)
    minSharpness: float = Field(ge=0)
    roi: list[float] = Field(min_length=4, max_length=4)


@app.on_event('startup')
def startup():
    wait_for_db()
    threading.Thread(target=worker, daemon=True, name='analysis-worker').start()


@app.get('/health')
def health():
    with connect() as c:
        pending = c.execute("SELECT count(*) FROM analysis_job WHERE status = 'PENDING'").fetchone()[0]
    return {'status': 'UP', 'pending': pending}


@app.post('/jobs', status_code=202)
def enqueue(job: Job):
    with connect() as c:
        dup = c.execute("SELECT job_id FROM analysis_job WHERE observation_id = %s AND status IN ('PENDING','RUNNING')",
                        (job.observationId,)).fetchone()
        if dup:
            return {'jobId': dup[0], 'duplicate': True}
        job_id = c.execute('INSERT INTO analysis_job (observation_id) VALUES (%s) RETURNING job_id',
                           (job.observationId,)).fetchone()[0]
        c.execute('NOTIFY analysis_job')
    return {'jobId': job_id, 'duplicate': False}


@app.get('/api/admin/analysis/criteria')
def get_criteria():
    with connect() as c:
        return load_criteria(c)


@app.put('/api/admin/analysis/criteria')
def put_criteria(body: Criteria):
    x0, y0, x1, y1 = body.roi
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise HTTPException(400, '관심 영역은 0~1 비율이며 x0<x1, y0<y1 이어야 합니다')
    if body.minBrightness >= body.maxBrightness:
        raise HTTPException(400, '밝기 최소값은 최대값보다 작아야 합니다')
    with connect() as c:
        c.execute("""UPDATE analysis_criteria SET min_brightness = %s, max_brightness = %s, min_sharpness = %s,
                     roi = %s, updated_at = now() WHERE id = 1""",
                  (body.minBrightness, body.maxBrightness, body.minSharpness, body.roi))
        return load_criteria(c)


@app.get('/api/admin/analysis/jobs')
def jobs(limit: int = 50):
    with connect() as c:
        rows = c.execute("""SELECT job_id, observation_id, status, attempts, error, created_at, finished_at
                            FROM analysis_job ORDER BY job_id DESC LIMIT %s""", (min(limit, 200),)).fetchall()
    keys = ['jobId', 'observationId', 'status', 'attempts', 'error', 'createdAt', 'finishedAt']
    return [dict(zip(keys, r)) for r in rows]


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8084)
