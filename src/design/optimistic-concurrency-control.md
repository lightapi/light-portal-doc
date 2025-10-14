# Optimistic Concurrency Control (OCC)

In the previous document(./optimistic-pessimistic-ui.md), we have decided to leverage the OCC to prevent multiple users update the same aggregate at the same time from different browser sessions. 

With OCC, we have the single point of necessary trust: **the read model must be consistent *enough* to support the OCC check.**

The concern here is the core trade-off of CQRS: **Eventual Consistency.**

---

### The Problem: When Eventual Consistency Breaks OCC

Your system's flow is:

1.  **Read (UI):** Reads `ReadModel (V=5)` from Projection DB.
2.  **Write (Command Handler):**
    *   Command arrives with `expectedVersion=5`.
    *   Handler verifies against **Event Store** (Source of Truth): `EventStore.currentVersion` must be `5`.
3.  **The Stale Read Model Gap (The Problem):**
    *   Event `E6` is processed by the Command Handler and committed to `EventStore (V=6)`.
    *   *Before* the Consumer applies `E6` to the Projection DB, the UI reads.
    *   UI still reads `ReadModel (V=5)` (STALE).
    *   User submits `Command2 (expectedVersion=5)`.
    *   **The Conflict:** The Command Handler checks `EventStore.currentVersion` which is now **6**. It sees `6 != 5` and throws a **ConcurrencyException**.

**Result:** The user is incorrectly told there was a conflict and must refresh, even though their original read was perfectly valid and their change was submitted before any *other* user's command. The issue is that the read model was too slow to reflect the change that *already happened* in the source of truth.

---

### The Solution: Shift the OCC Check to the Event Store's Version

The best way to handle this and eliminate the dependency on the read model's consistency is to **ensure the UI's OCC is based on the authoritative version from the Event Store itself.**

Here are three practical options for injecting the authoritative version.

The "best" option balances **data consistency (critical)** against **performance and complexity (practical)**. Given the context of a high-performance CQRS/ES application, here is the evaluation and recommendation.

---

### Evaluation of Options for OCC Version Retrieval

| Option | Where Version is Fetched | Consistency Status | Performance Impact | Complexity | Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Join with `event_store_t` (Pagination Query)** | Read Model + Event Store | **Authoritative** (Best) | **High** (Slows down *every* page load, large joins are expensive). | High (Complex SQL, need to avoid full table scans). | **POOR** (Breaks Read Performance/Scalability). |
| **2. Button Click/Form Load** | Dedicated Version Service (Event Store) | **Authoritative** (Best) | **Low/Moderate** (1 extra, quick, targeted query per form load). | Low/Moderate (Easy to implement service). | **GOOD** (Decouples Read/Write, best UX). |
| **3. Command Submission** | Dedicated Version Service (Event Store) | **Authoritative** (Best) | **Low** (1 extra query per command). | Low/Moderate (Easy to implement service). | **GOOD but FLAWED UX** (Causes more false failures). |

---

### The Recommended Option: **Option 2 (Button Click / Form Load)**

**Fetch the authoritative version *when the user initiates the edit (button click / form load).***

#### Why Option 2 is the Best Balance:

1.  **Highest Consistency & UX:** It provides the highest level of consistency without sacrificing the performance of the common "list entities" query. When the user loads the edit form, they are guaranteed to see the latest version. If another user commits a change *before the form loads*, the user will see the newest data and version, preventing the immediate "false conflict."
2.  **Performance Preservation:** The most frequently executed query (`queryAllEntitiesWithPagination`) remains fast, hitting only the optimized Projection DB. The extra query (`VersionLookup`) only runs when a user takes the *action* to edit, which is a rare event compared to listing.
3.  **Simplicity:** It requires a simple, dedicated, fast endpoint in your backend (e.g., `/api/version/role/{id}`) that executes the `SELECT MAX(sequence_number) ...` query against your `event_store_t`.

---

### Why the Other Options Fail:

*   **Option 1 (Join with Pagination Query):** **Fails Scalability.** Joining a wide, paginated projection table with a potentially massive, ever-growing `event_store_t` table (even with indexes) is a performance killer. It makes every single query slow. You use CQRS to *avoid* this kind of cross-cutting query.
*   **Option 3 (Command Submission):** **Fails User Experience.**
    *   User loads data (Version 5).
    *   User spends 5 minutes making changes.
    *   *During those 5 minutes, another user commits V6 and V7.*
    *   User submits `Command (expectedVersion=5)`.
    *   Handler fetches latest version (V7). **Conflict: 7 != 5.**
    *   User is rejected and loses 5 minutes of work.
    *   *By contrast, Option 2 would have made the user refresh immediately upon clicking 'Edit' (because the version check would have failed then), saving the user from losing their work.*

---

### Implementation Flow for Option 2 (The Correct Flow)

1.  **UI/List View:** Populated from `Projection.queryEntities(offset, limit, filters)`. This query is fast and does **NOT** return the version (or returns the stale one, which is ignored).
2.  **User Action:** User clicks "Edit" button for `role_id=R1`.
3.  **Backend Call 1 (Version Check):** UI calls a dedicated endpoint: `/api/write/version/{aggregate_id}` (R1).
    *   **Backend:** Executes `SELECT MAX(sequence_number) FROM event_store_t WHERE aggregate_id = 'R1'`. Returns `currentVersion = V`.
    *   **Failure Check:** If the UI has cached data from V\_stale, you might perform a check here and prompt a refresh, but usually you just return V.
4.  **Backend Call 2 (Form Data):** UI calls `/api/read/role/{id}` to get fresh form data if needed (or uses data from the list).
5.  **UI Form:** Data is populated. A hidden field is set to `aggregateVersion = V`.
6.  **User Submission:** UI sends `UpdateCommand(..., expectedVersion=V)` to the command endpoint.
7.  **Command Handler:** Executes OCC check against the Event Store. **This check is now authoritative and highly likely to succeed.**



# Aggregate Version in Projection

Adding aggregate_version in all tables in read models is the most common, reliable, and scalable pattern to implement **Optimistic Concurrency Control (OCC)** in a CQRS/Event Sourcing system that uses a relational database for its read models.

---

### Confirmation of the OCC Pattern


| Component | Responsibility for OCC | Details |
| :--- | :--- | :--- |
| **Projection Tables (Read Model)** | **Store the Version** | **Required:** Must have an `aggregate_version` column (e.g., `BIGINT`) on every entity row that represents an Aggregate Root. |
| **Pagination/List Query (UI Read)** | **Retrieve the Version** | **Required:** The API endpoint for listing entities must include the `aggregate_version` column in its `SELECT` statement and return it to the UI. |
| **UI Form (Client)** | **Hold the Version** | **Required:** The UI must store this retrieved `aggregate_version` (often in a hidden field) and rename it to `expectedVersion` for the next command. |
| **Command Handler (Write Model)** | **Perform the Check** | **Required:** When the command arrives, check: `EventStore.actualVersion` **MUST EQUAL** `command.expectedVersion`. |

---

### Summary of Why This is Necessary

1.  **Atomicity of the Check:** The `aggregate_version` in the read model serves as the **handle** for the OCC check. The UI has to pass *some* authoritative marker of the state it observed.
2.  **Decoupling:** By having the version in the read model, you avoid performing costly `SELECT MAX(sequence_number)` queries against the `event_store_t` for every single row in the pagination result. Instead, you only perform the authoritative version lookup (or the OCC check itself) on the *one specific record* the user is attempting to modify.
3.  **Read/Write Split:** This solution maintains the separation of concerns:
    *   **Read Side:** Fast, optimized for retrieval.
    *   **Write Side:** Slow, transactionally consistent, responsible for the final state check.

---

### **Final Recommendation:**

**Yes, we must include `aggregate_version` in all projected tables that are used as the basis for user updates, and it must be part of the data retrieved by the UI's list queries.**

