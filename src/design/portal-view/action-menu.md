# Action Menu and Expanded Buttons

Status: Implemented.

Portal pages share an action menu with an optional expanded button view.
One flag in localStorage controls the display across all pages, set from a
single control in the header. There are no page-specific settings or overrides.

## Problem

Before this change, `/app/instance/InstanceAdmin` displayed 11 common row actions and two
additional actions for product ID `agt`: Publish Agent policy and Open Agent
chat. The buttons share an unwrapped row, putting pressure on the action column
and causing alignment problems when different products have different actions.

Icon-only buttons also require new users to hover to discover their purpose.
Pages with many actions consume considerable table space. Experienced users
still need the option to access actions directly with one click.

## Display Modes

### Menu (Default)

- Display a labeled **Actions** button with a dropdown indicator in each row.
- Use a consistent action-column width, independent of the row's action count.
- Show an icon, a clear action label, and a short description for each menu item.
- Render actions as a single flat list without category headings or submenus.
- Place destructive actions last, below a divider, and preserve their existing
  confirmation dialogs.
- Keep menus within the viewport, with scrolling when the full list cannot fit.

Descriptions explain the action rather than repeating its label. For example,
**Open agent chat** can use **Open Chat with this instance selected**. When a
definition supplies no description, render the label alone. Never fall back to
repeating the label as its own description.

### Expanded Buttons

- Render the same available actions as icon-only buttons in one compact,
  unwrapped row, restoring the presentation from before this refactoring.
- Keep the same order, disabled states, and handlers as the menu. Place
  destructive actions last and retain their destructive color.
- Do not show visible button labels or wrap buttons onto additional lines.
  Experienced users can recognize the icons and invoke an action directly.
- Keep accessible names on every button. Tooltips show the disabled reason,
  description, or action label, in that priority order. Preserve the `<span>`
  wrapper so disabled buttons still expose their tooltips.
- Size the action column to the widest currently rendered icon row, including
  cell padding. A page with only a few actions must not reserve a large fixed
  width. All rows in the same table retain a common column width for alignment.

Expanded mode trades table space for direct access. Keep the single icon row on
narrow screens and use the table's horizontal scrolling when necessary rather
than wrapping buttons or silently changing the preference. Menu mode remains
the option for visible labels and descriptions without hover.

### Why Not a Split Button

A split button that keeps one primary action visible and collapses the rest was
considered and rejected. Row actions across Portal have no consistent primary:
Update leads on InstanceAdmin, but other pages lead with navigation or with a
page-specific verb. Choosing a primary per page reintroduces the per-page
variation this design removes, so the two modes stay all-menu or all-buttons.

## One Shared Preference

| Setting | Contract |
| --- | --- |
| localStorage key | `portal.actionDisplay.v1` |
| Expanded buttons | String `"expanded"` |
| Menu | String `"menu"` |
| Missing or unrecognized value | Menu |
| Scope | All Portal pages on the same browser origin |

The value is a mode name rather than a boolean so a later third mode does not
require a second key or a key whose name no longer describes its values. The
`.v1` suffix matches the existing `portal.tablePageSize.v1:<userId>` key in
`usePersistentPagination` and leaves room to change the value set later.

This is a browser preference, not a user preference. Unlike page size, it is
deliberately **not** keyed by user ID: page size changes which rows a query
returns, so it resets on an account switch, while action display changes only
presentation and carries nothing across accounts that matters. It survives
navigation, reloads, and sign-out; accounts using the same browser profile and
origin share it. Other browsers and origins have their own localStorage, so
dev, test, and production each keep a separate value. No backend preference API
is required. Do not add a route, table, host, or user ID to the key.

### Control Placement

The preference is global, so it has exactly one control: a checkable
**Expanded buttons** item in the header profile menu, with **Action display ·
Applies to all pages** helper text. Checked selects Expanded; unchecked selects
Menu. The item participates in menu arrow-key navigation and toggles with Enter
or Space. Every Portal page exposes the same setting.

Per-page toolbar controls are deliberately excluded. A global setting repeated
in 86 toolbars costs space on the pages this design is meant to declutter, and
needs helper text on each copy to explain that it is not page-specific.
InstanceAdmin's top toolbar already carries Create, Compare, Clear selection,
selection chips, and an ownership label; a second entry point there earns
nothing. If discoverability proves to be a problem after rollout, a toolbar
control can be added later without changing the stored contract.

### State Provider

Add a typed `ActionDisplayProvider` and `useActionDisplay` hook under
`src/contexts/`, following the typed pattern in `UserContext` rather than the
untyped `LayoutContext`. Mount it in `main.tsx` inside `ThemeProvider` and
outside `UserProvider`, since the preference is not user-scoped.

