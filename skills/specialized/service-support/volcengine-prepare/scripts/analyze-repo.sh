#!/usr/bin/env bash
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: MIT
# analyze-repo.sh — Analyze a project directory: language, framework, port,
# runtime dependencies, migration paths, entrypoint. Output JSON to stdout.
#
# Usage: bash analyze-repo.sh <repo-directory>
# Exit non-zero only on hard errors (missing dir). Unknown values become
# "unknown"/empty arrays so downstream agents can keep moving.

set -euo pipefail

repo_dir="${1:-.}"

if [ ! -d "$repo_dir" ]; then
  echo "{\"error\": \"Directory not found: ${repo_dir}\"}"
  exit 1
fi

cd "$repo_dir"

# ---------- helpers ----------

# Build a JSON array literal from positional args. Empty -> [].
json_array() {
  local items=("$@")
  if [ ${#items[@]} -eq 0 ]; then
    echo "[]"
    return
  fi
  local result="["
  local i
  for i in "${!items[@]}"; do
    [ "$i" -gt 0 ] && result+=","
    result+="\"${items[$i]}\""
  done
  result+="]"
  echo "$result"
}

# Glob expansion safe inside `if`. Returns 0 if pattern matches any file/dir.
has_glob() {
  local pattern="$1"
  [ -n "$(find . -maxdepth 2 -name "$pattern" 2>/dev/null | head -1)" ]
}

detect_compose_file() {
  for f in compose.yaml compose.yml docker-compose.yaml docker-compose.yml; do
    [ -f "$f" ] && echo "$f" && return
  done
  echo ""
}

detect_compose_file_in_dir() {
  local dir="$1"
  for f in compose.yaml compose.yml docker-compose.yaml docker-compose.yml; do
    [ -f "$dir/$f" ] && echo "$f" && return
  done
  echo ""
}

is_deployable_dir() {
  local dir="$1"
  [ -f "$dir/Dockerfile" ] && return 0
  [ -n "$(detect_compose_file_in_dir "$dir")" ] && return 0

  if [ -f "$dir/package.json" ]; then
    if grep -qE '"(start|dev|build|serve|preview)"[[:space:]]*:' "$dir/package.json"; then
      return 0
    fi
  fi

  if [ -f "$dir/bun.lock" ] || [ -f "$dir/bun.lockb" ] || [ -f "$dir/deno.json" ] || [ -f "$dir/deno.jsonc" ]; then
    return 0
  fi
  if [ -f "$dir/go.mod" ] && { [ -f "$dir/main.go" ] || [ -d "$dir/cmd" ]; }; then
    return 0
  fi
  if [ -f "$dir/requirements.txt" ] || [ -f "$dir/pyproject.toml" ] || [ -f "$dir/setup.py" ]; then
    if [ -f "$dir/main.py" ] || [ -f "$dir/app.py" ] || [ -f "$dir/manage.py" ] ||
      [ -f "$dir/wsgi.py" ] || [ -f "$dir/asgi.py" ] || [ -d "$dir/src" ]; then
      return 0
    fi
  fi
  if [ -f "$dir/pom.xml" ] || [ -f "$dir/build.gradle" ] || [ -f "$dir/build.gradle.kts" ]; then
    return 0
  fi
  if [ -f "$dir/Cargo.toml" ] && [ -f "$dir/src/main.rs" ]; then
    return 0
  fi
  if [ -f "$dir/Gemfile" ] && { [ -f "$dir/config.ru" ] || [ -f "$dir/app.rb" ] || [ -d "$dir/bin" ]; }; then
    return 0
  fi
  if [ -f "$dir/composer.json" ] && { [ -f "$dir/public/index.php" ] || [ -f "$dir/index.php" ]; }; then
    return 0
  fi
  find "$dir" -maxdepth 1 \( -name "*.csproj" -o -name "*.sln" \) 2>/dev/null | grep -q . && return 0

  return 1
}

detect_deploy_subdir() {
  is_deployable_dir "." && { echo "."; return; }

  local candidates=(site web app apps frontend backend server api homepage)
  local dir
  for dir in "${candidates[@]}"; do
    [ -d "$dir" ] && is_deployable_dir "$dir" && { echo "$dir"; return; }
  done

  while IFS= read -r dir; do
    is_deployable_dir "$dir" && { echo "${dir#./}"; return; }
  done < <(find packages apps services -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

  echo ""
}

# ---------- language detection ----------
# Order matters: Bun/Deno take priority over Node since they may coexist
# with package.json but use different runtimes. PHP added.

detect_language() {
  if [ -f "bun.lock" ] || [ -f "bun.lockb" ]; then echo "bun"
  elif [ -f "deno.json" ] || [ -f "deno.jsonc" ] || [ -f "deno.lock" ]; then echo "deno"
  elif [ -f "package.json" ]; then echo "nodejs"
  elif [ -f "go.mod" ]; then echo "go"
  elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then echo "python"
  elif [ -f "pom.xml" ] || [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then echo "java"
  elif [ -f "Cargo.toml" ]; then echo "rust"
  elif [ -f "Gemfile" ]; then echo "ruby"
  elif [ -f "composer.json" ]; then echo "php"
  elif has_glob "*.csproj" || has_glob "*.sln"; then echo "dotnet"
  elif [ -f "mix.exs" ]; then echo "elixir"
  else echo "unknown"
  fi
}

# ---------- framework detection ----------

detect_framework() {
  local lang="$1"
  case "$lang" in
    nodejs|bun|deno)
      local deps=""
      [ -f "package.json" ] && deps=$(cat package.json)
      [ -f "deno.json" ] && deps="$deps $(cat deno.json)"
      if echo "$deps" | grep -q '"@nestjs/core"'; then echo "nestjs"
      elif echo "$deps" | grep -q '"next"'; then echo "nextjs"
      elif echo "$deps" | grep -q '"express"'; then echo "express"
      elif echo "$deps" | grep -q '"fastify"'; then echo "fastify"
      elif echo "$deps" | grep -q '"koa"'; then echo "koa"
      elif echo "$deps" | grep -q '"hono"'; then echo "hono"
      elif echo "$deps" | grep -q '"oak"'; then echo "oak"
      else echo "unknown"
      fi
      ;;
    python)
      local all_deps=""
      [ -f "requirements.txt" ] && all_deps=$(cat requirements.txt)
      [ -f "pyproject.toml" ] && all_deps="$all_deps $(cat pyproject.toml)"
      if echo "$all_deps" | grep -qi "fastapi"; then echo "fastapi"
      elif echo "$all_deps" | grep -qi "django"; then echo "django"
      elif echo "$all_deps" | grep -qi "flask"; then echo "flask"
      elif echo "$all_deps" | grep -qi "tornado"; then echo "tornado"
      elif echo "$all_deps" | grep -qi "sanic"; then echo "sanic"
      else echo "unknown"
      fi
      ;;
    go)
      if [ -f "go.mod" ]; then
        local mods
        mods=$(cat go.mod)
        if echo "$mods" | grep -q "gin-gonic"; then echo "gin"
        elif echo "$mods" | grep -q "labstack/echo"; then echo "echo"
        elif echo "$mods" | grep -q "gofiber/fiber"; then echo "fiber"
        elif echo "$mods" | grep -q "go-chi/chi"; then echo "chi"
        elif echo "$mods" | grep -q "gorilla/mux"; then echo "gorilla"
        else echo "unknown"
        fi
      fi
      ;;
    java)
      local build_file=""
      [ -f "pom.xml" ] && build_file=$(cat pom.xml)
      [ -f "build.gradle" ] && build_file="$build_file $(cat build.gradle)"
      [ -f "build.gradle.kts" ] && build_file="$build_file $(cat build.gradle.kts)"
      if echo "$build_file" | grep -qi "spring-boot"; then echo "spring-boot"
      elif echo "$build_file" | grep -qi "quarkus"; then echo "quarkus"
      elif echo "$build_file" | grep -qi "micronaut"; then echo "micronaut"
      else echo "unknown"
      fi
      ;;
    rust)
      if [ -f "Cargo.toml" ]; then
        local cargo
        cargo=$(cat Cargo.toml)
        if echo "$cargo" | grep -q "actix-web"; then echo "actix"
        elif echo "$cargo" | grep -q "axum"; then echo "axum"
        elif echo "$cargo" | grep -q "rocket"; then echo "rocket"
        elif echo "$cargo" | grep -q "warp"; then echo "warp"
        else echo "unknown"
        fi
      fi
      ;;
    ruby)
      if [ -f "Gemfile" ]; then
        if grep -q "rails" Gemfile; then echo "rails"
        elif grep -q "sinatra" Gemfile; then echo "sinatra"
        else echo "unknown"
        fi
      fi
      ;;
    php)
      if [ -f "composer.json" ]; then
        local composer
        composer=$(cat composer.json)
        if echo "$composer" | grep -q "laravel/framework"; then echo "laravel"
        elif echo "$composer" | grep -q "symfony/symfony\|symfony/framework-bundle"; then echo "symfony"
        elif echo "$composer" | grep -q "slim/slim"; then echo "slim"
        else echo "unknown"
        fi
      fi
      ;;
    *) echo "unknown" ;;
  esac
}

