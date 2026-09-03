# Enterprise LLM Inference Options and Mac Studio Business Case

## Status

Decision proposal and pilot plan. Pricing and product availability were checked
on September 3, 2026 and must be refreshed before purchase.

## Executive Recommendation

Approve one Mac Studio with M5 Ultra, 256 GB unified memory, and at least 2 TB
of storage as a capacity-measurement and model-qualification node. Use its
measured throughput to size an N+1 production fleet during a bounded 90-day
pilot. Do not approve one Mac as the production capacity plan.

Use a hybrid routing policy:

- route approved, repetitive, data-sensitive diagnosis and agent workflow calls
  to the local Mac;
- retain Amazon Bedrock as the managed fallback and as the escalation route for
  tasks that require Claude Opus 5 or Claude Fable 5 quality; and
- keep the LLM Gateway Public Alias stable so applications do not depend on the
  physical provider.

This is the most defensible case for the Mac. The anticipated workload runs
continuously and may present about 100 million or more logical input tokens per
day. At that volume, premium per-token inference can dominate operating cost.
A right-sized Mac fleet buys a private, fixed-cost capacity pool for workloads
that pass on an open-weight model, while Bedrock continues to cover
policy-eligible bursts, disaster recovery, and the quality ceiling.

The purchase case is strong against always-on Opus 5 or Fable 5 traffic, but it
is not automatically strong against inexpensive open-weight models already
hosted by Bedrock. The final decision depends on measured local throughput,
cache hit rate, required fleet size, workflow quality, and availability—not
only the daily token counter.

## Scope and Requirements

The target workloads are Light Portal diagnosis and agentic workflows, not
foundation-model training. The selected service must support:

- reliable tool calling and structured output across multi-step workflows;
- streaming responses and cancellation;
- adequate context for logs, configurations, retrieved knowledge, and tool
  results;
- predictable latency at the expected concurrent-session count;
- private handling of prompts, retrieved knowledge, tool results, and output;
- auditable model, quantization, prompt, runtime, and configuration revisions;
- an OpenAI-compatible or other LLM Gateway-supported provider protocol; and
- a tested fallback when the local model is unavailable or fails a capability
  policy.

Model fit is an acceptance test, not an assumption. A model that fits in memory
but cannot reliably select tools, preserve arguments, or finish the workflow is
not a viable deployment.

## Workload Profile

The expected workload is materially larger and more continuous than an
interactive assistant:

- workflows operate 24 hours per day to monitor services;
- incidents trigger diagnosis and potentially corrective actions;
- `light-portal-test` and corporate regression suites run continuously or on a
  schedule;
- agents inspect test results, correlate failures, report findings, and address
  approved issues; and
- aggregate logical input volume can reach about 100 million tokens per day and
  may grow beyond that as workflows are added.

This profile favours owned capacity, but it also makes capacity engineering a
first-order requirement. At a perfectly even arrival rate:

| Gross input tokens/day | Average input rate before cache effects |
| ---: | ---: |
| 100 million | 1,157 tokens/second |
| 500 million | 5,787 tokens/second |

These are aggregate input rates, not the decode speed of one request. Traffic
will be burstier than the average, and generated reasoning/output consumes a
separate, usually scarcer decode budget. A single Mac must not be assumed to
serve even the 100-million-token tier until an end-to-end replay measures
prefill throughput, prompt-cache reuse, decoding, concurrency, and queueing.
The 500-million row is a growth sensitivity, not a claim that a practical Mac
fleet can serve it. Do not extrapolate beyond the measured pilot range.

Track at least four different quantities:

1. gross logical input tokens presented by workflows;
2. uncached input tokens actually prefetched by the model;
3. cache-read tokens and cache eviction/rebuild frequency; and
4. reasoning plus visible output tokens actually decoded.

Agent workflows often repeat system prompts, tool schemas, policy, repository
context, and test metadata. Prefix caching and context compaction may therefore
reduce physical compute and cloud billing substantially. Conversely, merely
counting gross tokens can overstate both the Bedrock bill and the local fleet
required. Capacity and TCO must use the same trace and cache semantics.

### Interpreting Codex-Like Token Counters

