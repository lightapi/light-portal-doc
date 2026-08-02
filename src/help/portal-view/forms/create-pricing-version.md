# Create Pricing Version

Use this form to add an approved, effective-dated rate schedule for a Provider
Deployment. Pricing Versions are separate from Deployments so rate changes can
be reviewed, audited, and published without changing provider endpoint or
credential configuration.

Rates use integer **micros per one million tokens**. One unit of currency is
`1,000,000` micros. For example, `$2.50` per million tokens is entered as
`2500000`, not `2.5`.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. The selected Deployment must belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Provider Deployment | Active provider endpoint to which this rate schedule applies. | `openai-prod-ca` (`30000000-0000-4000-8000-000000000030`) |
| Pricing Version | Positive operator-assigned sequence for this Deployment's pricing. It is business versioning, distinct from Aggregate Version. The Deployment and Pricing Version pair must be unique. | `3` |
| Input Micros Per Million Tokens | Non-negative charge for one million non-cached input tokens. `$2.50` is `2500000` micros. | `2500000` |
| Output Micros Per Million Tokens | Non-negative charge for one million generated output tokens. `$10.00` is `10000000` micros. | `10000000` |
| Cached Input Micros Per Million Tokens | Optional non-negative cached-input rate. The control plane retains it, but the current MVP gateway projection does not consume it separately. | `1250000` |
| Effective Time | ISO 8601 timestamp at which the rate becomes eligible for use and publication. | `2026-08-01T12:00:00Z` |
| Expiration Time | Optional ISO 8601 end of the pricing window. It must be later than Effective Time. Leave it empty for an open-ended rate. | `2026-11-01T12:00:00Z` |
| Pricing Source | Bounded reference describing where the approved numbers came from, such as a provider contract, price sheet, or internal agreement. | `provider-contract-2026-08` |
| Approved By | Person, group, or approval identity responsible for authorizing this rate. | `finops@example.com` |

## Example

```json
{
  "providerDeploymentId": "30000000-0000-4000-8000-000000000030",
  "pricingVersion": 3,
  "inputMicrosPerMillion": 2500000,
  "outputMicrosPerMillion": 10000000,
  "cachedInputMicrosPerMillion": 1250000,
  "effectiveTs": "2026-08-01T12:00:00Z",
  "expiresTs": "2026-11-01T12:00:00Z",
  "source": "provider-contract-2026-08",
  "approvedBy": "finops@example.com"
}
```

The system does not automatically close an older Pricing Version or reject
overlapping effective windows. Before creating the record, review existing
Pricing entries for the Deployment and choose a unique version and an
unambiguous time window.

Creating the record makes the price available to control-plane validation; it
does not immediately change a running gateway. The rate reaches the gateway
only through a valid new publication. The backend generates the Pricing
Version Id and Aggregate Version. The `active` state is backend-managed through
soft delete and is not part of this form.
