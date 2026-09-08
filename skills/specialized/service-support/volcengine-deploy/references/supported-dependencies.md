# Supported runtime dependencies

## Wiring loop

A managed dependency is not done when it reports "created". Before deploying the app, complete this loop:

1. Get the private endpoint and ensure the dependency and ECS/VKE are in the same VPC when the selected product uses private VPC connectivity.
2. Create the app database/account or app Redis account, and generate or collect the password.
3. Add the ECS/VKE subnet CIDR, security group source, or node source to the dependency allowlist.
4. Assemble runtime variables such as `DATABASE_URL`, engine-specific database connection strings, and `REDIS_URL`, then hand them to the env/Secret injection stage of `volcengine-deploy`.
5. If `migration_paths` is non-empty, run migrations first, then do the final health check.

Do not use a public endpoint as the default wiring method; only do so when the user explicitly asks for public exposure and accepts the security group / allowlist risk.

When managed dependency creation fails with a missing `ServiceRoleFor...` role, or when you need to preflight account readiness for common deployment products, use [`service-linked-roles.md`](./service-linked-roles.md). Confirm the exact `ServiceName` and template before calling `CreateServiceLinkedRole`; do not infer it from the role name.

## Database Product Choice

Represent database selection with:

```json
{
  "database_product": "rds",
  "database_engine": "mysql"
}
```

Valid combinations:

| Product | Engines | Execution path |
| --- | --- | --- |
| `rds` | `mysql`, `postgresql`, `sqlserver` | Use the matching RDS CLI service: `rdsmysql`, `rdspostgresql`, or `rdsmssql` |
| `aidap` | `supabase`, `postgresql` | Call `volcengine-db-supabase` for AIDAP workspace provisioning |

AIDAP here refers to Volcengine's `AI 原生 BaaS 平台 Supabase 版` product; for deployment, treat its database workspace surface as the managed database provider. Keep deploy selection at the stable engine level (`supabase` or `postgresql`) and let `volcengine-db-supabase` resolve current `CreateWorkspace` `EngineType` / `EngineVersion` enums. Do not model AIDAP Supabase as an RDS PostgreSQL provider variant.

### MySQL
**Detection keywords** (config files / code / dependencies):
- `mysql`, `mysql2`, `mysqlclient`, `pymysql`, `MYSQL_HOST`, `3306`, `mysql://`, `jdbc:mysql`
- `image: mysql` in `docker-compose.yml`

**Volcengine product/engine**: `database_product=rds`, `database_engine=mysql`

**Volcengine service**: RDS MySQL (`ve rdsmysql`)

**Creation parameters**:
```bash
# RDS swagger discovery can return 404; use CLI help for the body schema.
ve rdsmysql CreateDBInstance --help
```

**Recommended spec** (entry level):
- Instance type: `HA` (high availability)
- Spec: `rds.mysql.2c4g` (2 vCPU / 4 GB)
- Storage: 20GB ESSD PL0
- Version: MySQL 8.0

**Notes**:
- Must be in the same VPC as VKE
- After creation, create the database and account
- The allowlist must include the VKE subnet CIDR
- Assemble the private endpoint, database name, account, and password into `DATABASE_URL`; do not write credentials to logs

---

### PostgreSQL
**Detection keywords**:
- `pg`, `postgres`, `postgresql`, `psycopg2`, `pg-promise`, `POSTGRES_HOST`, `5432`, `postgres://`, `jdbc:postgresql`
- `image: postgres` in `docker-compose.yml`

**Volcengine product/engine options**:
- `database_product=rds`, `database_engine=postgresql`: RDS PostgreSQL (`ve rdspostgresql`) for managed RDS PostgreSQL.
- `database_product=aidap`, `database_engine=postgresql`: AIDAP PostgreSQL engine workspace via `volcengine-db-supabase`.
- `database_product=aidap`, `database_engine=supabase`: AIDAP Supabase engine workspace via `volcengine-db-supabase`.

