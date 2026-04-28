# Deployment Workflow

Light Portal manages product, API, application, instance, runtime
configuration, and deployment metadata for multiple tenants. The deployment
workflow extends that model so a user can deploy a configured instance to a
Kubernetes cluster from the Instance Admin page.

The goal is to provide a production-like deployment path for small businesses
and enterprise tenants without requiring Light Portal to have direct network
access to every customer cluster.

## Problem

Each API or application repository can contain a `k8s/` folder with Kubernetes
deployment templates. The templates contain variables in the following format:

```text
${key:defaultValue}
```

For each configured portal instance, Light Portal can generate a `values.yml`
document that contains deployment-time values such as image URL, namespace,
replica count, service ports, config references, resource limits, ingress host,
and rollout options.

When a user clicks the Deployment button for an instance, the system should:

1. Resolve the target instance and deployment environment.
2. Generate or fetch the instance deployment `values.yml`.
3. Send a deployment command to a deployer that can access the target
   Kubernetes cluster.
4. Render the final Kubernetes manifests from the repository templates.
5. Validate and apply the manifests.
6. Track rollout status and return deployment results to Light Portal.

## Recommended Architecture

The recommended default is to run a small Rust deployer inside each target
Kubernetes cluster.

```text
Light Portal
  |
  | deployment request / status query
  v
Light Controller
  |
  | outbound WebSocket session / MCP tool call
  v
In-cluster Rust Deployer Pod
  |
  | Kubernetes API via in-cluster ServiceAccount
  v
Customer Kubernetes Cluster
```

This is similar to the agent model used by GitOps and cloud management systems:
the cluster-local agent connects outbound to the control plane and performs
cluster operations using tightly scoped Kubernetes RBAC.

## Why In-Cluster Deployer

Running the deployer inside the cluster should be the default for production.

### Kubernetes Authentication

An in-cluster deployer can use Kubernetes in-cluster configuration. The Rust
service can use `kube-rs` and call the equivalent of default client discovery.
Kubernetes mounts a ServiceAccount token into the pod, so no external
`kubeconfig` file needs to be copied, stored, rotated, or exposed.

### Least-Privilege RBAC

The deployer should run as a dedicated ServiceAccount with only the permissions
needed for the namespaces and resources it manages. If a deployer is
compromised, the blast radius is limited by Kubernetes RBAC.

For a small-business deployment, the first version can bind the deployer to a
dedicated namespace. For managed enterprise environments, the portal can create
one deployer per cluster or per tenant namespace.

### Firewall Traversal

Many customer clusters are behind firewalls or corporate networks. An in-cluster
deployer can open an outbound WebSocket connection to Light Controller. This
avoids inbound firewall rules and allows Light Portal to manage deployments
without direct access to the Kubernetes API server.

### Operational Simplicity

Customers do not need to run a separate VM or keep a standalone deployment
process alive. They install the deployer with one Kubernetes YAML file or Helm
chart, and Kubernetes restarts it if it fails.

## Deployment Transports

The deployment system should support two transports.

### Controller-Mediated WebSocket

This is the preferred transport for private customer environments.

1. The deployer pod starts inside the customer cluster.
2. It registers with Light Controller over an outbound WebSocket.
3. The controller authenticates the deployer and records its tenant, cluster,
   environment, capabilities, and current status.
4. Light Portal sends deployment commands to the controller.
5. The controller forwards the command to the deployer using MCP-style tool
   calls over the existing session.
6. The deployer streams status back through the controller.

This mode works when Light Portal cannot reach the customer environment.

### Direct Deployer URL

This is useful for local MicroK8s, managed clusters, and environments where
Light Portal can reach the deployer directly.

The deployer URL can be stored in deployment configuration or config server
metadata. Light Portal or the workflow engine can call the deployer's API/MCP
endpoint directly.

Direct mode should be treated as an optimization, not the primary model for
customer-managed private networks.

## Deployer Responsibilities

The deployer is intentionally narrow. It should not own tenant configuration or
business workflow decisions. It executes deployment instructions and reports
results.

The deployer should support these actions:

- `render`: Fetch templates and values, render manifests, and return a manifest
  summary.
- `dryRun`: Render manifests and validate them against the Kubernetes API
  without applying changes.
- `deploy`: Apply manifests and wait for rollout status.
- `redeploy`: Re-apply manifests and trigger rollout if needed.
- `undeploy`: Delete resources created by the deployment.
- `status`: Return current Kubernetes resource and rollout status.
- `logs`: Return recent pod logs for the deployed instance.
- `rollback`: Redeploy a previous Light Portal deployment snapshot.

The first implementation should include `dryRun`, `deploy`, `undeploy`, and
`status`.

