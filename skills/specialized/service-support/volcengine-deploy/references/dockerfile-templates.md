# Dockerfile templates

When the repo has no Dockerfile, generate one based on the project type. All templates follow best practices:
- Multi-stage build
- Non-root user
- Minimal base image
- HEALTHCHECK instruction
- Pinned version tags

---

## Node.js (Express / Fastify / NestJS / Koa)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production && cp -R node_modules /prod_modules
RUN npm ci
COPY . .
RUN npm run build 2>/dev/null || true

FROM node:20-alpine
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /prod_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./
COPY --from=builder /app/src ./src
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1
CMD ["node", "dist/index.js"]
```

> **Adaptation notes**:
> - Adjust the port from `PORT` in `package.json` or from code detection
> - If there is no build step, drop `npm run build` and the `dist` directory and `COPY src` directly
> - If using `yarn`/`pnpm`, replace with the matching package-manager commands
> - NestJS start command is usually `node dist/main.js`

---

## Python (FastAPI / Flask / Django)

### FastAPI / Flask

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Django

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN python manage.py collectstatic --noinput 2>/dev/null || true
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "config.wsgi:application"]
```

> **Adaptation notes**:
> - Adjust Django's WSGI module path to the project structure
> - If a `pyproject.toml` exists, use `pip install .` instead of `requirements.txt`
> - Poetry projects: run `poetry export -f requirements.txt` first, then install

---

## Go

```dockerfile
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server ./cmd/server

FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/server /server
USER nonroot:nonroot
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["/server", "--health-check"]
ENTRYPOINT ["/server"]
```

> **Adaptation notes**:
> - Adjust the `./cmd/server` path to the actual main package location
> - If `main.go` is in the repo root, use `.` instead
> - distroless images have no shell; use `alpine` instead if you need to debug
> - distroless does not support the CMD shell form of HEALTHCHECK; use a K8s probe instead

---

## Java (Spring Boot / Quarkus)

### Spring Boot (Maven)

```dockerfile
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY pom.xml mvnw ./
COPY .mvn .mvn
RUN chmod +x mvnw && ./mvnw dependency:go-offline -B
COPY src src
RUN ./mvnw package -DskipTests -B && \
    java -Djarmode=layertools -jar target/*.jar extract --destination /extracted

FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /extracted/dependencies/ ./
COPY --from=builder /extracted/spring-boot-loader/ ./
COPY --from=builder /extracted/snapshot-dependencies/ ./
COPY --from=builder /extracted/application/ ./
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

### Spring Boot (Gradle)

```dockerfile
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY build.gradle* settings.gradle* gradlew ./
COPY gradle gradle
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon
COPY src src
RUN ./gradlew bootJar --no-daemon -x test

FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## Rust

```dockerfile
FROM rust:1.77-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main(){}" > src/main.rs && cargo build --release && rm -rf src
COPY . .
RUN touch src/main.rs && cargo build --release

FROM alpine:3.19
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app/target/release/<binary-name> /usr/local/bin/app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/health || exit 1
CMD ["app"]
```

> **Adaptation notes**: replace `<binary-name>` with the `[[bin]]` name or package name in `Cargo.toml`

---

## Ruby (Rails)

```dockerfile
FROM ruby:3.3-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY Gemfile Gemfile.lock ./
RUN bundle config set --local without 'development test' && bundle install
COPY . .
RUN SECRET_KEY_BASE=placeholder bundle exec rails assets:precompile 2>/dev/null || true

FROM ruby:3.3-slim
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --from=builder /app .
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ruby -e "require 'net/http'; Net::HTTP.get(URI('http://localhost:3000/health'))" || exit 1
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
```

---

## .dockerignore (common)

Regardless of language, always generate a `.dockerignore`:

```text
.git
.gitignore
.env
.env.*
node_modules
__pycache__
*.pyc
.pytest_cache
.mypy_cache
target/debug
target/release/deps
target/release/build
*.log
.DS_Store
.vscode
.idea
*.md
!README.md
docker-compose*.yml
Dockerfile
.dockerignore
tests/
test/
spec/
coverage/
.github/
```

---

## Gotchas (image build / architecture)

| Symptom | Cause | Fix |
|---|---|---|
| Container exits immediately with `exec format error` on VKE/ECS | image architecture does not match the target node architecture (common when building directly on Apple Silicon/arm64) | Build for the target architecture: `docker buildx build --platform linux/amd64 ...`; do not trust the local Docker default platform; inspect the pushed image platform before rollout |
| Runs locally but crashes once pushed | a local arm64 image was pushed to amd64 nodes | Rebuild/push with explicit `--platform linux/amd64`; VKE defaults to `linux/amd64` unless node-pool data proves another architecture |
