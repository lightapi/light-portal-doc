# Register AI Agent

Use this task to register an AI agent as an API marketplace asset.

Typical steps:

- create or select the API
- create the API version with API type `agt`
- create the agent definition for the same API version id
- assign skills when the agent needs reusable behavior
- review tools exposed through the assigned skills
- configure role permissions before exposing the agent
- link the agent API version to a runtime instance when deployment metadata is available

The agent definition id is the API version id. This keeps the API catalog and
GenAI agent profile as one logical asset instead of two separate identities.