Rollback should be implemented through Light Portal deployment history, not
native Kubernetes rollout undo. Native Kubernetes rollback only reverts the
Deployment pod template and does not reliably revert associated ConfigMaps,
Secrets, or deployment values. A Light Portal rollback should redeploy a
previous immutable deployment snapshot so pods, config, environment variables,
and related resources return to the same known state.

## Deployment Request

A deployment request should be explicit and auditable.

```yaml
requestId: 01964b05-0000-7000-8000-000000000001
hostId: 01964b05-552a-7c4b-9184-6857e7f3dc5f
instanceId: petstore-dev
environment: dev
clusterId: microk8s-local
namespace: petstore-dev
action: deploy
valuesRef:
  source: config-server
  path: /deployments/petstore-dev/values.yml
template:
  repoUrl: https://github.com/lightapi/petstore-api.git
  ref: main
  path: k8s
options:
  dryRun: false
  waitForRollout: true
  timeoutSeconds: 300
```

The request should be created by Light Portal and persisted as deployment
history before it is sent to the deployer.

## Values File

The `values.yml` is instance-specific. It should contain all values needed to
render Kubernetes templates for one deployment target.

```yaml
image:
  repository: ghcr.io/lightapi/petstore-api
  tag: 1.0.0
deployment:
  replicas: 2
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
service:
  port: 8080
ingress:
  enabled: true
  host: petstore-dev.example.com
config:
  snapshotId: petstore-dev-20260427
  configServerUrl: https://config.lightapi.net
template:
  repoUrl: https://github.com/lightapi/petstore-api.git
  ref: main
  path: k8s
```

The deployer can receive the values inline or fetch them from config server
using the `valuesRef` in the deployment request.

Config Server should be the authoritative source of truth for deployment
values. At deployment time, Light Portal should create an immutable snapshot of
both the deployment `values.yml` and the runtime configuration `values.yml`.
That snapshot is the deployment evidence. If a deployment fails or must be
audited later, the team must be able to reconstruct exactly which values were
used even if the current config has changed.

Light Portal should persist the snapshot reference and hash in deployment
history. It should not rely only on a mutable config path.

## Template Rendering

The initial template format can use simple placeholders:

```yaml
image: ${image.repository}:${image.tag}
replicas: ${deployment.replicas:1}
```

The renderer should support nested keys and defaults. If a key is missing and no
default is provided, rendering should fail.

The deployer should render manifests in memory and avoid writing generated YAML
to disk unless debug mode is explicitly enabled.

Longer term, the deployer can support additional renderers:

- Built-in `${key:default}` renderer for simple service templates.
- Kustomize for standard Kubernetes overlays.
- Helm for teams that already maintain charts.

The built-in renderer should be deterministic and small. It should not evaluate
arbitrary code.

Do not use raw string replacement or regex replacement against raw YAML text.
YAML is indentation sensitive, and multi-line values, certificates, JSON
strings, and embedded config blocks can break when substituted as plain text.

The preferred first renderer is a constrained internal AST renderer:

1. Parse each template document with `serde_yaml` into `serde_yaml::Value`.
2. Recursively traverse the YAML value tree.
3. Resolve placeholders only inside string scalar values.
4. Replace `${key:default}` with values from the structured deployment values.
5. Serialize the YAML value back to YAML or convert it directly to Kubernetes
   dynamic objects.

This avoids most quoting, escaping, and indentation bugs because YAML parsing
and serialization remain responsible for formatting. It also keeps the renderer
small and prevents arbitrary code execution.

The implementation must include tests for ConfigMap multi-line blocks, JSON
strings, certificate-shaped values, and Secret references before production use.

## Kubernetes Execution

The Rust deployer should prefer `kube-rs` and the Kubernetes API over shelling
out to `kubectl`.

Benefits:

- no `kubectl` binary dependency
- structured errors
- easier dry-run and rollout status handling
- better control over authentication and namespaces
- safer request construction

`kubectl` can remain a diagnostic or fallback mode, but it should not be the
default production implementation.

The deployer should use Kubernetes server-side dry run for validation:

```text
dryRun=All
```

For apply, use server-side apply when possible so the deployer has a clear field
manager identity.

The field manager must be explicit, for example:

```text
fieldManager=light-deployer
```

Using a stable field manager is important for coexistence with other Kubernetes
controllers. For example, a Horizontal Pod Autoscaler may own Deployment
replica changes. Server-side apply helps the deployer avoid accidentally
overwriting fields owned by other managers.

For rollout status, the deployer should use the Kubernetes watch API rather
than only polling logs. The portal user experience should show resource status
transitions such as:

```text
Pending -> ContainerCreating -> Running -> Ready
```

Streaming watch events through the deployer gives Light Portal a precise
deployment timeline similar to a CI/CD job log while still preserving structured
Kubernetes state.

