## Soft Delete vs Hard Delete

Here is a classic problem in Event Sourcing, often related to the concept of **"soft deletes" or "state transitions" versus "hard deletes" and re-insertions**. The core issue is that `aggregate_version` must be strictly unique for a given aggregate. If you try to re-insert an aggregate at an old version, it fundamentally violates Event Sourcing principles.

Let's break down the scenario and the best ways to handle it.

---

### The Problem Scenario: Version Conflict on Re-add

Your scenario:
1.  `UserHostCreatedEvent (userId=U, hostId=H, aggregate_version=1)` -> `event_store_t` has version 1. `user_host_t` (projection) has version 1.
2.  `UserHostDeletedEvent (userId=U, hostId=H, aggregate_version=2)` -> `event_store_t` has version 2. `user_host_t` either deletes or marks as inactive.
3.  `UserHostCreatedEvent (userId=U, hostId=H, aggregate_version=1)` -> **CONFLICT!** This event says the aggregate `(U,H)` is at version 1 again, but `event_store_t` already has version 2 for `(U,H)`.

**Root Cause:** You cannot "re-add" an aggregate at an old version. An aggregate's version always strictly increases. The action of "adding back" is not a "first time add" in the event history; it's a *new* state transition.

---

### Best Ways to Handle This Kind of Scenario

The solution involves redefining what "add back" means in an Event Sourcing context and how your aggregates and projections handle it.

#### Option 1: State Transitions (Recommended for your scenario)

This is the most common and robust approach. Instead of thinking of "add" and "remove" as discrete CRUD operations on a single record, think of them as **state changes** of an aggregate instance that *always exists*.

**Aggregate Design (Conceptual `UserHostMapping` Aggregate):**

*   An aggregate representing the **state of a `(User, Host)` relationship** (e.g., `UserHostMappingAggregate(userId, hostId)`).
*   It has a state, e.g., `ACTIVE`, `INACTIVE`.
*   The `aggregate_id` for this aggregate would be a **composite ID** (e.g., `userId + "-" + hostId` or a UUID that represents this specific mapping).
*   It has a `version` (sequence number).

**Event Types:**

*   `UserHostActivatedEvent (userId, hostId, sequence_number)`
*   `UserHostDeactivatedEvent (userId, hostId, sequence_number)`

**Scenario with State Transitions:**

