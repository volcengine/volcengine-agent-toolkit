# Volcenginecc IAM SAML Provider Example

Verified example path:

```text
assets/examples/volcenginecc-iam-saml-provider/main.tf
```

Use this example when a deployment needs an IAM SAML provider for enterprise SSO. The example accepts base64-encoded SAML metadata as an input variable so private keys and generated certificates are not committed to the skill.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_iam_saml_provider` | SAML identity provider metadata for IAM SSO |

## Verified command sequence

The resource was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-iam-saml-provider
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_encoded_saml_metadata_document="$(base64 < idp-metadata.xml | tr -d '\n')"
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform apply
terraform plan -detailed-exitcode -input=false
terraform destroy
```

Observed apply result: SAML provider created successfully from a minimal IdP metadata document containing a self-signed public certificate. A follow-up plan returned `No changes`. Destroy removed the SAML provider and final state was empty.

Observed ID in the verification account:

```text
saml_provider_name = cc-iac-saml
```

## Pitfalls found during verification

1. The Terraform resource expects the entire SAML metadata XML base64-encoded. Do not pass a raw certificate or raw XML string.

2. The metadata should contain the IdP public signing certificate only. Do not commit private keys. During verification, the private key was generated only in `/tmp` to create a disposable self-signed certificate and was deleted with the temporary directory.

3. A minimal working metadata shape is:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="https://cc-iac-saml.example/idp">
  <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:KeyDescriptor use="signing">
      <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:X509Data>
          <ds:X509Certificate>BASE64_PUBLIC_CERT_BODY_WITHOUT_PEM_MARKERS</ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </md:KeyDescriptor>
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="https://cc-iac-saml.example/sso"/>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>
```

4. `sso_type = 1` was verified for role SSO. Re-test `sso_type = 2` and `status` before using this resource for user SSO.

5. SAML provider names are account-scoped enough to collide during repeated tests. Change `saml_provider_name` or import the existing provider before applying in a shared account.

## Import IDs

```bash
terraform import volcenginecc_iam_saml_provider.main <saml-provider-name>
```
