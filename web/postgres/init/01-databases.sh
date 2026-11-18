#!/bin/bash
# 서비스마다 자기 DB 와 계정을 하나씩 만든다(서비스 간 DB 공유 없음). 처음 볼륨을 만들 때만 실행된다.
set -euo pipefail
for svc in user inspection robot analysis; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
    CREATE ROLE ${svc}_svc LOGIN PASSWORD '${SERVICE_DB_PASSWORD}';
    CREATE DATABASE ${svc}db OWNER ${svc}_svc;
    REVOKE ALL ON DATABASE ${svc}db FROM PUBLIC;
SQL
done