## Security Model

Security is the central design constraint because this component can mutate a
customer cluster.

### Authentication

The deployer must authenticate to Light Controller or Light Portal before it can
receive commands. Recommended options:

- mTLS for deployer-to-controller registration
- signed JWT enrollment token for first registration
- short-lived command tokens issued by Light Portal

The deployer should have a stable `deployerId` and should report cluster,
namespace, version, and capability metadata during registration.

### Authorization

Light Portal must verify that the requesting user can deploy the target
instance, environment, and tenant. The deployer must also enforce local
constraints:

- allowed namespaces
- allowed repository hosts and repository names
- allowed image registries
- allowed Kubernetes resource kinds
- allowed actions

The deployer should reject commands outside its configured policy even if the
portal sends them.

### RBAC

For namespace-scoped deployments, prefer `Role` and `RoleBinding` over
`ClusterRole` and `ClusterRoleBinding`.

Version 1 should allow only application-level resource kinds:

- `Deployment`
- `Service`
- `Ingress`
- `ConfigMap`
- `Secret`

Version 1 should explicitly block cluster-scoped and control-plane resources,
including:

- `Namespace`
- `ClusterRole`
- `ClusterRoleBinding`
- `CustomResourceDefinition`
- admission webhooks

This keeps the default deployer RBAC narrow and supports least-privilege
customer installations.

Example namespace-scoped installation:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: light-portal-deployer
  namespace: petstore-dev
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: light-portal-deployer
  namespace: petstore-dev
