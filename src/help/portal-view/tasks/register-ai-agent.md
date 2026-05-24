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

If the agent does not need reusable skills yet, skip the skill assignment step.
The tool review step is only useful after skills are assigned, so it can remain
optional while you continue to access control or runtime linking.

After all required steps are complete and the remaining optional steps are
complete or skipped, use Complete Task on the task detail page. Completing the
task clears its stored task context so it no longer appears in Recent Tasks.

The agent definition id is the API version id. This keeps the API catalog and
GenAI agent profile as one logical asset instead of two separate identities.