1.  **Add Host to User Mapping (First Time):**
    *   Command: `ActivateUserHostMapping(userId=U, hostId=H, expectedVersion=0)` (Expected version 0 because it doesn't exist yet).
    *   Aggregate `(U,H)`: Generates `UserHostActivatedEvent (userId=U, hostId=H, sequence_number=1)`.
    *   `event_store_t`: Saves version 1.
    *   `user_host_t` (projection): **INSERTS** record `(U, H, status=ACTIVE, aggregate_version=1)`.

2.  **Remove Host to User Mapping:**
    *   Command: `DeactivateUserHostMapping(userId=U, hostId=H, expectedVersion=1)`.
    *   Aggregate `(U,H)`: Generates `UserHostDeactivatedEvent (userId=U, hostId=H, sequence_number=2)`.
    *   `event_store_t`: Saves version 2.
    *   `user_host_t` (projection): **UPDATES** record `(U, H)` to `status=INACTIVE, aggregate_version=2`. (Doesn't delete the row).

3.  **Add Back the Same Host to User Mapping:**
    *   Command: `ReactivateUserHostMapping(userId=U, hostId=H, expectedVersion=2)`. (Expected version 2 because it's currently INACTIVE at version 2).
    *   Aggregate `(U,H)`: Generates `UserHostActivatedEvent (userId=U, hostId=H, sequence_number=3)`.
    *   `event_store_t`: Saves version 3.
    *   `user_host_t` (projection): **UPDATES** record `(U, H)` to `status=ACTIVE, aggregate_version=3`.

**Benefits of State Transitions:**

*   **Strictly Monotonic Versions:** The `sequence_number` for the `UserHostMapping` aggregate (`U,H`) always increases (0 -> 1 -> 2 -> 3). No version conflicts.
*   **Complete History:** The Event Store clearly shows the activation/deactivation cycle.
*   **Simpler Projection:** The projection (`user_host_t`) never deletes rows; it only updates their status and version. This makes updates simple (`UPDATE ... WHERE aggregate_id = ? AND aggregate_version = ?`) and avoids `INSERT` conflicts on "re-add."
*   **Idempotent Read Model Updates:** The consumer logic is straightforward.

#### Option 2: Unique ID for Each Relationship Instance (Less common for simple toggles)

*   **Approach:** Instead of `(U,H)` being one aggregate that changes status, you treat each "active period" of `(U,H)` as a new, distinct aggregate.
*   `aggregate_id`: A brand new UUID for *each activation* of `(U,H)`.
*   Event Types:
    *   `UserHostCreatedEvent (mappingId=M1, userId=U, hostId=H, sequence_number=1)`
    *   `UserHostDeletedEvent (mappingId=M1, userId=U, hostId=H, sequence_number=2)`
    *   `UserHostCreatedEvent (mappingId=M2, userId=U, hostId=H, sequence_number=1)` (for the second time)
*   **Projection:** The `user_host_t` table would track these `mappingId`s, possibly with `start_ts` and `end_ts`. When a mapping is terminated, you update its `end_ts`. When "added back," you insert a new row with a new `mappingId`.
*   **Complexity:** Managing which `mappingId` is current for `(U,H)` can be tricky. It's usually overkill for simple active/inactive toggles.

#### Option 3: History Table for User Host Mapping
* **Approach:** Create a user_host_history_t to keep a history of UserHostMapping. 
* **Projection:** The `user_host_t` and `user_host_history_t` join together for the query with both snapshot and historical views. 
* **Complexity:** Managing both original and historical tables is overkill in this use case unless you need historical query very frequently. 

---

### Recommended Approach for your `user_host_t` scenario

**Go with Option 1: State Transitions for a `(User, Host)` Aggregate.**

**Detailed Changes:**

1.  **Database Schema for `user_host_t`:**
    *   Add a `status` column (e.g., `VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'`).
    *   Ensure `aggregate_version` column exists.
    *   Primary key/unique constraint likely remains `(host_id, user_id)`.

    ```sql
    ALTER TABLE user_host_t
    ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN aggregate_version BIGINT NOT NULL DEFAULT 0;

    -- Add a unique constraint if not already present on (host_id, user_id)
    -- ALTER TABLE user_host_t ADD CONSTRAINT pk_user_host PRIMARY KEY (host_id, user_id);
    ```

2.  **Define specific Event Types:**
    *   `UserHostActivatedEvent`
    *   `UserHostDeactivatedEvent`

3.  **Command Handling Logic (Write Model):**
    *   When the "add host to user" command comes in:
        *   Load the `UserHostMapping` aggregate (identified by `(host_id, user_id)`).
        *   If not found (expectedVersion 0), generate `UserHostActivatedEvent`.
        *   If found and `status=INACTIVE` (expectedVersion > 0), generate `UserHostActivatedEvent`.
        *   If found and `status=ACTIVE` (expectedVersion > 0), reject (already active, idempotent no-op).
    *   When the "remove host from user" command comes in:
        *   Load the `UserHostMapping` aggregate.
        *   If not found or `status=INACTIVE`, reject (already inactive/not found).
        *   If `status=ACTIVE`, generate `UserHostDeactivatedEvent`.

4.  **`PortalEventConsumer` Logic (Read Model Update):**

    *   **For `UserHostActivatedEvent`:**
        *   This event means the mapping is now active.
        *   Try to `UPDATE user_host_t SET status='ACTIVE', aggregate_version=? WHERE host_id=? AND user_id=? AND aggregate_version=?`.
        *   If 0 rows updated:
            *   Check if the record exists (`SELECT COUNT(*) ...`).
            *   If it exists (and version didn't match), it's a `ConcurrencyException`.
            *   If it *doesn't* exist, it's the *very first time* this mapping became active, so `INSERT INTO user_host_t (...) VALUES (...)`.
        *   This will handle both initial creation and reactivation as idempotent updates/inserts based on state.

    *   **For `UserHostDeactivatedEvent`:**
        *   This event means the mapping is now inactive.
        *   `UPDATE user_host_t SET status='INACTIVE', aggregate_version=? WHERE host_id=? AND user_id=? AND aggregate_version=?`.
        *   If 0 rows updated, it's either `ConcurrencyException` or "not found" (already inactive).

This approach treats the `user_host_t` relationship as a single logical entity (an aggregate instance) that transitions through states (`ACTIVE`/`INACTIVE`), ensuring the `aggregate_version` always progresses monotonically and avoiding the conflict you described.


## Command Handler Logic

It is crucial to figure out the db logic between the read model (what the UI sees) and the command model (what the command handler needs to decide). The command handler cannot rely solely on the UI's `expectedVersion` in this scenario. It needs to query its own source of truth (the Event Store) to decide if it's an "initial activation" or a "reactivation."

Let's refine the command handling logic for the `UserHostMapping` aggregate.

---

### Key: The Command Handler Owns the Decision, Using the Event Store

The command handler's job is to:
1.  **Load the aggregate's current state** (by replaying events from `event_store_t`).
2.  **Determine its *current status* and *current version*** based on that replay.
3.  **Compare the `expectedVersion` from the command** with the aggregate's `currentVersion`.
4.  **Apply business rules** to decide what event(s) to generate.

#### Event Types & Aggregate ID (as per previous recommendation)

*   **Aggregate ID:** A composite of `hostId` and `userId` (e.g., `hostId + "_" + userId`).
*   **Events:**
    *   `UserHostActivatedEvent`: Represents the relationship becoming active.
    *   `UserHostDeactivatedEvent`: Represents the relationship becoming inactive.

---

### Step-by-Step Command Handling Logic

Let's assume your command handler is `UserHostMappingCommandHandler` and it interacts with a `UserHostMappingAggregate`.

**1. `UserHostMappingAggregate` (Internal Logic):**

This aggregate needs to rebuild its state (`currentStatus`, `currentVersion`) from its event stream.

```java
public class UserHostMappingAggregate {
    private final String hostId;
    private final String userId;
    private UserHostMappingStatus currentStatus; // Enum: ACTIVE, INACTIVE, NON_EXISTENT
    private long currentVersion; // Sequence number of the last applied event

    private List<DomainEvent> uncommittedEvents = new ArrayList<>();

    public UserHostMappingAggregate(String hostId, String userId) {
        this.hostId = hostId;
        this.userId = userId;
        this.currentStatus = UserHostMappingStatus.NON_EXISTENT; // Initial state
        this.currentVersion = 0;
    }

    public static UserHostMappingAggregate loadFromEvents(String hostId, String userId, List<DomainEvent> history) {
        UserHostMappingAggregate aggregate = new UserHostMappingAggregate(hostId, userId);
        if (history != null && !history.isEmpty()) {
            history.forEach(aggregate::applyEvent);
        }
        return aggregate;
    }

    private void applyEvent(DomainEvent event) {
        if (event instanceof UserHostActivatedEvent) {
            this.currentStatus = UserHostMappingStatus.ACTIVE;
        } else if (event instanceof UserHostDeactivatedEvent) {
            this.currentStatus = UserHostMappingStatus.INACTIVE;
        }
        this.currentVersion = event.getSequenceNumber(); // Update version based on event
    }

    // --- Command Handling Methods ---

    public void activateMapping(long expectedVersion) {
        // OCC Check (optional here, but good practice if not relying solely on DB constraint)
        if (this.currentVersion != expectedVersion) {
            throw new ConcurrencyException("Concurrency conflict. Expected version " + expectedVersion + ", actual " + this.currentVersion);
        }

        // Business Logic: What state must it be in to activate?
        if (this.currentStatus == UserHostMappingStatus.ACTIVE) {
            // Already active, idempotent no-op or reject as invalid transition
            logger.info("Mapping for user {} host {} is already active. No new event generated.", userId, hostId);
            return;
        }

        // Generate new event
        long nextVersion = this.currentVersion + 1;
        UserHostActivatedEvent event = new UserHostActivatedEvent(
            UUID.randomUUID(), Instant.now(), getAggregateId(), "UserHostMapping", nextVersion, hostId, userId
        );
        uncommittedEvents.add(event);
        applyEvent(event); // Apply to internal state immediately for consistency
    }

    public void deactivateMapping(long expectedVersion) {
        // OCC Check
        if (this.currentVersion != expectedVersion) {
            throw new ConcurrencyException("Concurrency conflict. Expected version " + expectedVersion + ", actual " + this.currentVersion);
        }

        // Business Logic
        if (this.currentStatus != UserHostMappingStatus.ACTIVE) {
            logger.info("Mapping for user {} host {} is not active. Cannot deactivate.", userId, hostId);
            throw new IllegalStateException("Mapping is not active and cannot be deactivated.");
        }

        // Generate new event
        long nextVersion = this.currentVersion + 1;
        UserHostDeactivatedEvent event = new UserHostDeactivatedEvent(
            UUID.randomUUID(), Instant.now(), getAggregateId(), "UserHostMapping", nextVersion, hostId, userId
        );
        uncommittedEvents.add(event);
        applyEvent(event);
    }
    
    // Helper to get the composite aggregate ID
    public String getAggregateId() {
        return hostId + "_" + userId; // Consistent composite ID
    }

    // Getters for external access
    public UserHostMappingStatus getCurrentStatus() { return currentStatus; }
    public long getCurrentVersion() { return currentVersion; }
    public List<DomainEvent> getUncommittedEvents() { return uncommittedEvents; }
    public void markEventsCommitted() { uncommittedEvents.clear(); }

    public enum UserHostMappingStatus {
        ACTIVE, INACTIVE, NON_EXISTENT
    }
}
```

**2. `UserHostMappingCommandHandler` (Application Service):**

This is where the command logic happens. The key is that the command from the UI is now generic (e.g., `SetUserHostMappingStatus`).

```java
public class UserHostMappingCommandHandler { // This is your application service
    private final EventStoreEventRepository eventStoreRepository; // To load events
    private final OutboxMessageRepository outboxRepository;     // To save new events

    // Constructor injection
    // ...

    public void handleSetUserHostMappingStatus(String hostId, String userId, boolean activate, long expectedVersionFromUI) {
        String aggregateId = hostId + "_" + userId;
        
        // 1. Load aggregate state from Event Store
        List<DomainEvent> history = eventStoreRepository.findByAggregateIdOrderBySequenceNumberAsc(aggregateId)
                                       .stream()
                                       .map(this::deserializeEventStoreEvent) // Deserialize from DB format
                                       .collect(Collectors.toList());
        UserHostMappingAggregate aggregate = UserHostMappingAggregate.loadFromEvents(hostId, userId, history);

        // 2. Perform business logic based on intent (activate) and current state
        if (activate) {
            aggregate.activateMapping(expectedVersionFromUI); // Will generate UserHostActivatedEvent
        } else {
            aggregate.deactivateMapping(expectedVersionFromUI); // Will generate UserHostDeactivatedEvent
        }

        // 3. Persist new events
        List<DomainEvent> newEvents = aggregate.getUncommittedEvents();
        if (!newEvents.isEmpty()) {
            // Your transactional outbox logic (save to Event Store and Outbox)
            eventStoreRepository.saveAll(newEvents.stream().map(this::mapToEventStoreEvent).collect(Collectors.toList()));
            outboxRepository.saveAll(newEvents.stream().map(this::mapToOutboxMessage).collect(Collectors.toList()));
            aggregate.markEventsCommitted();
        }
    }
    
    // Helper methods for serialization/deserialization as shown in previous examples
    // ...
}
```

**3. `PortalEventConsumer` Logic (Read Model Update):**

The consumer updates `user_host_t` based on the events.

*   **For `UserHostActivatedEvent`:**
    ```java
    // In your PortalEventConsumer (inside processSingleEventWithRetries for this event type)
    Map<String, Object> eventData = extractEventData(eventMap);
    String hostId = (String) eventMap.get(Constants.HOST); // Assuming hostId is a CE extension
    String userId = (String) eventMap.get(Constants.USER); // Assuming userId is a CE extension
    String aggregateId = (String) eventMap.get(CloudEventV1.SUBJECT); // Or extract from eventData if set as such
    long newVersion = getEventSequenceNumber(eventMap);

    // SQL: UPSERT is ideal here. If record exists, update status/version. If not, insert.
    // This handles both initial activation (INSERT) and reactivation (UPDATE) idempotently.
    final String upsertSql = "INSERT INTO user_host_t (host_id, user_id, status, aggregate_version, update_user, update_ts) " +
                             "VALUES (?, ?, ?, ?, ?, ?) " +
                             "ON CONFLICT (host_id, user_id) DO UPDATE SET " +
                             "status = EXCLUDED.status, " +
                             "aggregate_version = EXCLUDED.aggregate_version, " +
                             "update_user = EXCLUDED.update_user, " +
                             "update_ts = EXCLUDED.update_ts " +
                             "WHERE user_host_t.aggregate_version < EXCLUDED.aggregate_version"; // Only update if incoming event is newer

    try (PreparedStatement statement = conn.prepareStatement(upsertSql)) {
        statement.setObject(1, UUID.fromString(hostId));
        statement.setObject(2, UUID.fromString(userId));
        statement.setString(3, UserHostMappingAggregate.UserHostMappingStatus.ACTIVE.name());
        statement.setLong(4, newVersion);
        statement.setString(5, (String)eventMap.get(Constants.USER)); // From CE extension
        statement.setObject(6, OffsetDateTime.parse((String)eventMap.get(CloudEventV1.TIME)));
        statement.executeUpdate();
    }
    ```
    *   **Crucial `ON CONFLICT ... WHERE user_host_t.aggregate_version < EXCLUDED.aggregate_version`:** This makes the projection update idempotent and handles out-of-order delivery. If the database already has a *newer* version than the incoming event, it simply does nothing (`0 rows affected`), preventing a stale event from overwriting a more recent state.

*   **For `UserHostDeactivatedEvent`:**
    ```java
    // In your PortalEventConsumer (inside processSingleEventWithRetries for this event type)
    Map<String, Object> eventData = extractEventData(eventMap);
    String hostId = (String) eventMap.get(Constants.HOST);
    String userId = (String) eventMap.get(Constants.USER);
    long newVersion = getEventSequenceNumber(eventMap);

    final String updateSql = "UPDATE user_host_t SET status='INACTIVE', aggregate_version=?, update_user=?, update_ts=? " +
                             "WHERE host_id = ? AND user_id = ? AND aggregate_version < ?"; // Only update if incoming event is newer

    try (PreparedStatement statement = conn.prepareStatement(updateSql)) {
        statement.setLong(1, newVersion);
        statement.setString(2, (String)eventMap.get(Constants.USER));
        statement.setObject(3, OffsetDateTime.parse((String)eventMap.get(CloudEventV1.TIME)));
        statement.setObject(4, UUID.fromString(hostId));
        statement.setObject(5, UUID.fromString(userId));
        statement.setLong(6, newVersion); // Only update if current DB version < newVersion (from event)
        statement.executeUpdate();
    }
    ```

---

### How to Figure it Out in the Command Handler (from UI perspective)

The UI will initially query the `user_host_t` read model.

*   **Scenario A: UI queries, no record for `(U,H)` found.**
    *   UI infers state is "Non-Existent" or "Inactive".
    *   UI provides `expectedVersion = 0` to the command (because the read model had no entry).
    *   Command handler: `aggregate.currentStatus == NON_EXISTENT`. Generates `UserHostActivatedEvent (sequence_number=1)`.

*   **Scenario B: UI queries, record `(U,H, status=ACTIVE, aggregate_version=1)` found.**
    *   UI provides `expectedVersion = 1` to the command.
    *   User wants to "remove."
    *   Command handler: `aggregate.currentStatus == ACTIVE`. Generates `UserHostDeactivatedEvent (sequence_number=2)`.

*   **Scenario C: UI queries, record `(U,H, status=INACTIVE, aggregate_version=2)` found.** (This assumes your UI *could* list inactive items, or an admin UI can see it.)
    *   UI provides `expectedVersion = 2` to the command.
    *   User wants to "add back" / "reactivate."
    *   Command handler: `aggregate.currentStatus == INACTIVE`. Generates `UserHostActivatedEvent (sequence_number=3)`.

*   **Crucial UI Aspect:** If the UI doesn't display inactive items (which is typical for a "list active" view), and the user tries to "add" an item that *used to exist but is now inactive*, the UI would initially send `expectedVersion = 0`.
    *   Command handler receives `expectedVersion = 0`, but aggregate is actually `INACTIVE` at `version=2`.
    *   **OCC Conflict!** `aggregate.currentVersion (2) != expectedVersion (0)`. Command is rejected.
    *   **User Experience:** "Cannot add. This mapping exists in an inactive state. Please activate it instead." This forces a clearer UI workflow.

By leveraging state transitions within your aggregate and using `ON CONFLICT` / `WHERE aggregate_version < EXCLUDED.aggregate_version` in your projection updates, you ensure strict versioning, idempotent read models, and a consistent business logic flow.