This is the non-negotiable step to ensuring your access control system prevents the dangerous "Last-Write-Wins" scenario.


# Refresh Data for Edit

We need to get the latest data after user click the 'Edit' button, there are two ways to get the lastet data: Read model or Replay. Let's clarify exactly what data consistency level is needed for the "Edit" form.

The answer is: **You should read the data from the Read Model (Projection) and retrieve the latest `aggregate_version` from the Event Store.**

You should **NOT** replay the Event Store to populate the UI form.

---

### Analysis of the Two Read Operations

| Operation | Source | Purpose | Consistency Level | Performance |
| :--- | :--- | :--- | :--- | :--- |
| **Data Retrieval** | **Read Model (`role_t` Projection)** | To populate the UI form fields (name, description, etc.). | **Eventual** (It's the data the user sees). | **Fast** (Single row lookup by PK). |
| **Version Retrieval** | **Event Store (`event_store_t`)** | To provide the authoritative `expectedVersion` for OCC. | **Strictly Authoritative** (Source of Truth). | **Fast** (Single `SELECT MAX(sequence_number) WHERE aggregate_id=?` query). |
| **Replay Operation** | **Event Store (`event_store_t`)** | To reconstruct the current state by re-running all events. | **Source of Truth** (Highest fidelity). | **Slow** (Involves reading many rows, deserialization, and business logic execution). |

---

### Why Combining Read Model + Version Lookup is Best

The flow for the `/api/read/role/{id}` endpoint should be:

1.  **Retrieve Authoritative Version:**
    *   Execute: `SELECT MAX(sequence_number) AS authoritative_version FROM event_store_t WHERE aggregate_id = ?`
    *   (This is fast).

2.  **Retrieve Data (The actual form fields):**
    *   Execute: `SELECT * FROM role_t WHERE role_id = ?`
    *   (This is also fast).

3.  **Combine and Return:**
    *   Return the data from the **Read Model** and replace the `aggregate_version` in the final JSON with the `authoritative_version` retrieved in Step 1.

    ```json
    // Final API Response
    {
      "roleId": "R1",
      "roleDesc": "...", // Data from Read Model
      "updateUser": "...", // Data from Read Model
      "aggregateVersion": [Authoritative_Version_from_ES] // Replaced version from Event Store
    }
    ```

#### Reasons for this Approach:

*   **Speed (Performance):** Replaying the Event Store is computationally expensive and slow. You would never do this for a simple read-to-populate-a-form scenario unless the Read Model was completely missing the data. Using the existing projected data for the form fields is orders of magnitude faster.
*   **Decoupling (Read/Write Split):** This maintains the CQRS separation. The Read Model is still the source for what is displayed to the user. The Event Store is only queried for the transactional anchor (`MAX(sequence_number)`).
*   **Consistency (High Enough):** By replacing the read model's version (`V_stale`) with the authoritative version (`V_authoritative`), you achieve **transactional consistency** for the critical OCC field, and **high eventual consistency** for the form data (since the event consumer should be very fast at updating the read model).

### What if the Read Model is Out of Sync?

The only time this approach is problematic is if the **read model is severely stale** (e.g., the consumer has been down for hours). In this case, the form data the user sees might not reflect the most recent events, even though the `aggregateVersion` is correct.

*   **Example:** Event E6 added a field `is_admin = true`. The consumer is down. The Read Model doesn't have `is_admin = true`. The UI loads the form, sets `aggregateVersion=V6`, but the form field for `is_admin` is missing.
*   **Mitigation:** The expectation in a healthy CQRS system is that the read model lag is measured in milliseconds, not minutes or hours. If lag is severe, the solution is to **fix the consumer and the Eventual Consistency pipeline**, not to slow down every read operation by resorting to full Event Replay.

**Conclusion:** **The solution is to mix and match:** Read data from the projection, but read the version from the source of truth (Event Store).

# Eventual Consistency Trade Off

**Availability/consistency trade-off** is the most nuanced and important philosophical point in CQRS/Event Sourcing.

It is correct that **Option 2 (Version Lookup on Button Click) temporarily breaks pure eventual consistency for the purpose of transactional integrity.**

Here is the detailed elaboration on why this is necessary and how it *redefines* the consistency boundary, rather than fundamentally destroying the trade-off.

---

### 1. The Principle of Eventual Consistency (EC)

*   **Definition:** The system state (Read Model) will eventually equal the Source of Truth (Write Model/Event Store) after a small delay ($\Delta t$).
*   **Trade-Off:** You trade strong/immediate consistency for high availability and high performance (speed of writes and reads).
*   **The Acceptable Lie:** The Read Model is allowed to lie for $\Delta t$ seconds.

### 2. The Unacceptable Lie: Breaking Transactional Integrity

The moment a user wants to perform a **write operation**, the system must enforce **Strong Consistency** for that single transaction, regardless of the CQRS pattern.

*   **Goal of the Transaction:** To guarantee that the command (write) is based on a known, singular, correct state of the Aggregate.
*   **The Problem:** If we use the **stale** version from the Projection DB (`V_stale`), and the **Write Model** is at `V_authoritative`, one of two things happens:
    1.  **If `V_authoritative > V_stale` (Stale Read):** The command is rejected (correctly by the Command Handler's OCC check). The user is told to refresh.
    2.  **If we tried to bypass OCC:** A new event is generated based on stale data, potentially creating an invalid state (e.g., inventory going negative). This is a **data integrity failure.**

**Conclusion:** For the **Write Path**, you must have **Strong Consistency**. The Write Path does not participate in the EC trade-off.

### 3. Why Option 2 is the Best Synthesis (The Redefined Trade-Off)

Option 2 queries Projection *AND* Event Store) is a controlled and highly localized violation of pure EC that elevates transactional integrity.

| Operation | Consistency Mechanism | Status |
| :--- | :--- | :--- |
| **A. List View** | **Eventual Consistency (EC)** | Hits Projection DB only. Fast. Can be stale. $\checkmark$ |
| **B. Button Click/Form Load** | **Read-Your-Own-Writes Consistency (RYOW) / Strong Consistency** | **Hits Event Store for Version ONLY.** Checks `V_stale` against `V_authoritative`. If `V_stale < V_authoritative`, the read is aborted, forcing a fresh, consistent read for the form. $\checkmark$ |
| **C. Command Submission** | **Optimistic Concurrency Control (OCC) / Strong Consistency** | Hits Event Store for the final check. **Guarantees data integrity.** $\checkmark$ |

#### The "Controlled Violation" Justification

1.  **Only for the Edit Form:** The slow, authoritative query is only done for one Aggregate when a user chooses to edit it. This minimizes performance impact.
2.  **Only for the Version:** The authoritative query (`SELECT MAX(sequence_number)`) is the lightest possible query against the Event Store, ensuring minimum latency for this strong consistency check. It doesn't incur the cost of full Event Replay or full Projection DB reads.
3.  **Redefining the UX Contract:** You are establishing a clear contract: "The List View is for quick display (EC). The Edit Form guarantees that the state you see is the last known state, and we checked the Source of Truth just for you (Strong Consistency)."

**The Availability Trade-off is NOT Broken:**

*   **Availability:** The Write Model (Command Handler) is still available. The Read Model (Projection) is still available. The system has not halted.
*   **Performance:** The List View remains fast (available). The Write Path remains fast (available).
*   **The Cost:** The cost is one extra, fast, authoritative query right before the edit begins, which is a small price to pay for preventing a major data integrity or user experience failure.

### Summary

The pattern you are implementing with **Option 2 (Projection Data + Event Store Version)** is the **standard, correct way to implement OCC across the Read-Write boundary** in a performant CQRS/ES system. It is a necessary local "tightening" of the eventual consistency model to ensure transactional correctness where it absolutely matters: at the point of data modification.