A large cumulative input/output ratio is normal for an agent. Each model call
includes a substantial prefix: system and developer instructions, tool
definitions, relevant conversation history, previous model output, and tool
results. The cumulative input counter adds the input tokens for every call, so
the same logical prefix may be counted many times. Output is only the newly
generated tokens for each call.

The input tokens are real logical model inputs, but they are not necessarily
unique tokens or full prefill work. Official OpenAI usage objects report total
input and cached input separately; total input includes the cached portion. A
local Codex session inspected on September 3, 2026 reported approximately
3.54M cumulative input tokens, 3.36M cached input tokens, and 19.7K output
tokens. About 95 percent of its reported input was cache hits, leaving about
178K uncached input tokens at that observation point.

That example must not be assumed for Light Portal. Measure the actual workflow
traffic because cache reuse depends on stable prefixes, cache retention,
eviction, model revisions, process restarts, and routing. For financial and
capacity analysis, always graph:

```text
logical_input = cached_read + cache_write + uncached_input
cache_hit_rate = cached_read / logical_input
physical_prefill_work ~= cache_write + uncached_input
```

The final approximation is runtime-specific. Cache hits still use KV-cache
memory and some lookup/attention work, but they avoid recomputing the entire
cached prefix. They can also be billed at a discounted cached-input rate by a
managed provider; they are not automatically free.

## Current Product Facts

The proposed Mac is real but very new. Apple announced the M5 Ultra Mac Studio
on August 25, 2026, with customer availability starting September 22. The
36-core CPU, 80-core GPU, 256 GB unified-memory, 1 TB configuration is currently
listed at CAD 15,749; moving to 2 TB adds CAD 750. Apple specifies 1.2 TB/s
memory bandwidth, 10 Gb Ethernet, and configurations up to 512 GB unified
memory. The 256 GB configuration is therefore a purchasable candidate, but no
internal production evidence should be inferred from Apple's performance
claims.

The model names in this proposal are also current:

- Claude Opus 5 is active in Bedrock with a 1 million-token context window and
  a 128,000-token maximum output. Its published base price is USD 5 per million
  input tokens and USD 25 per million output tokens.
- Claude Fable 5 is active in Bedrock with the same stated context and maximum
  output sizes. Its published price is USD 10 per million input tokens and USD
  50 per million output tokens.
- Qwen3.8-27B is a 27-billion-parameter dense vision-language model under
  Apache-2.0. Its official artifact is about 55.6 GB in BF16 and has a native
  262,144-token context window.
- Qwen3.8-Flash-Next is not a 27B model. It is an experimental MoE preview whose
  repository is about 180B parameters overall; the model card reports a 125B
  model core, 51B n-gram embedding parameters, and 6B activated parameters.
  It uses the Qwen Community License rather than Apache-2.0. Qwen recommends
  dedicated serving engines for production/high-throughput use, so Mac runtime
  support and commercial licence applicability must be proved before selection.

Do not use a family name as the production pin. Procurement and qualification
must record the exact model repository, immutable revision, weight digest,
quantization, chat template, inference runtime, and licence review.

## Options at a Glance

| Criterion | Bedrock managed models | AWS GPU self-hosting | Mac Studio self-hosting |
| --- | --- | --- | --- |
| Up-front cost | Lowest | Low | Highest for one pilot node |
| Cost shape | Per token/request | Per instance-hour plus storage/network | Capital cost plus power, support, and labour |
| Scale | Immediate within quotas | Elastic but capacity/startup constrained | Fixed; another node requires another purchase |
| Frontier quality | Best option | Open-weight models only unless separately licensed | Open-weight models only unless separately licensed |
| Data locality | AWS boundary and selected routing region | Customer AWS account/VPC | Corporate premises; can operate without inference egress |
| Operational burden | Lowest | High: Linux, CUDA, drivers, scheduler, images | Medium/high: new macOS, Metal/MLX, native service operations |
| Software ecosystem | Provider managed | Broadest production ecosystem through CUDA | Improving, but narrower and newer than CUDA |
| Availability | Managed multi-tenant service | Can be multi-AZ and autoscaled | One box is one failure domain |
| Burst handling | Strong | Strong after capacity is available | Weak without queueing or cloud fallback |
| Hardware flexibility | None required | Many GPU sizes and generations | GPU and unified memory fixed for life of unit |
| Best fit | Low/variable demand and frontier escalation | High concurrency, CUDA-first serving, elastic demand | Private, steady demand when a measured fleet can carry the load |

