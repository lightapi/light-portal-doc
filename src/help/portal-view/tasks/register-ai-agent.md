# Register AI Agent

Use this task to register an AI agent as an API marketplace asset.

Typical steps:

- create or select the API
- create the API version with API type `agt`
- create the agent definition for the same API version id
- assign skills when the agent needs reusable behavior
- review tools exposed through the assigned skills
- configure role permissions before exposing the agent
- choose whether to save the Agent as a definition or deploy it now
- for deployment, select a compatible unbound `agt` runtime or create a new one
- verify the Agent API version has an active Instance API association

If the agent does not need reusable skills yet, skip the skill assignment step.
The tool review step is only useful after skills are assigned, so it can remain
optional while you continue to access control or runtime linking.

The runtime decision is required, but a runtime deployment is not. Select
**Save as Agent definition only** when authoring should finish without creating
a runnable deployment. The Agent remains unavailable at runtime until it is
linked and published.

When deploying now, the task only offers active `agt` runtime instances that
match the Agent API version's service identity and are not already assigned to
another Agent. Creating a new runtime locks its product version to the current
`agt` release and returns to the task to create and verify the Instance API
association.

An Instance ID alone does not complete deployment. The task verifies an active
`instance_api_t` association for the selected Agent API version before marking
the runtime step complete.

Runtime linking is still staging. Policy publication, Config Server snapshot
activation, and runtime acknowledgement must complete before the Agent is live.

After all required steps are complete and the remaining optional steps are
complete or skipped, use Complete Task on the task detail page. Completing the
task clears its stored task context so it no longer appears in Recent Tasks.

The agent definition id is the API version id. This keeps the API catalog and
GenAI agent profile as one logical asset instead of two separate identities.