# ---------- port detection ----------

detect_port() {
  local port=""

  # Dockerfile EXPOSE
  if [ -f "Dockerfile" ]; then
    port=$(grep -i "^EXPOSE" Dockerfile 2>/dev/null | head -1 | grep -oE '[0-9]+' | head -1)
    [ -n "$port" ] && echo "$port" && return
  fi

  # docker-compose ports
  local compose_file
  compose_file=$(detect_compose_file)
  if [ -n "$compose_file" ]; then
    port=$(grep -E 'ports:' -A 5 "$compose_file" 2>/dev/null | grep -oE '[0-9]+:[0-9]+' | head -1 | cut -d: -f2)
    [ -n "$port" ] && echo "$port" && return
  fi

  # Source code scan: widened from depth 3/30 files to depth 5/100 files
  local all_code=""
  while IFS= read -r f; do
    all_code="$all_code $(cat "$f" 2>/dev/null || true)"
  done < <(find . -maxdepth 5 \( -name "*.js" -o -name "*.ts" -o -name "*.py" \
    -o -name "*.go" -o -name "*.java" -o -name "*.rs" -o -name "*.rb" -o -name "*.php" \
    -o -name "*.env" -o -name "*.env.example" \
    -o -name "application.yml" -o -name "application.properties" \) 2>/dev/null | head -100)

  port=$(echo "$all_code" | grep -oiE 'port\s*[=:]\s*[0-9]+' | grep -oE '[0-9]+' | head -1)
  [ -n "$port" ] && echo "$port" && return

  # Framework default fallback
  local lang
  lang=$(detect_language)
  case "$lang" in
    nodejs|bun|deno) echo "3000" ;;
    python) echo "8000" ;;
    go) echo "8080" ;;
    java) echo "8080" ;;
    rust) echo "8080" ;;
    ruby) echo "3000" ;;
    php) echo "8000" ;;
    dotnet) echo "5000" ;;
    *) echo "8080" ;;
  esac
}