## Option 1: Amazon Bedrock

### Advantages

- Fastest and lowest-risk path to supported frontier models.
- No GPU acquisition, drivers, model downloads, serving framework, host
  patching, or capacity scheduler for the Portal team.
- Per-token charging is attractive for pilots, sporadic use, and unpredictable
  demand; batch, cache, and service-tier discounts may reduce cost further.
- IAM, CloudTrail, KMS, VPC endpoints, quotas, regional controls, and existing
  AWS procurement integrate with normal enterprise operations.
- Current Bedrock documentation supports `Invoke` and `Converse` for Opus 5 and
  Fable 5. The Light Portal runtime already defines `bedrock_converse` and
  requires it to be paired with `providerType: aws_bedrock`.
- Bedrock offers much cheaper open-model routes as well as frontier models. For
  example, the current US price for Gemma 4 31B is USD 0.14/M input and
  USD 0.40/M output; Sydney pricing for Qwen3 32B is USD 0.1545/M input and
  USD 0.618/M output. Exact regional availability must be checked.

### Disadvantages and Risks

- Frontier agent loops can create large and difficult-to-predict token bills,
  particularly when tool results and history are repeatedly sent as input.
- Service quotas, throttling, provider incidents, model retirement, price
  changes, and region availability are outside the customer's control.
- Inference requires connectivity to AWS and cannot continue during an isolated
  corporate-network event.
- Prompts and results leave the premises even when AWS contractual and technical
  controls are acceptable.
- Data handling is model-specific. Bedrock documents provider access controls
  and configurable retention, but Fable 5 currently requires
  `provider_data_share` unless the account receives a zero-data-retention
  exception. In that mode prompts and completions are shared with Anthropic and
  may be retained for up to 30 days. This can disqualify Fable for sensitive
  diagnosis even though other Bedrock models meet the policy.
- Frontier quality cannot be compared fairly to a medium local model. A lower
  local token cost has no value if workflow failure causes human rework or an
  unsafe action.

### Best Use

Use Bedrock as the initial benchmark, fallback, burst route, and frontier
escalation. It may also remain the cheapest primary route when demand is low or
when a low-cost hosted open model meets the quality gate.

## Option 2: Self-Hosted Model on AWS GPU Compute

This option includes EC2 or a managed SageMaker real-time endpoint using a GPU
instance. It is distinct from Bedrock because the team owns the model server,
runtime, scaling, and most availability work.

### Advantages

- Broad Linux/CUDA ecosystem: vLLM, SGLang, NVIDIA tooling, containers,
  telemetry, and established automation skills.
- Elastic choice of GPU size, count, Region, tenancy, and deployment topology.
- Easier than a Mac to reproduce with infrastructure as code, replace after
  failure, place behind a load balancer, and scale horizontally.
- Suitable for high concurrency and continuous batching. AWS G7e supplies
  96 GB per GPU, while larger sizes aggregate multiple GPUs.
- On-Demand avoids capital commitment; Savings Plans suit predictable demand;
  Spot can reduce eligible fault-tolerant capacity by up to 90%.
- Workloads stay in the corporate AWS security perimeter and can use private
  networking and existing cloud operations.

### Disadvantages and Risks

- An always-on endpoint accumulates cost while idle. As one published reference
  point, AWS lists `ml.g7e.2xlarge` with one 96 GB GPU at USD 4.20/hour in a
  SageMaker inference comparison: about USD 3,066 per 730-hour month before
  storage, network, support, or engineering labour.
- GPU capacity and quotas may not be immediately available in the desired
  Region or Availability Zone.
- The team owns image and driver updates, runtime regressions, model loading,
  autoscaling, security patches, monitoring, and incident response.
- Spot is interruptible with a two-minute notice, so it is not the only
  capacity for interactive agent sessions.
- Multi-GPU instances can be costly and may add tensor-parallel complexity.
- Prompts still leave the premises, and the instance needs carefully controlled
  model-download and software-supply-chain paths.

### Best Use