1. Initialize the state from localStorage when the application starts.
2. On a mode change, update the shared React state immediately and persist the
   value. Already mounted consumers update without a reload.
3. Listen for the browser `storage` event to synchronize other tabs on the same
   origin. Ignore events for other keys. Treat `event.key === null`, which the
   browser sends for `clear()`, and removal of the key as a return to Menu.
4. If storage access fails, keep the control working through in-memory state
   for the current application session. A failed read or write must never throw
   out of the toggle or out of a table render.

The writing tab must update React state directly because its own localStorage
write does not generate a `storage` event in that tab. Switching modes closes
any open action menu without resetting filters, pagination, or row selection.

## Shared Action Component

Introduce a reusable `PortalActions` renderer and `ActionDisplayToggle`, backed
by the shared preference provider. Each page supplies action definitions:

```ts
type PortalAction<T> = {
  id: string;                        // stable, unique within the group
  label: string;                     // menu label and expanded accessible name
  description?: string;              // menu secondary line; omit rather than
                                     // repeat the label
  icon: React.ReactNode;
  destructive?: boolean;             // sorted last, below the divider
  hidden?: (row: T) => boolean;      // action does not apply to this record
  disabledReason?: (row: T) => string | null;  // null means enabled
  loading?: (row: T) => boolean;
  onSelect: (row: T) => void;        // existing handler or navigation callback
};
```

Actions render in list order. Hidden actions are omitted, so a row without the
`agt` actions closes the gap rather than reserving empty positions; alignment
across rows comes from consistent column sizing, not from fixed button slots.
Reserving positions for actions a record cannot use would add complexity for no
benefit, since the reserved slot carries no meaning to the reader.

Both modes consume the same definitions. Pages retain their business rules and
handlers; the shared renderer owns presentation and interaction. Custom table rows
and card action groups use the same renderer. Page-level and toolbar buttons
retain their visible text labels and do not use this renderer.

### Material React Table Integration

`PortalActions` renders inside the existing `renderRowActions` callback for both
modes. MRT's built-in `renderRowActionMenuItems` is a workable alternative for
menu mode alone: it returns `ReactNode[]`, so descriptions render fine. It does
not provide the labeled **Actions** trigger this design specifies, and it covers
only MRT row actions. Custom table rows and card action groups need the
same renderer regardless, so rendering both modes through `renderRowActions`
keeps one integration point across every migration rather than two paths to
maintain.

Render one `Menu` instance per table, anchored on demand with the active row
held in state. A closed MUI menu unmounts its children, so this is not about
idle DOM; it is about holding open/anchor state and item rendering in one place
so every row opens an identical menu.

Menu mode uses a consistent 120px action-column width. Expanded mode uses
content-based sizing instead of a fixed 360px width or a hand-maintained action
count on each page:

- `PortalActionScope` measures the rendered icon groups and actual cell padding,
  then applies the widest row's width to the action column. Hidden actions do
  not contribute to a row's measured width.
- Resize observation keeps measurements current when button visibility, row
  content, or table density changes. Removing the widest row lets the column
  shrink to the remaining rows, subject to a small minimum width.
- Header and body cells share the resulting width. Mixed `agt` and non-`agt`
  rows therefore remain aligned; shorter rows may have space left over only
  because another rendered row needs it.
- Native table layout reserves the content width rather than distributing spare
  table width into the action column. Resizable MRT grids use the measured pixel
  width. Native MUI tables use `PortalActionTableCell` with the same scope.
- Derive sizing from the rendered buttons, not a duplicated action-count literal
  or a fixed assumption about horizontal cell padding.

The shared `usePortalActionTableOptions` helper marks MRT action columns for this
sizing. ConfigUpdatePage's inline MRT configuration uses the same
`portalActionColumn` helper. Page-level toolbar buttons remain independent of this sizing, and catalog
lists share one scope around their cards.

Action column position stays as each page has it today. Roughly two thirds of
current call sites set `positionActionsColumn: 'first'` and the rest do not;
standardizing that is a separate change and is out of scope here.

### Availability and State

Hide actions that do not apply to a record. For example, agent actions appear
only when `productId === 'agt'`. Keep applicable but unavailable actions visible
and disabled. Preserve existing ownership, active/current/read-only checks,
loading indicators, confirmation dialogs, and task-aware navigation in both
modes.

Disabled actions must state their reason differently in each mode, because
disabled elements do not fire pointer events and cannot drive a tooltip:

- Menu mode renders the reason as inline secondary text on the disabled item.
- Expanded mode keeps the existing `<span>` wrapper around the disabled button
  so its tooltip still opens.

Opening the menu, or clicking an expanded button, must not toggle row selection
or fire the row click handler. Stop propagation at the trigger. InstanceAdmin's
Compare workflow depends on selection state that a stray toggle would corrupt.

### Interaction and Focus