# ---------- runtime dependency detection ----------

detect_dependencies() {
  local deps=()

  local search_content=""

  # Config files
  for f in compose.yaml compose.yml docker-compose.yml docker-compose.yaml .env .env.example \
    .env.sample config.yml config.yaml application.yml application.properties \
    appsettings.json; do
    [ -f "$f" ] && search_content="$search_content $(cat "$f" 2>/dev/null || true)"
  done

  # Manifest files
  for f in package.json go.mod requirements.txt pyproject.toml pom.xml \
    build.gradle build.gradle.kts Cargo.toml Gemfile composer.json deno.json; do
    [ -f "$f" ] && search_content="$search_content $(cat "$f" 2>/dev/null || true)"
  done

  # Source scan: depth 5 / 100 files (was depth 4 / 30)
  while IFS= read -r f; do
    search_content="$search_content $(cat "$f" 2>/dev/null || true)"
  done < <(find . -maxdepth 5 \( -name "*.js" -o -name "*.ts" -o -name "*.py" \
    -o -name "*.go" -o -name "*.java" -o -name "*.rs" -o -name "*.rb" -o -name "*.php" \) \
    2>/dev/null | head -100)

  if echo "$search_content" | grep -qiE 'mysql|mysql2|mysqlclient|pymysql|jdbc:mysql|:3306'; then
    deps+=("mysql")
  fi
  if echo "$search_content" | grep -qiE 'postgres|postgresql|psycopg|pg-promise|jdbc:postgresql|:5432'; then
    deps+=("postgresql")
  fi
  if echo "$search_content" | grep -qiE 'redis|ioredis|redis-py|bull|:6379'; then
    deps+=("redis")
  fi
  if echo "$search_content" | grep -qiE 'mongodb|mongoose|pymongo|mongoclient|:27017'; then
    deps+=("mongodb")
  fi
  if echo "$search_content" | grep -qiE 'kafka|kafkajs|kafka-python|confluent.kafka|:9092'; then
    deps+=("kafka")
  fi
  if echo "$search_content" | grep -qiE 'rabbitmq|amqplib|amqp|pika|:5672'; then
    deps+=("rabbitmq")
  fi
  # Memcached (new)
  if echo "$search_content" | grep -qiE 'memcache|memcached|pymemcache|:11211'; then
    deps+=("memcached")
  fi
  # ClickHouse (new) — bare keyword catches drivers and class references
  if echo "$search_content" | grep -qiE 'clickhouse|:8123'; then
    deps+=("clickhouse")
  fi
  if echo "$search_content" | grep -qiE 'elasticsearch|@elastic|opensearch|:9200'; then
    deps+=("elasticsearch")
  fi
  # Volcengine TOS
  if echo "$search_content" | grep -qiE '@volcengine/tos|tos-sdk|tos\.volces\.com|TOS_BUCKET|VOLCENGINE_TOS'; then
    deps+=("tos")
  fi
  # Object storage compatibility signals.
  # Skip if TOS already detected (TOS is the preferred Volcengine equivalent).
  local has_tos=false
  local d
  for d in ${deps[@]+"${deps[@]}"}; do
    [ "$d" = "tos" ] && has_tos=true && break
  done
  if [ "$has_tos" = false ]; then
    if echo "$search_content" | grep -qiE 'minio|MINIO_ENDPOINT|s3cmd|minio-py|boto3'; then
      deps+=("s3-compatible")
    fi
  fi

  json_array ${deps[@]+"${deps[@]}"}
}