Use AWS GPU hosting when CUDA compatibility, high concurrency, elasticity,
multi-node scaling, or normal cloud HA is more important than the lowest
steady-state single-node cost. It is also the safest technical validation
environment for a model whose authors recommend vLLM or SGLang but whose Apple
Silicon support is not yet qualified.

## Option 3: Mac Studio M5 Ultra with 256 GB

### Advantages

- Prompts, retrieved documents, tool results, and model output can remain on the
  corporate network. Inference can continue without cloud egress.
- Fixed capital cost eliminates per-token charges for accepted local traffic
  and makes a fully utilized node easier to budget.
- The 256 GB unified-memory pool is much larger than a single mainstream cloud
  GPU's memory and avoids CPU-to-discrete-GPU weight copies. It gives the team
  room to test multiple quantizations and models substantially larger than 27B.
- Apple specifies 1.2 TB/s unified-memory bandwidth. `llama.cpp` treats Apple
  Silicon as a first-class Metal target and provides an OpenAI-compatible HTTP
  server. Apple's MLX and MLX-LM support Apple-Silicon generation,
  quantization, fine-tuning, and distributed inference.
- The unit is compact, quiet, and includes 10 Gb Ethernet; no data-centre GPU
  rack, high-amperage circuit, or cloud GPU reservation is required for a
  single-node pilot.
- It provides a reusable private-model lab for evaluation, quantization,
  embedding experiments, regression testing, and incident diagnosis even when
  local inference is not the final production route.
- AppleCare for Enterprise can add 24/7 telephone support and eligible onsite
  repair, reducing—but not eliminating—the new-platform support risk.

### Disadvantages and Risks

- The M5 Ultra system is pre-release as of this decision date. Framework and
  model-kernel compatibility, stability under sustained load, thermals, and
  real throughput are unproved for the Portal workload.
- A Mac Studio is a workstation, not an automatically replaceable cloud
  instance. One unit is a single failure and maintenance domain; production HA
  requires at least a second qualified route, normally Bedrock at first.
- The CUDA production ecosystem remains broader. The best-performing upstream
  recipe for a newly released architecture may arrive first for vLLM/SGLang on
  NVIDIA, while the Mac waits for MLX or GGUF conversion and kernel support.
- The inference server must normally run natively to use Metal. The team cannot
  assume that its Linux/CUDA container image will receive Mac GPU acceleration.
- Unified memory is shared by weights, KV cache, runtime, and the operating
  system. A model fitting by weight size alone does not prove the desired
  context length or concurrency.
- Long contexts can consume large KV caches and reduce concurrent sessions.
  Quantization can reduce quality, and model-specific tool parsing may be less
  robust than frontier APIs.
- GPU, memory, and internal storage cannot be upgraded later. A wrong sizing or
  immature runtime choice becomes sunk cost.
- macOS lifecycle, MDM, service accounts, FileVault recovery, certificates,
  unattended reboot, monitoring, log collection, backup, and physical security
  must be added to the support team's runbooks.
- Open-weight does not mean unrestricted. Each exact model licence, acceptable
  use policy, attribution requirement, and third-party conversion must pass
  legal and supply-chain review.

### Best Use

Use a Mac fleet as the primary route only for qualified private workloads with
steady demand and a model that meets the business outcome gate. Fleet size must
come from measured throughput at the required context and concurrency. Retain a
paid fallback for policy-eligible overflow, failure, and tasks requiring
frontier quality.

## Cost Model and Break-Even

Do not compare the Mac purchase price only with one month's peak Bedrock bill.
Use the same workload trace, successful-workflow denominator, support labour,
availability target, and three-year period for every option.

### Required Inputs

| Input | Symbol |
| --- | --- |
| Monthly non-cached input tokens | `I` |
| Monthly output/reasoning tokens | `O` |
| Cached input by cache class | `C` |
| Required concurrency and p95 time to first/output token | workload SLO |
| Successful workflow rate and human-rework cost | quality cost |
| Mac purchase, tax, support, spare/HA node, power, and labour | local TCO |
| GPU instance hours, storage, snapshots, network, support, and labour | AWS GPU TCO |
| Fallback percentage and its token price | fallback TCO |

The basic monthly formulas are:

```text
Bedrock = I * input_rate + O * output_rate + cache and feature charges

AWS GPU = instance_hours * hourly_rate + storage + network + operations

Mac = (purchase + support + power + operations + replacement reserve) / life_months
      + paid_fallback

Cost per successful workflow = total cost / workflows passing the outcome gate
```

For a local fleet, calculate required nodes from both compute dimensions and
availability:

```text
prefill_nodes = peak_uncached_input_tokens_per_second
                / (measured_prefill_tokens_per_second_per_node * target_utilization)

decode_nodes = peak_output_tokens_per_second
               / (measured_decode_tokens_per_second_per_node * target_utilization)

capacity_nodes = ceiling(max(prefill_nodes, decode_nodes, concurrency_nodes))

production_nodes = capacity_nodes + failure/maintenance reserve
```

Use no more than 70 percent sustained target utilization until soak testing
supports a different value. The reserve must permit one node to be patched or
failed without violating the service objective. For a small fleet this normally
means N+1, not one production node plus an untested purchase plan.

### Illustrative Hardware-Only Threshold

The following is a sensitivity example, not a budget quote. It uses the US
USD 11,299 price for the 256 GB/2 TB configuration, adds a 15% support and
replacement reserve, assumes 350 W average wall power at USD 0.15/kWh, and
amortizes over 36 months. That is about USD 14,374 total or USD 399/month. It
excludes tax, facilities, engineering labour, downtime, and a second HA node.

For a workload mix of four input tokens per output token, USD 399/month is
approximately equivalent to:

| Comparator | Published rates (USD/M input, output) | Approximate monthly tokens at USD 399 |
| --- | --- | --- |
| Claude Fable 5 | 10, 50 | 17.7M input + 4.4M output |
| Claude Opus 5 | 5, 25 | 35.5M input + 8.9M output |
| Bedrock Gemma 4 31B, US | 0.14, 0.40 | 1.66B input + 416M output |

This reveals both sides of the case:

- compared with premium frontier traffic, a busy local node can recover its
  hardware cost at a moderate token volume;
- compared with a cheap hosted open model, token spend alone may never justify
  the Mac at the expected demand; and
- privacy, offline operation, local experimentation, stable capacity, and
  avoided data-governance work may therefore be the decisive benefits.

Replace every assumption with a procurement quote and 30 days of LLM Gateway
usage telemetry. Convert all candidates to one currency on the approval date.

### Cost at the Expected Traffic Scale

The following sensitivity shows input charges only, uses 30 days per month,
published standard uncached-input rates, and assumes every input token is an
uncached token. It intentionally excludes output charges because the observed
agent ratio is much more input-heavy than the earlier four-to-one assumption.
It also excludes prompt-cache, batch, volume, regional, and negotiated
discounts. It is a maximum uncached-input exposure, not an invoice forecast.

| Daily logical input volume | Claude Opus 5 input/month | Claude Fable 5 input/month | Bedrock Gemma 4 31B US input/month |
| --- | ---: | ---: | ---: |
| 100M input | USD 15,000 | USD 30,000 | USD 420 |
| 500M input growth case | USD 75,000 | USD 150,000 | USD 2,100 |

Add measured output and reasoning-token charges separately. Then replace the
uncached assumption with the actual provider-specific cache-read and cache-write
rates. For local capacity, use measured uncached/cache-write prefill work rather
than pricing every logical cache read as a fresh prefill.

At this scale, replacing routine premium-model traffic has very large potential
savings. Even a multi-node local fleet can have a short capital payback relative
to Opus or Fable. However, the cheap hosted-open-model column remains the
critical control: the local fleet must beat its cost, privacy, or operational
properties, and it must do so per successful workflow.

For example, eight illustrative USD 399/month Mac nodes are about USD 3,192 per
month on the same hardware-only assumptions, before labour, network, support,
spares beyond those eight nodes, and fallback. That can be far below uncached
premium-model input, but it exceeds the raw Gemma input charge at 100M logical
input tokens per day. Eight is an illustration, not a sizing recommendation;
only a cache-aware replay benchmark can determine whether the workload needs
two nodes, eight nodes, or a higher-throughput architecture.

### Cost Reduction Before Buying Capacity

