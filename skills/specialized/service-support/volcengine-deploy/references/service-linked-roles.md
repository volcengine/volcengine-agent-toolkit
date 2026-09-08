# Deployment Service-Linked Roles

Use this reference when Volcengine deployment or managed dependency creation fails with a missing `ServiceRoleFor...`
role, or when preflighting account readiness for common deployment resources.

## Repair Rule

Do not derive `ServiceName` from `RoleName` by string conversion. Volcengine service names can be lowercase, uppercase,
mixed case, or underscore-delimited. Use the product-specific mapping below only where it matches the failing product,
then confirm the template exists before creating the role:

```bash
ve iam GetServiceLinkedRoleTemplate --ServiceName <service-name>
ve iam CreateServiceLinkedRole --ServiceName <service-name>
ve iam GetRole --RoleName <role-name>
```

Treat `RoleAlreadyExists` as already authorized. After `GetRole` confirms `IsServiceLinkedRole=1` and the trust
principal matches the expected service, retry the original product action once. If template lookup or creation is
denied, fall back to the product console authorization flow or ask the user for an account with IAM permission.

## Evidence And Scope

The mappings below come from IAM service-linked role API evidence: role list/get responses where `IsServiceLinkedRole=1`
and the trust policy `Principal.Service` contains the listed service principal. Account-specific fields such as account
IDs, RoleIds, TRNs, create timestamps, and update timestamps are intentionally omitted.

Use this table as a dispatch map for common deployment dependencies. Before creating a role, still call
`ve iam GetServiceLinkedRoleTemplate --ServiceName <service-name>`; the template result is the current authority for
whether that service-linked role can be created in the target account.

## Common Deployment Mappings

| Deployment surface                  | RoleName                       | `CreateServiceLinkedRole --ServiceName` | Check when                                                               |
|-------------------------------------|--------------------------------|-----------------------------------------|--------------------------------------------------------------------------|
| AIDAP Supabase/PostgreSQL workspace | `ServiceRoleForAIDAP`          | `aidap`                                 | Before or after the first `CreateWorkspace` failure                      |
| RDS MySQL                           | `ServiceRoleForRDSMySQL`       | `rds_mysql`                             | Before managed MySQL instance creation or cross-service operations       |
| RDS PostgreSQL                      | `ServiceRoleForRDSPG`          | `rds_postgresql`                        | Before managed PostgreSQL instance creation or cross-service operations  |
| RDS SQL Server                      | `ServiceRoleForRDSMSSQL`       | `rds_mssql`                             | Before managed SQL Server instance creation or cross-service operations  |
| Redis                               | `ServiceRoleForRedis`          | `Redis`                                 | Before Redis instance creation or public endpoint/subnet operations      |
| MongoDB                             | `ServiceRoleForMongoDB`        | `mongodb`                               | Before MongoDB instance creation                                         |
| Kafka                               | `ServiceRoleForKafka`          | `Kafka`                                 | Before Kafka instance creation                                           |
| RocketMQ                            | `ServiceRoleForRocketMQ`       | `RocketMQ`                              | Before RocketMQ instance creation                                        |
| RabbitMQ                            | `ServiceRoleForRabbitMQ`       | `RabbitMQ`                              | Before managed RabbitMQ creation when available; otherwise deploy in VKE |
| BMQ                                 | `ServiceRoleForBmq`            | `bmq`                                   | Before BMQ instance creation                                             |
| VKE                                 | `ServiceRoleForVKE`            | `vke`                                   | Before cluster or managed add-on operations                              |
| Container Registry                  | `ServiceRoleForCR`             | `cr`                                    | Before registry operations that access other services such as TOS        |
| veFaaS                              | `ServiceRoleForVeFaaS`         | `vefaas`                                | Before function deployment or service-managed integration                |
| API Gateway                         | `ServiceRoleForApig`           | `apig`                                  | Before API Gateway creation/integration                                  |
| CLB                                 | `ServiceRoleForLoadBalancer`   | `clb`                                   | Before CLB creation or listener operations                               |
| CLB log delivery                    | `ServiceRoleForClbLogDelivery` | `clblogdelivery`                        | Before CLB log delivery integrations                                     |
| ALB                                 | `ServiceRoleForALB`            | `alb`                                   | Before ALB creation or public/private type changes                       |
| NAT Gateway                         | `ServiceRoleForNatGateway`     | `natgateway`                            | Before NAT Gateway creation                                              |
| PrivateLink                         | `ServiceRoleForPrivateLink`    | `privatelink`                           | Before PrivateLink endpoint/service operations                           |
| PrivateZone                         | `ServiceRoleForPrivateZone`    | `private_zone`                          | Before resolver endpoint or PrivateZone integrations                     |
| Transit Router                      | `ServiceRoleForTransitRouter`  | `transitrouter`                         | Before TR attachment creation                                            |
| TLS                                 | `ServiceRoleForTLS`            | `TLS`                                   | Before log service integrations such as log delivery                     |
| CloudMonitor                        | `ServiceRoleForCM`             | `cloudmonitor`                          | Before CloudMonitor integrations                                         |
| VolcObserve                         | `ServiceRoleForVolcObserve`    | `Volc_Observe`                          | Before CloudMonitor/observability paths that require this role           |
| VMP                                 | `ServiceRoleForVMP`            | `vmp`                                   | Before managed Prometheus workspace or scrape integration                |
| APMPlus                             | `ServiceRoleForAPMPlusServer`  | `apmplus_server`                        | Before APMPlus server-side integration                                   |
| KMS                                 | `ServiceRoleForKMS`            | `kms`                                   | Before KMS integrations                                                  |
| MetaKMS                             | `ServiceRoleForMetaKMS`        | `metakms`                               | Before MetaKMS integrations                                              |

## Placement

Keep product-specific repair details in the product skill when the failure is verified there. For example, AIDAP
`CreateWorkspace` handling belongs in `volcengine-db-supabase`, PrivateZone resolver handling belongs in
`volcengine-iac`, and Transit Router setup belongs in `volcengine-landing-zone`. Use this file as a deployment preflight
and dispatch map, not as a replacement for product-specific procedures.
