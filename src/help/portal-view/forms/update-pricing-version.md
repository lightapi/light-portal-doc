# Update Pricing Version

Use this form to correct an existing Pricing Version's Deployment, rates,
effective window, or approval metadata. A change reaches a gateway only after
a valid new publication is created and applied.

For a genuinely new provider rate period, prefer creating a new Pricing Version
instead of rewriting a historical rate that may already be referenced by
published configuration or usage evidence.

The **Host Id**, **Pricing Version Id**, and **Aggregate Version** are read-only.
Aggregate Version provides optimistic concurrency protection; it is different
from the operator-assigned **Pricing Version**.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. | `10000000-0000-4000-8000-000000000001` |
| Pricing Version Id | Read-only identifier generated when this Pricing record was created. | `50000000-0000-4000-8000-000000000050` |
| Provider Deployment | Deployment to which this rate schedule applies. | `openai-prod-ca` (`30000000-0000-4000-8000-000000000030`) |
| Pricing Version | Positive business version unique for the selected Deployment. It is not the optimistic-concurrency version. | `3` |
| Input Micros Per Million Tokens | Non-negative input rate in micros per one million tokens. | `2500000` |
| Output Micros Per Million Tokens | Non-negative output rate in micros per one million tokens. | `10000000` |
| Cached Input Micros Per Million Tokens | Optional cached-input rate retained by the control plane. The current MVP gateway projection does not consume it separately. | `1250000` |
| Effective Time | ISO 8601 timestamp when the rate becomes effective. | `2026-08-01T12:00:00Z` |
| Expiration Time | Optional ISO 8601 timestamp later than Effective Time. Leave empty for no scheduled expiration. | `2026-11-01T12:00:00Z` |
| Pricing Source | Reference to the contract, price sheet, or agreement supporting the rate. | `provider-contract-2026-08-rev1` |
| Approved By | Identity that approved the corrected record. | `finops@example.com` |
| Aggregate Version | Read-only record version included with the update command. Reload the record if another update has advanced it. | `4` |

## Example

```json
{
  "pricingVersionId": "50000000-0000-4000-8000-000000000050",
  "providerDeploymentId": "30000000-0000-4000-8000-000000000030",
  "pricingVersion": 3,
  "inputMicrosPerMillion": 2500000,
  "outputMicrosPerMillion": 10000000,
  "cachedInputMicrosPerMillion": 1250000,
  "effectiveTs": "2026-08-01T12:00:00Z",
  "expiresTs": "2026-11-01T12:00:00Z",
  "source": "provider-contract-2026-08-rev1",
  "approvedBy": "finops@example.com",
  "aggregateVersion": 4
}
```

After an update, verify that the Deployment does not have ambiguous overlapping
Pricing windows and publish a new immutable gateway candidate before expecting
runtime cost calculations to change. The `active` state is backend-managed
through soft delete and is not part of this form.