Apply these controls to all three hosting options:

- cache stable system prompts, tool schemas, policies, repository summaries,
  and test-suite metadata with model-specific cache keys;
- send deltas and bounded log windows instead of entire histories;
- summarize or index historical test output once, then retrieve only evidence
  needed for the current decision;
- use deterministic code for polling, parsing, deduplication, thresholding, and
  known remediations; invoke an LLM only for semantic work;
- route classification and summarization to the smallest model that passes its
  task-specific gate;
- stop agent loops with explicit budgets, repeated-state detection, and
  idempotent action checks; and
- deduplicate identical incidents and fan out one diagnosis to affected
  workflows instead of recomputing it.

The lowest-cost token is the one the architecture does not need to infer.

## Why 256 GB Instead of a Smaller Mac

The 27B dense model is not the economic reason to buy 256 GB: a quantized 27B
model fits much smaller accelerators. The memory headroom is justified only if
the roadmap includes one or more of the following:

- testing 70B-to-120B-class quantized models;
- evaluating Qwen3.8-Flash-Next-class large MoE artifacts after runtime and
  licence qualification;
- retaining longer KV caches or serving multiple controlled contexts;
- running an embedding/reranking model beside generation; or
- keeping two model revisions resident to reduce changeover time.

If the pilot corpus and concurrency need only a 27B model, benchmark a smaller
M5 Max or lower-memory Ultra configuration before procurement. Unused unified
memory does not improve output quality.

## Other Viable Options

### Bedrock-Hosted Open Models

This is the most important fourth option. Test Gemma, Qwen, GPT-OSS, Nemotron,
Mistral, or another approved low-cost Bedrock model against the same workflow
suite. It preserves managed operations and may cost less than local ownership
at low utilization. Availability, licence, region, protocol behavior, and model
quality still require qualification.

### Managed Dedicated Endpoint

Use SageMaker or another approved managed endpoint instead of raw EC2. It costs
more than carefully operated EC2 but reduces serving, deployment, monitoring,
and autoscaling work. Scale-to-zero or scheduled endpoints can be useful for
development if cold-start time is acceptable.

### On-Premises NVIDIA Server or Appliance

A rack or tower server with one or more NVIDIA enterprise GPUs gives the support
team Linux/CUDA, container, telemetry, and vendor-support familiarity. It may
offer ECC memory, replaceable parts, and conventional redundancy depending on
the chosen server. It normally costs more, uses more power, and provides less
accelerator memory per purchase dollar than the Mac, but may be the better
production platform when CUDA compatibility and enterprise hardware service
are mandatory.

### Scheduled or Spot GPU Pool

Use On-Demand only for interactive baseline capacity and add Spot for
interruptible evaluation, batch diagnosis, quantization, or test execution.
This lowers idle cost without claiming Spot is safe for a live agent session.

### Hybrid Model Cascade

Use a small local or inexpensive hosted model for classification, retrieval
planning, summarization, and simple diagnosis; escalate only difficult or
low-confidence steps to Opus or Fable. Prompt caching, context compaction,
bounded tool output, and request deduplication can reduce cost regardless of
hardware.

## Proposed Light Portal Architecture

The deployment does not change application-facing contracts:

```text
Light Portal diagnosis / light-agent / light-workflow
                         |
                         | Public Alias
                         v
                    llm-gateway
                    /         \
       local replica group     Bedrock fallback / frontier escalation
        /      |      \                       |
       v       v       v                      v
    Mac 01   Mac 02   Mac N          bedrock_converse provider
    same immutable model, quantization, template, and runtime contract
```

For the Mac route, use `providerType: compatible` and the protocol actually
proved by conformance, normally `providerProtocol: openai_chat`. `llama-server`
already exposes an OpenAI-compatible chat endpoint and supports parallel
decoding. MLX-LM is a promising alternative, but the exact released server API
and tool-call behavior must be pinned and tested.

Follow [Local Model Provider Transport For LLM Gateway](../light-gateway/local-model-provider-transport.md):
terminate private TLS on the model host, bind the raw inference listener to
loopback, expose only required inference and identity paths, and publish the
provider through the normal immutable
[LLM Gateway topology](llm-gateway-topology.md). That transport design is still
marked proposed, so its implementation and production qualification are a
dependency—not an already available guarantee.