When the user explicitly chooses an AIDAP engine from the console choices, preserve that choice. If they only say "PostgreSQL", ask whether they want RDS PostgreSQL, AIDAP PostgreSQL, or AIDAP Supabase unless the surrounding deployment context already makes one product clear or the user has delegated the choice. If the user says "you decide" and there is no explicit RDS/AIDAP PostgreSQL/Supabase signal, use AIDAP Supabase.

**Recommended spec**:
- Instance type: `HA`
- Spec: `rds.postgres.2c4g`
- Storage: 20GB ESSD PL0
- Version: PostgreSQL 15

**Wiring**:
- For HA instances, `NodeInfo` at creation must include both `Primary` and `Secondary`
- Use `Inherit,Login` for the app account privileges, not `ReadWrite`
- When creating the database, prefer setting `Owner` to the app account; if migrations still lack `public` schema privileges, run `ModifySchemaOwner` on `public`
- Omit `CharacterSetName` on `CreateDatabase` at first; do not pass an unverified uppercase `UTF8`
- After the instance reaches `Running`, account/database/schema operations may still hit a brief exclusive status; wait and retry
- After creating the database and app account, assemble `DATABASE_URL` from the private endpoint
- Add the ECS/VKE subnet CIDR or security group source to the allowlist
- When a migration directory exists, run migrations first, then ramp the health check

#### AIDAP database workspace

Use `volcengine-db-supabase` when `database_product=aidap`. Do not duplicate AIDAP workspace provisioning or use a cross-plugin relative path in `volcengine-deploy`; activate that skill and let it follow its own `references/deploy-provider.md`. If it is unavailable, use `volcengine-find-skills` to install `volcengine-db-supabase`, then resume in a new thread. Return with `DATABASE_URL` and any engine-specific AIDAP/Supabase values such as `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and server-only `SUPABASE_SERVICE_ROLE_KEY` wired into the deploy env/Secret path.

### SQL Server
**Detection keywords**:
- `mssql`, `sqlserver`, `tedious`, `pyodbc`, `SQLSERVER_HOST`, `MSSQL_HOST`, `1433`, `sqlserver://`, `jdbc:sqlserver`
- `image: mcr.microsoft.com/mssql/server` or `image: *sqlserver*` in `docker-compose.yml`

**Volcengine product/engine**: `database_product=rds`, `database_engine=sqlserver`

**Volcengine service**: RDS SQL Server (`ve rdsmssql`)

**Recommended spec**:
- Instance type: Basic or HA according to workload and current regional availability.
- Version/spec must be selected from current `ve rdsmssql` help or describe APIs; do not invent defaults.

**Wiring**:
- Use the private endpoint and app login credentials to assemble the SQL Server connection string.
- Add the ECS/VKE subnet CIDR or security group source to the SQL Server allowlist.
- Treat creation and deletion as slower than stateless resources; poll instance state before database/account follow-up operations.

---

### Redis
**Detection keywords**:
- `redis`, `ioredis`, `redis-py`, `REDIS_HOST`, `REDIS_URL`, `6379`, `redis://`
- `image: redis` in `docker-compose.yml`

**Volcengine service**: Redis (`ve redis`)

**Recommended spec**:
- Type: primary-replica
- Spec: 1GB memory
- Version: Redis 6.0

**Creation example**:
```bash
ve redis CreateDBInstance --body '{
  "InstanceName": "deploy-<repo>-redis",
  "RegionId": "<region>",
  "ConfigureNodes": [{"AZ": "<zone-id>"}],
  "ShardedCluster": 0,
  "NodeNumber": 2,
  "ShardCapacity": 1024,
  "ShardNumber": 1,
  "EngineVersion": "6.0",
  "SubnetId": "<subnet-id>",
  "VpcId": "<vpc-id>",
  "Password": "<auto-generated>",
  "Tags": [
    {"Key": "project", "Value": "<repo>"},
    {"Key": "publish-by", "Value": "deploy-skill"}
  ]
}'
```

