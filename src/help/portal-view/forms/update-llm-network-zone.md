# Update Network Zone

Use `/app/form/updateLlmNetworkZone` to revise a private-provider outbound
allowlist. Host Id, Network Zone Id, and Aggregate
Version are read-only.

Editable fields have the same meaning as the Create form: Zone Name, allowed
DNS names, CIDRs, ports, and private TLS/plaintext flags. Choose **Apply** after
changing a structured array.

Changing a Zone does not rewrite a running gateway snapshot. Review every
Endpoint that references the Zone, publish a new candidate, and verify private
connectivity.

The hosted NVIDIA endpoint uses `PUBLIC_TLS` and should not reference a Network
Zone. Do not repurpose or delete an unrelated private Zone merely to configure
the NVIDIA demo.