The alias should express capability and policy, such as
`diagnosis-private-medium`, rather than hardware or a mutable model name. Route
order, timeout, retry, paid fallback, and data-classification policy must be
explicit. Never send data that is restricted to premises through a cloud
fallback.

### Replica Routing Gap

The current LLM Gateway alias contains an ordered list of deployments. Dispatch
tries the first healthy deployment with an available concurrency permit and
spills to later candidates when an earlier deployment is unavailable or full.
This supports bounded fallback and some capacity spillover, but it is not an
explicit round-robin, least-loaded, or cache-affine replica scheduler.

For a multi-Mac fleet serving the same model, add a replica-group routing
contract to LLM Gateway rather than treating independent machines as
semantically different fallback models. A replica group must require the same
model revision, weight digest, quantization, tokenizer, chat template,
capability evidence, and pricing basis across members. It must provide:

- per-node health, readiness, concurrency, queue depth, and circuit state;
- least-loaded or power-of-two-choices selection for new stateless work;
- stable session-affinity or consistent-hash routing for multi-turn agents so
  reusable prompt/KV-cache prefixes return to the same Mac;
- bounded rebalance when a node is saturated, draining, failed, or patched;
- immutable audit evidence recording the physical node that served each call;
- no retry on a different node after response bytes or an action-bearing tool
  call have been accepted; and
- an N+1 failure reserve with a distinct Bedrock escalation tier.

An internal load balancer in front of the Macs is an interim alternative, but
it hides per-node capacity and physical-runtime identity from LLM Gateway. If
used, it must implement health-aware consistent hashing and expose trustworthy
node identity in signed response/audit metadata. Native replica-group routing
in LLM Gateway is the preferred production design.

Cache affinity is an optimization, not correctness state. A request must remain
correct after a cache miss or failover, although it may be slower. Report cache
hit rate by replica and session; an aggregate fleet hit rate can hide one hot
node and several ineffective replicas.

## 90-Day Pilot

### Phase 0: Before Purchase

1. Export 100-300 representative, sanitized diagnosis and agent workflows,
   including tool errors, long logs, retries, and adverse inputs. Also capture
   at least seven days of arrival rate, token, cacheability, concurrency, and
   output-length distributions for capacity replay.
2. Record Bedrock Opus 5, Fable 5, and at least two cheaper hosted models as
   quality/cost baselines.
3. Define numeric gates: workflow success, unsafe action rate, tool-call schema
   accuracy, p50/p95 latency, concurrent sessions, aggregate prefill and decode
   tokens per second, prompt-cache hit rate, queue depth, maximum context,
   uptime, and operator hours.
4. Obtain CAD quotes for the Mac, 2 TB storage, AppleCare, tax, power, and an HA
   strategy. Obtain matched AWS quotes in the same currency and Region.
5. Complete security, privacy, model-licence, model-card, and third-party weight
   conversion review.

### Phase 1: Lab Bring-Up

1. Enrol the Mac through the corporate Apple/MDM process; enable FileVault,
   escrow recovery, host firewall, EDR, certificate management, patch policy,
   non-interactive service identity, and physical access controls.
2. Pin macOS, Xcode/Metal dependencies, inference runtime, model revision,
   quantization, tokenizer, chat template, and hashes in a reproducible build
   record.
3. Run the inference service natively under a supervised service. Do not expose
   a model-management UI or raw runtime port.
4. Add private TLS, workload authentication, health/readiness, bounded queues,
   request/body/time limits, metrics, log redaction, and controlled model
   downloads.
5. Integrate through LLM Gateway; do not let applications call the Mac directly.

### Phase 2: Qualification

Run every candidate at the intended quantization and context:

- cold/warm start, streaming, cancellation, malformed responses, and tool-call
  conformance;
- 1, expected, peak, and overload concurrency with queue-saturation behavior;
- trace replay at the expected 100M logical-input-token daily load and a 500M
  growth sensitivity, with measured cached and uncached variants;
- session-affinity, cache-hit, rebalance, hot-node, and node-drain behaviour
  across at least two serving replicas;
