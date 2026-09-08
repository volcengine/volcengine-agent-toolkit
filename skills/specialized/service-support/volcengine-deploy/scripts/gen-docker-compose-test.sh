#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# gen-docker-compose-test.sh — Read a lightweight analysis/context JSON and
# emit a docker-compose.test.yml that includes the application image plus
# managed dependency containers (mysql / postgresql / redis / mongodb /
# kafka / rabbitmq / elasticsearch / memcached / clickhouse).
#
# The generated compose file lets the operator smoke-test the freshly built
# image locally before pushing to CR.
#
# Usage:
#   gen-docker-compose-test.sh <analysis-or-context.json> <image-name:tag> [app-port]
#
# Output: full YAML to stdout.

set -uo pipefail

report="${1:-}"
image="${2:-}"
app_port="${3:-}"

if [ -z "$report" ] || [ -z "$image" ]; then
  echo "Usage: $0 <analysis-or-context.json> <image-name:tag> [app-port]" >&2
  exit 2
fi

if [ ! -f "$report" ]; then
  echo "Error: report file not found: $report" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required" >&2
  exit 1
fi

# Derive port from context if not passed explicitly. Support the current
# lightweight deploy-choice shape and the older nested analysis shape.
[ -z "$app_port" ] && app_port=$(jq -r '.port // .repo_analysis.port // "8080"' "$report")

deps=$(jq -r '(.dependencies // .repo_analysis.dependencies // [])[]?' "$report")

# Collect env-var references the app should receive for each dep
app_envs=()
dep_blocks=""

emit_dep() {
  local name="$1"
  shift
  dep_blocks="${dep_blocks}$(printf '\n  %s:\n%s' "$name" "$*")"
}

for dep in $deps; do
  case "$dep" in
    mysql)
      emit_dep "mysql" "    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: testpw
      MYSQL_DATABASE: appdb
    ports: [\"3306:3306\"]
    healthcheck:
      test: [\"CMD\", \"mysqladmin\", \"ping\", \"-h\", \"localhost\"]
      interval: 5s
      retries: 10"
      app_envs+=("DB_HOST=mysql" "DB_PORT=3306" "DB_USER=root" "DB_PASSWORD=testpw" "DB_NAME=appdb")
      ;;
    postgresql)
      emit_dep "postgres" "    image: postgres:16
    environment:
      POSTGRES_PASSWORD: testpw
      POSTGRES_DB: appdb
    ports: [\"5432:5432\"]
    healthcheck:
      test: [\"CMD\", \"pg_isready\", \"-U\", \"postgres\"]
      interval: 5s
      retries: 10"
      app_envs+=("DB_HOST=postgres" "DB_PORT=5432" "DB_USER=postgres" "DB_PASSWORD=testpw" "DB_NAME=appdb")
      ;;
    redis)
      emit_dep "redis" "    image: redis:7-alpine
    ports: [\"6379:6379\"]
    healthcheck:
      test: [\"CMD\", \"redis-cli\", \"ping\"]
      interval: 5s
      retries: 10"
      app_envs+=("REDIS_HOST=redis" "REDIS_PORT=6379")
      ;;
    mongodb)
      emit_dep "mongo" "    image: mongo:7
    ports: [\"27017:27017\"]
    healthcheck:
      test: [\"CMD\", \"mongosh\", \"--eval\", \"db.adminCommand('ping')\"]
      interval: 5s
      retries: 10"
      app_envs+=("MONGO_URL=mongodb://mongo:27017/appdb")
      ;;
    kafka)
      emit_dep "kafka" "    image: bitnami/kafka:3.7
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: controller,broker
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    ports: [\"9092:9092\"]"
      app_envs+=("KAFKA_BOOTSTRAP=kafka:9092")
      ;;
    rabbitmq)
      emit_dep "rabbitmq" "    image: rabbitmq:3-management
    ports: [\"5672:5672\", \"15672:15672\"]
    healthcheck:
      test: [\"CMD\", \"rabbitmq-diagnostics\", \"ping\"]
      interval: 10s
      retries: 10"
      app_envs+=("RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/")
      ;;
    elasticsearch)
      emit_dep "elasticsearch" "    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      discovery.type: single-node
      xpack.security.enabled: \"false\"
      ES_JAVA_OPTS: -Xms512m -Xmx512m
    ports: [\"9200:9200\"]"
      app_envs+=("ES_HOSTS=http://elasticsearch:9200")
      ;;
    memcached)
      emit_dep "memcached" "    image: memcached:1.6-alpine
    ports: [\"11211:11211\"]"
      app_envs+=("MEMCACHED_SERVERS=memcached:11211")
      ;;
    clickhouse)
      emit_dep "clickhouse" "    image: clickhouse/clickhouse-server:latest
    ports: [\"8123:8123\", \"9000:9000\"]
    ulimits:
      nofile: 262144"
      app_envs+=("CLICKHOUSE_HOST=clickhouse" "CLICKHOUSE_PORT=8123")
      ;;
    tos|s3-compatible)
      # No local equivalent shipped — TOS is remote; surface a note instead
      emit_dep "minio" "    image: minio/minio:latest
    command: server /data
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports: [\"9000:9000\", \"9001:9001\"]"
      app_envs+=("S3_ENDPOINT=http://minio:9000" "S3_ACCESS_KEY=minio" "S3_SECRET_KEY=minio12345")
      ;;
    *)
      ;;
  esac
done

# Build the app's environment block as YAML list entries (- KEY=VALUE)
app_env_lines=""
for kv in ${app_envs[@]+"${app_envs[@]}"}; do
  app_env_lines="${app_env_lines}      - ${kv}"$'\n'
done

cat <<EOF
# Generated by gen-docker-compose-test.sh — local smoke test for $image
services:
  app:
    image: $image
    ports: ["${app_port}:${app_port}"]
    environment:
      - PORT=${app_port}
EOF

# Inline app env vars
if [ -n "$app_env_lines" ]; then
  printf '%s' "$app_env_lines"
fi

# Depends-on block (only if there are deps)
dep_names=$(printf '%s\n' $deps | sort -u | sed 's/tos\|s3-compatible/minio/' | sed 's/postgresql/postgres/' | sed 's/mongodb/mongo/' | tr '\n' ' ')
if [ -n "$dep_names" ] && [ "$dep_names" != " " ]; then
  echo "    depends_on:"
  for d in $dep_names; do
    echo "      $d:"
    echo "        condition: service_started"
  done
fi

# Append dependency service blocks
[ -n "$dep_blocks" ] && printf '%s\n' "$dep_blocks"
