# Validate LLM Embeddings Through The Live Gateway

Use this workflow after authoring the LLM records in Portal. Validation is an
ordinary, authenticated request to the selected live `light-gateway` replica;
it is not a provider test performed by Portal.

The NVIDIA demo validates the public Aliases `kb-query` and `kb-index`, backed
by `nvidia/nemotron-3-embed-1b`, against the declared 2048-dimensional
embedding space.

## What This Validation Does

The checked helper sends curl requests to the gateway's Alias discovery and
embeddings APIs. The gateway selects the active Route, resolves its provider
credential locally, calls the provider, and returns bounded response metadata.

The validation:

- does not ask Portal for a provider API key or gateway bearer token;
- does not send provider credentials through helper arguments;
- does not call a provider endpoint directly;
- does not store a vector, raw provider body, or gateway credential;
- does not mutate Portal authoring records, publications, Aliases, or
  Deployments; and
- does not claim that every Deployment behind an Alias is healthy.

An Alias may succeed by using a fallback Route. A successful Alias probe proves
only that one normal routed request completed with the expected embedding
contract.

## Operator Workflow

### 1. Publish the configuration

In the LLM Model Control Plane **Publication** tab, select the environment and
gateway instance. Choose **Generate from active records**, review the preview,
and choose **Publish to instance**. Create and promote the corresponding config
snapshot, then restart or explicitly reload the selected gateway as required by
your deployment.

Portal publication history confirms the configuration application to the
selected instance. It is not proof that a particular running replica loaded the
revision.

### 2. Confirm the selected replica applied it

Before sending a billable model request, confirm that the replica reports an
`ACKNOWLEDGED` row for the intended publication ID, sequence, and root digest.
Operators with database access can use:

```sql
SELECT gateway_publication_id,
       gateway_instance,
       acknowledgement_state,
       sequence_id,
       root_digest,
       material_generation,
       applied_at
  FROM llm_gateway_publication_ack_t
 WHERE host_id = :host_id
   AND environment = :environment
   AND gateway_publication_id = :gateway_publication_id
   AND gateway_instance = :gateway_instance;
```

Use the equivalent acknowledgement view provided by your operations platform
when direct database access is unavailable. Stop if the row is absent or its
state is `PENDING`, `FAILED`, or `DIVERGENT`. Alias discovery alone is not proof
of the intended revision because an older snapshot can expose the same Alias.

### 3. Provision the provider key only on the gateway

Provision the NVIDIA credential through the selected gateway deployment's
protected environment or secret-injection mechanism, then restart or reload
that replica. The published credential record contains only the external secret
reference.

Do not enter the provider value into Portal, a helper argument, a request file,
a ticket, or a validation report. For the local demo, follow the deployment
instructions in `all-in-lt/llm-gateway-rust/NVIDIA-DEMO.md` from
`portal-config-loc`.

### 4. Prepare the gateway client credential

Run the helper from a network location authorized to call the gateway. Create
a protected curl header file containing the caller's normal gateway bearer
token:

```bash
set -euo pipefail
umask 077

gateway_header_file=$(mktemp)
trap 'rm -f -- "$gateway_header_file"' EXIT
read -rsp 'Gateway client bearer token: ' gateway_client_token
printf '\n'
printf 'Authorization: Bearer %s\n' "$gateway_client_token" >"$gateway_header_file"
unset gateway_client_token
chmod 600 "$gateway_header_file"
```

The token is not echoed and does not appear in curl's process arguments. This
is a gateway caller credential, not the NVIDIA provider credential.

### 5. Run the checked curl helper

From `portal-config-loc/all-in-lt/llm-gateway-rust`, validate the query lane:

```bash
validation/validate-embedding.sh \
  --gateway-url https://localhost:8444 \
  --alias kb-query \
  --header-file "$gateway_header_file" \
  --ca-file config/ca.pem \
  --expected-space-id nvidia-nemotron-3-embed-1b \
  --expected-space-revision 1 \
  --expected-dimension 2048 \
  --timeout-seconds 30
```

Validate the indexing lane independently by changing only the Alias:

```bash
validation/validate-embedding.sh \
  --gateway-url https://localhost:8444 \
  --alias kb-index \
  --header-file "$gateway_header_file" \
  --ca-file config/ca.pem \
  --expected-space-id nvidia-nemotron-3-embed-1b \
  --expected-space-revision 1 \
  --expected-dimension 2048 \
  --timeout-seconds 30
```

For a publicly trusted production gateway, omit `--ca-file` and use the system
trust store. Never disable certificate verification or follow redirects. The
gateway URL must be the selected gateway origin, not a provider URL.

A passing helper emits one bounded report:

```json
{
  "schemaVersion": "lightapi.llm.embedding-validation/v1",
  "status": "pass",
  "category": "validated",
  "alias": "kb-query",
  "requestId": "example-request-id",
  "httpStatus": 200,
  "contract": {
    "expected": {"spaceId": "nvidia-nemotron-3-embed-1b", "spaceRevision": 1, "dimension": 2048},
    "actual": {"spaceId": "nvidia-nemotron-3-embed-1b", "spaceRevision": 1, "dimension": 2048}
  },
  "vectorCount": 1,
  "configGeneration": 1,
  "billedCostMicros": 0
}
```

The real request ID and billed cost vary. The helper never prints the vector.
The embeddings request traverses normal gateway authentication, authorization,
audit, quota, routing, and billing. Treat it as a normally audited and
potentially billable provider request.