# ---------- migration detection ----------

detect_migration() {
  local migration_paths=()

  for dir in migrations db/migrate prisma alembic flyway src/main/resources/db/migration \
    database/migrations knex/migrations sql; do
    [ -d "$dir" ] && migration_paths+=("$dir")
  done

  [ -f "prisma/schema.prisma" ] && migration_paths+=("prisma/schema.prisma")

  for f in init.sql schema.sql setup.sql; do
    [ -f "$f" ] && migration_paths+=("$f")
  done

  json_array ${migration_paths[@]+"${migration_paths[@]}"}
}

# ---------- Dockerfile presence ----------

has_dockerfile() {
  [ -f "Dockerfile" ] && echo "true" || echo "false"
}

has_compose() {
  [ -n "$(detect_compose_file)" ] && echo "true" || echo "false"
}

# ---------- entrypoint detection ----------

detect_entrypoint() {
  local lang="$1"
  case "$lang" in
    nodejs|bun|deno)
      if [ -f "package.json" ]; then
        local main
        main=$(grep -oE '"main"\s*:\s*"[^"]+"' package.json 2>/dev/null \
          | grep -oE '"[^"]+"\s*$' | tr -d '"' | xargs || true)
        [ -n "$main" ] && echo "$main" && return
        local start_script
        start_script=$(grep -oE '"start"\s*:\s*"[^"]+"' package.json 2>/dev/null | head -1)
        [ -n "$start_script" ] && echo "npm start" && return
      fi
      for f in src/index.ts src/main.ts src/server.ts src/app.ts index.ts \
        src/index.js src/main.js src/server.js src/app.js index.js server.js app.js \
        main.ts mod.ts; do
        [ -f "$f" ] && echo "$f" && return
      done
      ;;
    python)
      for f in main.py app.py manage.py src/main.py src/app.py wsgi.py asgi.py; do
        [ -f "$f" ] && echo "$f" && return
      done
      ;;
    go)
      [ -d "cmd" ] && echo "cmd/" && return
      [ -f "main.go" ] && echo "main.go" && return
      ;;
    java)
      local main_class
      main_class=$(find . -maxdepth 6 -name "*.java" \
        -exec grep -l "public static void main" {} \; 2>/dev/null | head -1)
      [ -n "$main_class" ] && echo "$main_class" && return
      [ -f "pom.xml" ] && echo "pom.xml (Maven)" && return
      [ -f "build.gradle" ] && echo "build.gradle (Gradle)" && return
      ;;
    rust)
      [ -f "src/main.rs" ] && echo "src/main.rs" && return
      ;;
    ruby)
      [ -f "config.ru" ] && echo "config.ru" && return
      [ -f "app.rb" ] && echo "app.rb" && return
      ;;
    php)
      [ -f "public/index.php" ] && echo "public/index.php" && return
      [ -f "index.php" ] && echo "index.php" && return
      ;;
    dotnet)
      local proj
      proj=$(find . -maxdepth 2 -name "*.csproj" 2>/dev/null | head -1)
      [ -n "$proj" ] && echo "$proj" && return
      ;;
  esac
  echo "unknown"
}

# ---------- main ----------

repo_root=$(pwd)
deploy_subdir=$(detect_deploy_subdir)
analysis_dir="$repo_root"
if [ -n "$deploy_subdir" ] && [ "$deploy_subdir" != "." ]; then
  analysis_dir="$repo_root/$deploy_subdir"
  cd "$analysis_dir"
fi

language=$(detect_language)
framework=$(detect_framework "$language")
port=$(detect_port)
has_dockerfile=$(has_dockerfile)
has_compose=$(has_compose)
compose_file=$(detect_compose_file)
dependencies=$(detect_dependencies)
migration=$(detect_migration)
entrypoint=$(detect_entrypoint "$language")
runnable=$([ -n "$deploy_subdir" ] && echo "true" || echo "false")

cat <<EOF
{
  "repo_dir": "$repo_dir",
  "deploy_subdir": "$deploy_subdir",
  "language": "$language",
  "framework": "$framework",
  "port": "$port",
  "has_dockerfile": $has_dockerfile,
  "has_compose": $has_compose,
  "compose_file": "$compose_file",
  "entrypoint": "$entrypoint",
  "dependencies": $dependencies,
  "migration_paths": $migration,
  "runnable": $runnable
}
EOF
