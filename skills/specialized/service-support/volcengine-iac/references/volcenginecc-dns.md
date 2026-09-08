# Volcenginecc DNS Example

Verified example path:

```text
assets/examples/volcenginecc-dns/main.tf
```

Use this example when a Volcengine deployment needs Terraform-managed public Cloud DNS zones for application domains, CDN/WAF CNAME targets, or delegated subdomains.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_dns_zone` | Public DNS zone that receives Volcengine name servers and can later host records |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-dns
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy
```

Observed apply result: one DNS zone was created for `cc-iac-dns-0530043107.com`, returning `zid = <zone-id>` and name servers `ns1.volcengine-dns.com` / `ns2.volcengine-dns.com`. Follow-up plan returned `No changes`. Destroy removed the zone and final state was empty.

## Pitfalls found during verification

1. `zone_name` must be a syntactically valid public domain. Using the reserved `.invalid` TLD failed with `ErrParamInvalid: validation fail: params:[ZoneName]`.

2. Creating a subdomain under an existing parent domain can require domain ownership verification before create. `cc-iac-dns.example.com` failed with `ErrSubDomainMustVerify: create a subdomain must verification`.

3. A unique apex domain can be created even before DNS delegation is correct. The verified zone read back `stage = 3` and `is_ns_correct = false` because the domain was not delegated to the allocated Volcengine name servers. This is acceptable for IaC shape validation but not for production traffic.

4. Keep `tags` fully specified with both `key` and `value`. Generated docs sometimes show partial tag objects, which can cause set comparison instability.

5. For production, replace the example `zone_name` default with a domain owned by the account or delegate the parent domain first. Do not rely on DNS resolution until the registrar NS records match `allocate_dns_server_list`.

## Import ID

```bash
terraform import volcenginecc_dns_zone.main <zid>
```