**Wiring**:
- Assemble `REDIS_URL` from the private endpoint and app account/password
- Add the ECS/VKE subnet CIDR or security group source to the allowlist
- Run a connectivity check from the app runtime environment first, then a public health check

---

### MongoDB
**Detection keywords**:
- `mongodb`, `mongoose`, `pymongo`, `mongoclient`, `MONGO_URI`, `MONGODB_URL`, `27017`, `mongodb://`
- `image: mongo` in `docker-compose.yml`

**Volcengine service**: MongoDB (`ve mongodb`)

**Recommended spec**:
- Type: replica set
- Spec: `mongo.2c4g` (2 vCPU / 4 GB)
- Storage: 20GB
- Version: MongoDB 5.0

---

### Kafka
**Detection keywords**:
- `kafka`, `kafkajs`, `kafka-python`, `confluent-kafka`, `KAFKA_BROKERS`, `KAFKA_BOOTSTRAP_SERVERS`, `9092`
- `image: *kafka*` in `docker-compose.yml`

**Volcengine service**: Kafka (`ve kafka`)

**Recommended spec**:
- Version: 2.8
- Spec: `kafka.20xrate.hw` (entry level)
- Storage: 100GB
- Partitions: per topic configuration

---

### RabbitMQ
**Detection keywords**:
- `rabbitmq`, `amqplib`, `amqp`, `pika`, `RABBITMQ_HOST`, `AMQP_URL`, `5672`, `amqp://`
- `image: rabbitmq` in `docker-compose.yml`

**Volcengine service**: no managed service

**Deployment**: deploy the official Docker image in the VKE cluster

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
spec:
  serviceName: rabbitmq
  replicas: 1
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management-alpine
        ports:
        - containerPort: 5672
          name: amqp
        - containerPort: 15672
          name: management
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: password
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
        volumeMounts:
        - name: data
          mountPath: /var/lib/rabbitmq
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
spec:
  selector:
    app: rabbitmq
  ports:
  - port: 5672
    name: amqp
  - port: 15672
    name: management
```

---

### TOS (object storage)
**Detection keywords**:
- `@volcengine/tos`, `tos-sdk`, `TOS_ENDPOINT`, `TOS_BUCKET`, `tos.volces.com`
- code references an S3-compatible API with the endpoint pointing at Volcengine

**Volcengine service**: TOS (`tosutil` / Terraform IaC)

The current `ve` CLI build may not have a `tos` service; do not generate `ve tos` commands. When object transfer is needed, prefer the standalone `volcengine-tosutil` skill or create the bucket with Terraform/IaC. In `volcengine-deploy`, `tosutil` can only be an optional capability, and you must keep SSH/scp or a user-provided artifact URL as a fallback.

```bash
tosutil mb tos://deploy-<repo>-assets -acl=private -sc=STANDARD
tosutil cp ./dist/app.tar.gz tos://deploy-<repo>-assets/artifacts/app.tar.gz
tosutil presign tos://deploy-<repo>-assets/artifacts/app.tar.gz -vp=15min
```

---

## Generic dependency handling (not in the list above)

For other service dependencies (e.g. Elasticsearch, MinIO, Memcached), use this strategy:

1. Deploy the official Docker image as a **StatefulSet** in the VKE cluster
2. Persist data with a **PVC**
3. Expose it to the app via a **ClusterIP Service**

```yaml
# Generic template
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: <dependency-name>
spec:
  serviceName: <dependency-name>
  replicas: 1
  selector:
    matchLabels:
      app: <dependency-name>
  template:
    metadata:
      labels:
        app: <dependency-name>
    spec:
      containers:
      - name: <dependency-name>
        image: <official-docker-image>
        ports:
        - containerPort: <port>
        resources:
          requests:
            cpu: 250m
            memory: 256Mi
          limits:
            cpu: "1"
            memory: 1Gi
        volumeMounts:
        - name: data
          mountPath: <data-path>
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```