Use accessible names, keyboard opening and navigation, visible focus, Escape to
close, and appropriate focus restoration. Menu labels and descriptions must also
work on touch devices without hover.

Actions that open a dialog need explicit ordering. MUI returns focus to the
menu's anchor when the menu closes, which can pull focus out of a dialog that
mounts in the same tick. Close the menu first, then open the dialog, so focus
lands and stays inside the dialog. Publish Agent policy on InstanceAdmin is the
first case of this.

## Scope and Rollout

Apply this pattern to row and card action groups throughout Portal. All page-level
and toolbar buttons retain their visible text labels in both display modes,
including Update Config Values, configuration sync, policy overview, snapshot
history, refresh status, catalog administration, profile editing, clone-result
links, and snapshot Copy/Download controls. Do not classify these buttons as
secondary actions to move them into the shared renderer. Create, Save, Cancel,
selection-based Compare, and other workflow controls also remain directly visible.

1. Add the shared preference, the header control, and the action components,
   then migrate InstanceAdmin with every existing action, including the two
   `agt` actions.
2. Inventory and migrate the remaining pages. The initial source survey found
   86 non-test components using `renderRowActions`; also inspect custom action
   columns and card action groups that do not use that callback.
3. Use the same display rules across the migrated pages. The rollout is complete
   when all applicable action groups use the shared pattern, not only
   InstanceAdmin.

### During the Rollout

The header control is added in step 1, so the preference is reachable from every
page from the start. Migrated pages respond to it; unmigrated pages keep their
current icon-only rows and ignore it. This mixed state is expected and
acceptable for the length of step 2. A single header control makes the mixed
state easier to explain than a control that appears on some pages only.

The description text for each action is written by whoever migrates that page,
as part of that page's migration. A migration is not complete while its actions
carry labels alone, except where a label is already self-explanatory.

### Holding the Pattern

After a page is migrated, nothing in the build prevents the next new page from
hand-rolling an action column again. Add a lint rule, or a line in the code
review checklist, that flags a `renderRowActions` implementation that does not
go through `PortalActions`.

### Rollback

Each page's migration is independent and revertible on its own. If the shared
renderer has to be withdrawn after several pages have migrated, the preference
and the header control can stay in place while individual pages revert, since
an unmigrated page simply ignores the flag. There is no data migration and no
stored state to unwind beyond a single localStorage key.

Per-page preferences, pinned favorites, custom action ordering, and backend
profile synchronization are outside this design.

## Testing

Unit tests, following the pattern in `usePersistentPagination.test.tsx`:

- The provider defaults to Menu with no stored value, an unrecognized value, a
  cleared key, and a `localStorage` accessor that throws.
- A `storage` event for `portal.actionDisplay.v1` updates the mode; an event for
  an unrelated key does not; `event.key === null` returns the mode to Menu.
- A write failure leaves the in-memory mode changed and does not throw.
- Both modes render the same action set from one definition list, including
  hidden, disabled, and loading actions.
- Selecting an action that opens a dialog leaves focus inside the dialog.
- Activating the trigger does not change row selection.
- Expanded buttons have accessible names but no visible labels and stay on one
  line.
- Action columns fit the widest visible button group, shrink when that row is
  removed, and account for actual padding and density in native and MRT tables.
- The header preference is reachable with arrow keys and toggles with Enter or
  Space.

## Acceptance Checks

- With no stored value, every applicable page uses Menu mode.
- Selecting Expanded buttons updates other mounted consumers, subsequently
  visited pages, and other open tabs on the same origin.
- Reloading preserves the mode; selecting Menu anywhere switches it back
  everywhere. Missing, invalid, cleared, or unavailable storage is handled.
- Both modes expose the same applicable actions and preserve their behavior,
  authorization checks, disabled states, loading states, and confirmations.
- A disabled action states its reason without hover in menu mode and on hover in
  expanded mode.
- Mixed `agt` and other-product rows remain aligned without button overlap in
  both modes.
- Pages with only a few expanded buttons have compact action columns with no
  large fixed blank area. Normal and resizable tables use the same sizing rule.
- Long menus scroll within the viewport. Expanded icon rows stay on one line
  and remain reachable through horizontal table scrolling on narrow screens.
- Menu labels and descriptions let keyboard and touch users identify actions
  without hover. Expanded icons retain accessible names and hover tooltips.
- Invoking an action that opens a dialog leaves focus inside the dialog.
- Switching modes preserves table filters, pagination, and selected rows.
- Opening a table of 100 rows in either mode shows no perceptible delay
  relative to the current implementation.

Page-level buttons preserve disabled-state explanations in tooltips, using a
span wrapper so disabled buttons can expose the reason. Delete buttons use
error styling to distinguish destructive actions from adjacent Edit or Update
buttons. These affordances apply in both action-display modes.
