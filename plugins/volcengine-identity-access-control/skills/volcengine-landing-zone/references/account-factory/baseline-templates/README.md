# Baseline package templates

Minimal, `terraform validate`-clean skeletons for authoring a custom baseline
package. Pick exactly one at authoring time — do not add an `enable_assume_role`
toggle or a `dynamic "assume_role"` block, so the package stays free of runtime
conditional logic.

- [`member-account/`](member-account/) — **Template A.** Target is a newly created
  member account. Provider carries `assume_role` into the member account's
  `OrganizationAccessControlRole`; every resource pins the `member` alias. Copy
  the built-in `network-cross-account-connectivity` package as the fuller working
  reference.
- [`management-account/`](management-account/) — **Template B.** Target is the
  current management account. Bare default provider (region only, no
  `assume_role`); resources need no `provider =` line.

Selection rule: **new member account → Template A; current management account →
Template B.** Cross-account execution rules live in the setup guidebook's
"Cross-account execution model".
