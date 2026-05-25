# Skill Workspace

Use Skill Workspace to review and assemble one GenAI skill after the skill
record has been created.

A skill contains the reusable instruction content that an agent can use. The
workspace shows the skill metadata, taxonomy, linked tools, linked workflows,
and test entry points in one place.

## Opening The Workspace

Open the workspace from the GenAI Skills page by selecting the workspace action
for a skill row.

The workspace needs a `skillId`. If the page is opened from a task or another
GenAI page, the portal carries that context through the URL so related actions
can prefill the current skill.

## Header Actions

Common actions:

- `Back`: return to the source page that opened the workspace.
- `Tool`: create a structured skill-to-tool link for the current skill.
- `Workflow`: create a structured skill-to-workflow link for the current skill.
- `Edit Skill`: update the skill metadata, parent skill, taxonomy, version, and
  content markdown.
- `Help`: open this guide in the portal documentation.

## Overview Tab

Use the Overview tab to confirm the skill identity and routing metadata.

The Skill panel shows:

- skill name
- version
- parent skill id
- active state

The Routing panel shows human-readable category and tag labels. These labels
come from the taxonomy tables. The update form stores the selected
`categoryIds` and `tagIds`, while the workspace displays the resolved labels.

The Description panel is a short human-readable summary of what the skill is
for.

## Tools Tab

Use the Tools tab to review the executable tools linked to the skill.

Each row shows:

- tool name
- tool id
- access level
- link configuration

Add tool links with the `Tool` button in the header. Tool links are structured
records; they are not parsed from the skill's markdown content.

## Workflow Tab

Use the Workflow tab to review workflows linked to the skill.

Each row shows:

- workflow name or workflow definition id
- workflow version
- workflow role
- start mode
- row actions

Available row actions:

- validate workflow tool links
- open the workflow editor
- start the workflow

Validation checks whether the linked workflow can resolve the tool references
needed by the skill workflow connection.

## Preview Tab

Use the Preview tab to inspect the skill's `contentMarkdown` and composition.

`contentMarkdown` is the instruction body for the skill. It should describe the
skill's goal, operating rules, and expected output format. It is not the source
of truth for executable tool, workflow, or endpoint references.

The Composition panel summarizes how many tools and workflows are linked and
which workflow is treated as primary.

## Test Tab

Use the Test tab to start the primary workflow linked to the skill.

The Start Primary Workflow button is enabled only when the skill has at least
one linked workflow. The primary workflow is the workflow with role `primary`;
if no primary role exists, the workspace uses the first linked workflow.

## Recommended Skill Authoring Flow

1. Create the skill with a clear name, description, content markdown, taxonomy,
   and optional parent skill.
2. Open the Skill Workspace.
3. Add the tools the skill is allowed to use.
4. Add the workflow that should execute or validate the skill.
5. Validate workflow tool links.
6. Preview the skill content and composition.
7. Start the primary workflow for a manual test.
8. Edit the skill if metadata, taxonomy, or instructions need adjustment.

## Troubleshooting

If categories or tags are missing, edit the skill and confirm taxonomy values
are selected.

If a tool or workflow is missing, add the structured link from the workspace.
Do not rely on a markdown `References` section to create executable links.

If workflow validation fails, open the workflow editor and confirm the workflow
uses tools that are linked to the skill.

If the Test tab is disabled, link a workflow to the skill first.
