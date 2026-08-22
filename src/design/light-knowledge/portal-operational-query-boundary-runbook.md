# Light Knowledge Operational Boundary Runbook

This runbook operates the post-cutover boundary: Config Server owns Knowledge
control-plane state, while the Light Knowledge database owns operational state.
Portal reads operational state only through the private `light-knowledge-admin`
API. After physical separation, an incident response must not fall back to a
Config Server operational mirror.

## Tenant/environment rollout

1. Create an isolated deployment cell containing the exact Portal query,
   `light-knowledge`, `light-knowledge-admin`, and worker versions being
   qualified.
2. Update the ingress or release-routing artifact so only the declared
   tenant/environment allowlist reaches that cell. Store its identity in
   `allowlist.enforcementArtifact`; an empty value cannot qualify.
3. Keep non-allowlisted traffic on a separate previously qualified cell. There
   is deliberately no per-request JDBC or legacy-authority branch inside
   `genai-query`.
4. Expand with another immutable routing/release artifact only after latency,
   availability, denial, redaction, acknowledgement-lag, and pool checks pass.
5. Roll back by routing the allowlist to the prior qualified service cell; do
   not re-enable the removed Config Server operational reads.

## Administration API outage

1. Confirm retrieval traffic on `light-knowledge` is healthy independently of
   the administration listener and pool.
2. Check `light-knowledge-admin` availability, request latency, circuit-open
   count, database-pool utilization, and JWT denial outcomes.
3. Keep Portal desired state, aggregate version, and projection state visible.
   Operational fields must report `UNAVAILABLE`; do not fabricate empty rows.
4. Roll back only to a previously qualified, API-compatible service image. Do
   not enable the removed JDBC path.
5. Record start, recovery, affected tenant/environment allowlists, and SLO
   impact in the Phase 7 daily evidence.

## Stale or rejected control snapshot

1. Read the active snapshot ID, applied watermark, signature key ID, rejection
   reason, and acknowledgement lag from each Knowledge deployment.
2. Stop rollout expansion. Keep the last-known-good snapshot active; never
   partially activate a rejected snapshot.
3. Compare the rejected publication with the Config Server snapshot manifest,
   tombstone set, host/environment scope, and monotonic version.
4. Correct and republish through Config Server. Do not write replica tables
   manually. Confirm all replicas acknowledge the replacement snapshot before
   resuming rollout.

## Database restore

1. Select a compatible evidence set containing the Config Server snapshot ID,
   Config Server backup SHA-256, Knowledge checkpoint, Knowledge backup SHA-256,
   and object-manifest SHA-256.
2. Stop Knowledge workers and snapshot application. Restore Config Server and
   Knowledge into separate databases from their independent artifacts.
3. Restore or verify object storage against the recorded manifest before
   starting workers.
4. Start snapshot application, then `light-knowledge-admin`, retrieval API, and
   workers. Confirm snapshot/checkpoint compatibility and promotion receipts.
5. Run the two-database ownership, authorization, retrieval, and administration
   smoke tests before reopening the tenant allowlist.

## Credential rotation

1. Rotate the private snapshot-signing key with an overlap that allows the old
   and new verification key IDs. Publish and acknowledge a snapshot signed by
   the new key before retiring the old key.
2. Rotate Config Server, Portal, and each Knowledge database login separately.
   Preserve database-scoped grants and network isolation.
3. Restart one replica at a time. Confirm JWT verification, delegated user-token
   forwarding, pool health, and zero cross-database connectivity.
4. Remove the previous secret only after every replica reports the new key or
   credential version.

## Service rollback

1. Freeze allowlist expansion and record current service versions, snapshot ID,
   Knowledge checkpoint, and object-manifest digest.
2. Select versions compatible with the active administration API and snapshot
   schema. Roll back admin, retrieval, and worker replicas independently where
   possible.
3. Verify Portal displays desired state during the rollback and that operational
   errors are explicit. The rollback must not fall back to a Config Server
   operational mirror.
4. Resume only after denial, redaction, acknowledgement-lag, latency, and pool
   checks pass.

## Retained-table cleanup

1. Complete seven consecutive UTC qualification windows with zero authorization
   scope mismatch and all declared Portal and Knowledge SLOs met.
2. Complete one declared rollback and backup cycle, including an independent
   restore exercise and service rollback without the stale operational mirror.
3. Store the completed evidence JSON and backup artifacts outside the source
   tree. Run the Phase 7 qualification gate and retain its SHA-256 output.
4. Set the exact cleanup confirmation and run the guarded cleanup command
   against an explicit Config Server URL. It prints the captured relation counts
   before dropping only `knowledge_rollback_evidence`.
5. Re-run the Config Server control-only schema gate and archive the operator
   transcript with the qualification evidence.