rules:
  - apiGroups: ["", "apps", "networking.k8s.io"]
    resources: ["deployments", "services", "ingresses", "configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: light-portal-deployer
  namespace: petstore-dev
subjects:
  - kind: ServiceAccount
    name: light-portal-deployer
    namespace: petstore-dev
roleRef:
  kind: Role
  name: light-portal-deployer
  apiGroup: rbac.authorization.k8s.io
```

Secrets should be handled carefully. Avoid logging rendered manifests that
contain secret values. Prefer references to existing Kubernetes Secrets,
External Secrets, Sealed Secrets, or config-server secret references resolved
inside the deployer.

The Rust implementation must also avoid logging raw Kubernetes apply payloads.
When using `tracing` or `log`, never log full `kube-rs` request objects,
patches, or serialized manifests for `Secret` resources. Kubernetes Secret
values are base64 encoded, not encrypted, and will leak credentials if written
to pod stdout.

## Deployment Pod

The deployer can be installed as a Kubernetes Deployment.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: light-portal-deployer
  namespace: petstore-dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: light-portal-deployer
  template:
    metadata:
      labels:
        app: light-portal-deployer
    spec:
      serviceAccountName: light-portal-deployer
      containers:
        - name: deployer
          image: ghcr.io/lightapi/light-portal-deployer:0.1.0
          env:
            - name: LIGHT_CONTROLLER_WS_URL
              value: wss://controller.lightapi.net/deployer/ws
            - name: DEPLOYER_ID
              value: petstore-dev-microk8s
            - name: DEPLOYER_TOKEN
              valueFrom:
                secretKeyRef:
                  name: light-portal-deployer-credentials
                  key: token
            - name: ALLOWED_NAMESPACES
              value: petstore-dev
```

## Portal Workflow

The Instance Admin Deployment button should not synchronously run deployment
logic in the browser request. It should create a deployment request and trigger
an asynchronous workflow.

Recommended flow:

1. User clicks Deployment for an instance.
2. Portal validates authorization.
3. Portal resolves instance, environment, product version, image, config
   snapshot, and template repository.
4. Portal creates a deployment request row/event.
5. Portal snapshots deployment values and runtime values.
6. Portal or workflow engine runs `dryRun`.
7. If the target environment requires approval, workflow waits for human
   approval.
8. Workflow calls `deploy`.
9. Deployer streams events: render complete, dry-run complete, apply started,
   pod phase changes, rollout progressing, rollout complete or failed.
10. Portal updates deployment history and status.
11. User can inspect rendered manifest summary, rollout status, pod status, and
    logs.

This fits the agentic workflow model. The workflow can ask the user to approve
the rendered changes before applying them.

Approval should be configurable at the environment level. Development and test
environments can allow automatic deployment. Production environments should
normally require manual approval through Light Portal or an agentic workflow
ask task.

## Status And Audit

Light Portal should persist deployment history.

Suggested fields:

- `deploymentId`
- `hostId`
- `instanceId`
- `environment`
- `clusterId`
- `namespace`
- `action`
- `status`
- `requestUser`
- `deployerId`
- `templateRepoUrl`
- `templateRef`
- `templatePath`
- `valuesHash`
- `valuesSnapshotId`
- `runtimeValuesHash`
- `runtimeValuesSnapshotId`
- `manifestHash`
- `templateCommitSha`
- `resourceSummary`
- `imageRepository`
- `imageTag`
- `startedTs`
- `completedTs`
- `errorMessage`

The deployer should return enough detail to reproduce the deployment intent
without storing secrets.

Light Portal should store only the rendered manifest hash, Git commit SHA, and a
redacted resource summary. It should not store full rendered YAML in the
database because rendered manifests can contain environment variables,
connection strings, or credentials.

Example resource summary:

```json
[
  {"kind": "Deployment", "namespace": "petstore-dev", "name": "petstore"},
  {"kind": "Service", "namespace": "petstore-dev", "name": "petstore"}
]
```

## Multi-Tenant Considerations

Small-business cloud service means multiple tenants may share Light Portal but
deploy to separate clusters or namespaces.

Rules:

- Tenant identity must be present in every deployment request.
- A deployer must be bound to one tenant boundary. In most installations, that
  means one tenant namespace or a tightly controlled set of namespaces owned by
  that tenant.
- Do not share one deployer across unrelated tenants.
- Namespace policy must be enforced both by portal authorization and deployer
  local policy.
- Deployment history must be filtered by `hostId`.
- A compromised deployer must not be able to receive commands for another
  tenant.

## Failure Handling

The deployer should classify failures:

- template repository fetch failure
- values file fetch failure
- render failure
- manifest validation failure
- Kubernetes API authorization failure
- apply failure
- rollout timeout
- health check failure
- controller WebSocket disconnected
- deployer registration rejected

Each failure should include a safe message and diagnostic metadata. Secret
values must be redacted.

For controller-mediated deployments, the deployer must have a resilient
WebSocket lifecycle. If Light Controller restarts or the network drops, the
deployer should not crash. It should reconnect with exponential backoff and
jitter, re-register after reconnecting, and resume accepting commands only after
the controller confirms the deployer session.

## First Implementation

The first implementation should target local MicroK8s and direct feedback in
Light Portal.

Phase 1:

- Create Rust deployer service.
- Run it inside MicroK8s.
- Support direct API mode for local testing.
- Implement `render`, `dryRun`, `deploy`, `undeploy`, and `status`.
- Use `kube-rs` and in-cluster ServiceAccount authentication.
- Support built-in `${key:default}` rendering.
- Add deployment request and deployment history tables/events.
- Add Instance Admin deployment request flow.

Phase 2:

- Add controller-mediated WebSocket registration.
- Expose deployer operations as MCP tools through the controller.
- Stream deployment progress and Kubernetes watch events to Light Portal.
- Implement exponential backoff reconnect and re-registration.
- Add approval step through agentic workflow.

Phase 3:

- Add Helm/Kustomize renderer support if needed.
- Add rollback support.
- Add multi-cluster inventory and deployer health view.
- Add deployment policy and quota enforcement.

## Resolved Design Decisions

- Config Server is the authoritative source of truth for values. Each
  deployment stores immutable deployment and runtime values snapshot references
  plus hashes.
- Light Portal stores rendered manifest hash, template Git commit SHA, and
  redacted resource summary. It does not store full rendered manifests by
  default.
- Regulated environments can add an opt-in enterprise artifact mode that stores
  the full rendered manifest in encrypted object storage with strict retention.
  Full manifests should stay out of the relational database.
- Deployment approval is configured at the environment level. Production should
  require approval by default.
- Deployers are installed per tenant boundary and should not be shared across
  unrelated tenants.
- Version 1 allows only application-level resources: Deployment, Service,
  Ingress, ConfigMap, and Secret.
- The first renderer should be a constrained internal AST renderer based on
  `serde_yaml`, not raw text replacement.
- The direct deployer URL mode should expose MCP immediately, using the same
  internal tool implementation that controller-mediated WebSocket mode will use
  later.
- Rollback is a redeploy of a previous Light Portal deployment snapshot, not a
  native Kubernetes rollout undo.

## Open Questions

- Which object storage providers should enterprise artifact mode support first?
- What retention policies should be available for encrypted rendered manifest
  artifacts?
- Should direct MCP use streamable HTTP only, or should it also expose SSE for
  long-running deployment progress events?
- Should rollback require the same environment-level approval policy as deploy?

## Recommendation

Use an in-cluster Rust deployer as the default production model. The deployer
should connect outbound to Light Controller and execute deployment commands via
MCP-style tools. Direct deployer URL mode is useful for MicroK8s and managed
environments but should be secondary. The MCP tool implementation should be
shared by both transports from the beginning.

Use `kube-rs` instead of shelling out to `kubectl` for the production execution
path. Keep the deployer small, policy-bound, and auditable. Let Light Portal own
deployment intent and history, while the deployer owns safe cluster-local
execution.