## Optional Rust validator

When the `light-gateway` executable is available, its checked Rust wrapper can
validate embeddings or a fixed, one-token generation request. It is a client of
the already-running gateway; it does not load another snapshot or start another
gateway server.

The embedding command uses the same protected header file and contract as the
shell helper:

```bash
light-gateway validate-llm-live \
  --gateway-url https://localhost:8444 \
  --operation embeddings \
  --alias kb-query \
  --header-file "$gateway_header_file" \
  --ca-file config/ca.pem \
  --timeout-seconds 30 \
  --expected-space-id nvidia-nemotron-3-embed-1b \
  --expected-space-revision 1 \
  --expected-dimension 2048
```

To validate generation, select one public Alias and one supported operation:

```bash
light-gateway validate-llm-live \
  --gateway-url https://localhost:8444 \
  --operation chat-completions \
  --alias public-chat-alias \
  --header-file "$gateway_header_file" \
  --ca-file config/ca.pem \
  --timeout-seconds 30

light-gateway validate-llm-live \
  --gateway-url https://localhost:8444 \
  --operation responses \
  --alias public-responses-alias \
  --header-file "$gateway_header_file" \
  --ca-file config/ca.pem \
  --timeout-seconds 30
```

Each generation validation sends exactly one ordinary, non-streaming Alias request
with the fixed text `Reply with OK.` and a one-token output limit. The
command does not accept arbitrary model input and does not enumerate Routes,
probe fallback Deployments, disconnect streams, test capacity, or call a
provider directly.

JSON is the default output. Add `--output text` for a bounded rendering derived
from the same report structure. Neither renderer includes generated text,
embedding vectors, raw error bodies, or credentials. The request remains
normally authorized, audited, quota-accounted, and potentially billable.

The Rust command is additive. The curl workflow and shell helper remain the
portable, required operator interfaces.

### 6. Correct, republish, and repeat

Use the report's `category`, `requestId`, and `configGeneration` to identify the
corrective action below. Change the responsible Portal record or gateway-local
state, publish a new revision when configuration changed, confirm the selected
replica acknowledgement, and repeat the same probe.

Retain only the bounded report when operational policy requires evidence. Do
not retain the bearer header file, raw response, provider response, API key,
request body, or embedding values.

## Troubleshooting

| Condition or report category | What it distinguishes | Corrective action |
| --- | --- | --- |
| Publication acknowledgement absent, `PENDING`, `FAILED`, or `DIVERGENT` | **Publication not applied** to the selected replica. This is different from an Alias lookup failure. | Correct snapshot promotion, replica selection, digest divergence, or reload failure. Wait for `ACKNOWLEDGED` before probing. |
| `gatewayAuthorization` | **Caller denied by gateway policy** (`401` or `403`); this is not provider authentication. | Obtain a valid gateway caller token and confirm the caller is authorized for Alias discovery and `/v1/embeddings`. Use the request ID in gateway audit records. |
| `aliasNotVisible` | **Alias missing from the active snapshot**, although the replica is reachable. | Confirm the Alias and at least one compatible Route are active in the target environment, republish, promote the snapshot, reload, and confirm acknowledgement. |
| `gatewayError` with gateway `service_unavailable` | **Gateway credential materialization failure, configuration failure, audit failure, or endpoint availability failure.** | Use the request ID and sanitized gateway diagnostics to identify the unavailable subsystem. Verify that external secret references match credentials injected into the gateway, then restart or reload when appropriate. Never copy the value into Portal. |
| `providerError` after credential materialization | **Provider rejection**, including an invalid/revoked credential, physical model, base URL, or provider protocol. | Use the request ID and sanitized gateway diagnostics to identify the rejected setting. Correct the gateway credential or Portal endpoint/deployment record, republish if configuration changed, and retry. |
| `providerRateLimited` | **Provider rate limit**. | Wait for the provider retry window or correct account quota/capacity. Retry without changing Portal records unless the configured account or Route must change. |
| `providerTimeout` or `transport` | **Provider/gateway timeout or network/TLS failure**. | Check gateway reachability, trusted CA, DNS, egress policy, provider availability, and configured timeouts. Keep TLS verification enabled. |
| `embeddingContract` with different space ID, revision, or dimension | **Embedding-space mismatch**. Mixing these vectors would corrupt retrieval behavior. | Stop indexing/querying. Align the Alias, Registration, Deployment, and knowledge-base embedding-space contract, republish, and create a new index generation when required. |
| `embeddingContract` with missing/malformed data or success headers | **Invalid provider response** or incompatible adapter mapping. | Verify provider protocol and physical model, inspect sanitized gateway diagnostics by request ID, correct the Endpoint or Deployment, republish, and retry. |
| `gatewayError` | Another bounded gateway failure that is not safely classified by the helper. | Look up the request ID in gateway logs/audit data, correct the reported local or configuration condition, and retry. Do not attach the raw response to a ticket. |
| `protectedHeaderFile`, `caFile`, or `localDependency` | Local validation setup is incomplete or unsafe. | Install the named dependency or recreate the protected file with the documented ownership and mode. Do not weaken the file or TLS checks. |

If an Alias has multiple Routes, validate each physical Deployment separately
only through an explicitly authorized operational procedure that can control
routing. Repeating this ordinary Alias probe cannot establish that every
fallback Deployment works.