- 24-hour soak and repeated restart/update/rollback exercises;
- p50/p95 time to first token, output rate, memory pressure, power, temperature,
  and operator intervention;
- prompt, retrieved-data, secret, vector, and reasoning-text leak checks;
- model quality and human-rework comparison against Bedrock baselines; and
- local failure, Mac reboot, network partition, certificate rotation, and
  policy-safe fallback.

### Phase 3: Controlled Production

Start with an internal cohort and a low traffic percentage. Increase traffic
only while fleet headroom remains above the failure reserve. Promote only an
immutable qualified artifact. Maintain a one-action rollback to the previous
local model or approved Bedrock route. Review quality, cache hit rate, queue
depth, per-node saturation, fallback rate, uptime, cost, and support labour
weekly.

## Approval and Exit Gates

Management should approve production use only if all of these hold:

1. The local model meets the agreed successful-workflow rate and safety bar;
   aggregate public benchmark scores are insufficient.
2. The fleet sustains the peak replay, expected concurrency, and p95 latency SLO
   at or below the approved utilization target without memory pressure or
   unbounded queues.
3. Three-year risk-adjusted TCO is favourable for the measured local-eligible
   traffic, or privacy/offline requirements independently justify the spend.
4. Security approves the on-premises data path, host hardening, model supply
   chain, licence, logging, and update process.
5. Technical support accepts a named owner, spare/fallback plan, monitoring,
   restore procedure, and patch/rollback SLO.
6. The production plan is N+1 or better for local-eligible traffic and retains
   a policy-safe fallback. One Mac is not represented as highly available.
7. LLM Gateway local-provider transport and live conformance evidence have
   completed their production gates.

Exit or resize the Mac route if the local model misses the quality gate, demand
is too low to justify ownership, support effort exceeds the budget, required
models remain unsupported on Metal/MLX, or traffic requires horizontal scale
that is cheaper and safer in AWS.

## Decision Requested

Authorize the 90-day pilot budget for one M5 Ultra/256 GB/2 TB Mac Studio as a
benchmark and qualification node, enterprise support coverage, security
onboarding, and named engineering/support capacity. Retain the existing Bedrock
path during the pilot. At day 60, present measured quality, cache effectiveness,
per-node prefill/decode throughput, concurrency, support effort, required N+1
fleet size, and projected three-year TCO. At day 90, decide among purchasing the
measured production fleet, using the Mac only for selected lanes, choosing AWS
GPU capacity, or retiring the local route.

This staged decision limits downside while preserving the Mac's central
business value: private, predictable, reusable inference capacity with no
per-token marginal charge for qualified local traffic.

## References

- [Apple Canada: M5 Ultra Mac Studio announcement and availability](https://www.apple.com/ca/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/)
- [Apple Canada: 256 GB M5 Ultra configuration and price](https://www.apple.com/ca/shop/buy-mac/mac-studio/m5-ultra-chip-36-core-cpu-80-core-gpu-256gb-memory-1tb-storage)
- [Apple Canada: Mac Studio technical specifications](https://www.apple.com/ca/mac-studio/specs/)
- [AppleCare for Enterprise](https://www.apple.com/support/professional/enterprise/)
- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
- [Amazon Bedrock: Claude Opus 5](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5.html)
- [Amazon Bedrock: Claude Fable 5](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-fable-5.html)
- [Amazon Bedrock data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html)
- [Amazon Bedrock data retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html)
- [AWS G7e inference performance and cost example](https://aws.amazon.com/blogs/machine-learning/accelerate-generative-ai-inference-on-amazon-sagemaker-ai-with-g7e-instances/)
- [Amazon EC2 accelerated instance specifications](https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html)
- [Amazon EC2 Spot pricing and interruption model](https://aws.amazon.com/ec2/spot/)
- [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B)
- [Qwen3.8-Flash-Next model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)
- [Qwen3.8-Flash-Next licence](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/main/LICENSE)
- [llama.cpp Metal and OpenAI-compatible server](https://github.com/ggml-org/llama.cpp)
- [MLX-LM](https://github.com/ml-explore/mlx-lm)
- [MLX distributed inference](https://github.com/ml-explore/mlx/blob/main/docs/src/usage/distributed.rst)
- [OpenAI API usage fields for cached and uncached input](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage)
