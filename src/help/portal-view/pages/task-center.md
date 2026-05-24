# Task Center

Use Task Center to start guided portal workflows that span multiple existing
pages and forms.

Task Center does not replace the underlying pages. It gives each workflow a
single starting point, carries useful context in the URL, and links to the
forms or admin pages needed to finish the work.

## Where Task Context Is Stored

Task context is stored in the user's browser `sessionStorage`, not in the portal
database. The saved values are local to the current browser session and are used
to restore Recent Tasks, skipped checklist steps, and the context chips shown on
task pages.

Task Center uses session storage keys such as:

- `portal-view.taskContext.<taskId>`
- `portal-view.taskSkippedSteps.<taskId>`
- `portal-view.recentTaskContexts`
- `portal-view.recentPages`

Because this state is browser-local, it is not shared across users, devices, or
different browser sessions. Clearing browser session storage, using Clear
Context, or completing a task removes the local task context and the task no
longer appears in Recent Tasks.

Common areas:

- search for tasks, pages, forms, or entity context
- filter tasks by category
- continue tasks shown in Recent Tasks
- open context-aware suggestions when the URL already contains entity IDs
- open a task detail page to review required and optional steps

Recent Tasks and Suggested Tasks are shown separately from the category list.
When there is no search query, tasks already shown in those sections are hidden
from the category cards so the same task does not appear twice on the page.

Task details show each workflow step, progress status, related pages, and
actions for opening the next page or form. When a task opens another page, the
portal carries task context through the URL so the destination can prefill or
highlight the relevant record when supported.
