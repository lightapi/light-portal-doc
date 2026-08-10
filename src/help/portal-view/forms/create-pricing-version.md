# Create Pricing Version

Use this form to add an approved, effective-dated rate schedule for one
Provider Deployment and operation. Pricing is separate from Deployment and
Credential identity so rate changes remain versioned and auditable.

Rates use integer micros per one million tokens. One currency unit is
`1,000,000` micros.

## Fields

| Field | Required | Description |
| --- | --- | --- |
| Host Id | Yes | Read-only tenant boundary. |
| Provider Deployment | Yes | Deployment whose operation is being priced. |
| Operation | Yes | `generate` or `embed`; it must match the Deployment protocol. |
| Pricing Version | Yes | Positive business version unique for the Deployment. |
| Pricing Basis | Yes | `EXTERNAL_PROVIDER`, `ZERO_MARGINAL`, or `AMORTIZED_INTERNAL`. |
| Input Micros Per Million Tokens | Yes | Non-negative input/embedding token rate. |
| Output Micros Per Million Tokens | For `generate` only | Required for generation and prohibited for `embed`. |
| Cached Input Micros Per Million Tokens | No | Optional cached-input rate. |
| Effective Time | Yes | ISO-8601 timestamp with timezone. |
| Expiration Time | No | Optional cutoff later than Effective Time. |
| Pricing Source | Yes | Reference to the contract, provider page, or approved demo assumption. |
| Approved By | Yes | Person, group, or automation identity approving the rate. |

Pricing-basis rules are:

- `EXTERNAL_PROVIDER` records a provider charge and may use zero only when the
  approved external rate is actually zero;
- `ZERO_MARGINAL` requires all supplied rates to be zero; and
- `AMORTIZED_INTERNAL` requires at least one non-zero rate.

## NVIDIA free endpoint example

For a free-demo entitlement with no marginal token charge, select the NVIDIA
Nemotron Deployment and use:

```json
{
  "operation": "embed",
  "pricingVersion": 1,
  "pricingBasis": "ZERO_MARGINAL",
  "inputMicrosPerMillion": 0,
  "cachedInputMicrosPerMillion": 0,
  "effectiveTs": "2026-08-10T00:00:00Z",
  "expiresTs": null,
  "source": "nvidia-build-free-endpoint-demo",
  "approvedBy": "local-demo-operator"
}
```

Leave Output Micros Per Million Tokens empty. Do not enter `0` in that field:
the embedding contract requires it to be omitted/null.

Verify the current NVIDIA account terms before using `ZERO_MARGINAL`. If the
account is billed or quota usage must carry a monetary rate, choose
`EXTERNAL_PROVIDER` and enter the approved input price instead. A free endpoint
can still have capacity and rate limits even when its marginal price is zero.

The system does not automatically close an older Pricing Version or reject all
overlapping windows. Use a new version for a new rate period and publish a new
gateway candidate. Portal generates Pricing Version Id and Aggregate Version;
`active` remains backend-managed.
