# Automated Integration Testing & AI Agent Strategy for Light-Portal

**Document Type:** Engineering Strategy / Architecture  
**System:** Light-Portal (Multi-Service Architecture)  

---

## 1. Executive Summary
As **Light-Portal** scales into a complex multi-service ecosystem, traditional end-to-end (E2E) tests become too slow, brittle, and difficult to maintain. To enable rapid updates without fear of regression, we must adopt a **Shift-Left Layered Integration Approach**. 

Furthermore, to minimize the manual overhead of test creation and maintenance, this strategy incorporates **AI QA Agents** capable of autonomously generating, executing, and self-healing test suites based on structured declarative specifications.

---

## 2. Core Automated Integration Strategy

To test inter-service communication reliably and rapidly, we will implement the following methodologies:

### A. Consumer-Driven Contract (CDC) Testing
Instead of spinning up the entire portal ecosystem to test a single integration, we will use **Pact**. 
* **How it works:** The "Consumer" service defines the expected API structure (the contract). The "Provider" service checks its responses against this contract during its CI pipeline.
* **Benefit:** Catches breaking API changes instantaneously without requiring a full staging environment.

### B. Ephemeral Environments
Tests should never rely on shared, persistent environments which are prone to state pollution.
* **Tooling:** **Testcontainers** or dynamic Docker Compose files.
* **Execution:** During the CI/CD pipeline, isolated instances of necessary services (e.g., databases, message brokers like Kafka, OAuth providers) are spun up, tested against, and destroyed. 

### C. API-First Testing
Because Light-Portal relies on strict API boundaries, UI-based testing should be minimized for integration validation.
* **Tooling:** **Karate DSL** or **REST Assured**.
* **Benefit:** Tests the actual data contracts and service boundaries directly, resulting in faster and more resilient tests.

### D. Mocking External Dependencies
* **Tooling:** **WireMock** or **Mountebank**.
* **Usage:** Stub out third-party APIs or external legacy systems to ensure our integration tests are entirely deterministic and not subject to external network failures.

---

## 3. AI Agent Automation Capabilities

Autonomous AI agents can significantly reduce the testing bottleneck. Within this architecture, AI agents will be utilized for the following tasks:

1. **Test Generation:** Automatically parse OpenAPI specifications to generate exhaustive test suites covering positive paths, edge cases, and error handling (400, 401, 429, 500).
2. **Self-Healing Test Pipelines:** When an engineer modifies an API schema intentionally, the AI agent will detect the resulting broken test, read the commit diff, and automatically generate a Pull Request to align the test with the new API schema.
3. **Synthetic Data Generation:** Generate realistic, schema-compliant JSON payloads for testing, avoiding hard-coded or outdated mock data.
4. **State Machine Exploration:** Execute multi-step user journeys by exploring the API state (e.g., *Authenticate -> Register Service -> Query Gateway -> Validate Routing*).

---

## 4. AI-Optimized Test Specifications & Plans

AI agents require structured, semantic, and declarative inputs to function reliably. To direct the AI agent, we will provide test plans in the following formats:

### A. OpenAPI / AsyncAPI Specifications (The Golden Source)
The most effective way to instruct an AI is to provide the API design spec. 
* **AI Action:** The agent reads `openapi.yaml`, identifies required headers (e.g., JWT authorizations) and payload schemas, and writes the baseline integration code automatically.

### B. Behavior-Driven Development (BDD) / Gherkin Syntax
For complex business logic, engineers and product managers will write Gherkin specs. The AI agent translates this plain English into executable API scripts.

**Example Spec:**
```gherkin
Feature: Light-Portal Service Registration

  Scenario: Registering a new microservice routing path
    Given the light-oauth2 service provides a valid admin JWT
    When I send a POST request to "/portal/services" with the following payload:
      """
      {
        "serviceId": "demo-service",
        "route": "/api/v1/demo"
      }
      """
    Then the response status should be 201
    And the service should be discoverable via the light-router instance
```

### C. Declarative YAML Test Workflows
Instead of writing imperative code (Java/Node.js), test workflows should be written in YAML. YAML is highly deterministic and minimizes AI syntax hallucinations.

**Example Spec:**
```yaml
# AI Agent Workflow Instructions
name: Developer Onboarding Flow
steps:
  - name: Get Token
    api: POST /oauth/token
    extract: 
      token: response.body.access_token
  - name: Register Service
    api: POST /portal/services
    headers:
      Authorization: Bearer ${token}
    assert:
      status: 200
```

### D. Flow-Based "User Stories" (Agentic Prompting)
For autonomous exploration, the AI can be given high-level flow objectives. The agent is responsible for breaking the flow into actual API requests.

**Example Prompt to Agent:**
> *"Simulate a developer onboarding flow for Light-Portal. 1. Request an OAuth token. 2. Register a new mock-service to the portal. 3. Update the rate-limiting configuration for that service to 5 requests per minute. 4. Send 10 concurrent requests to verify the rate limit correctly throws a 429 error."*

---

## 5. Conclusion & Next Steps
By combining **Contract Testing (Pact)**, **Ephemeral Environments (Testcontainers)**, and **Declarative AI-driven Automation**, Light-Portal can scale its microservices with confidence. 

**Immediate Action Items:**
1. Standardize and centralize all `openapi.yaml` files for Light-Portal services.
2. Integrate Testcontainers into the primary CI/CD pipeline.
3. Select an AI testing tool/framework (e.g., CodiumAI, Postman Postbot, or a custom LLM script) and seed it with our initial Gherkin business flows.
