# Database Concurrency

Multiple users updating the same aggregate is a classic concurrency problem in multi-user applications, often referred to as the "lost update" problem. In an Event Sourcing system, preventing this overwrite is crucial because the sequence of events defines the state.

The standard and most effective way to prevent concurrent updates from overwriting each other in an Event Sourcing system is through **Optimistic Concurrency Control (OCC)**, specifically using **version numbers (or sequence numbers) at the aggregate level.**

---

### How Optimistic Concurrency Control (OCC) Works in Event Sourcing

1.  **Version Tracking (Sequence Number):**
    *   Every Aggregate (e.g., a `Customer`, an `Order`, a `Product`) has a version, which is typically its **current sequence number** in the event stream. This sequence number represents the number of events that have been applied to build its current state.
    *   Your `events_store_t` table already has `sequence_number` for this purpose:
        ```sql
        CREATE TABLE events_store_t (
            id UUID PRIMARY KEY,
            aggregate_id VARCHAR(255) NOT NULL,
            -- ... other fields ...
            sequence_number BIGINT NOT NULL,       -- This is the key!
            UNIQUE (aggregate_id, sequence_number) -- CRITICAL constraint!
        );
        ```
        The `UNIQUE (aggregate_id, sequence_number)` constraint is the fundamental database-level guarantee against concurrent writes for the same aggregate at the same version.

2.  **Load the Aggregate's Current Version:**
    *   When your application service wants to modify an aggregate, it first loads the aggregate's current state by replaying all events for that `aggregate_id` from the `events_store_t`.
    *   During this replay, it tracks the `currentSequenceNumber` (the sequence number of the *last* event applied).

3.  **Pass Expected Version with Command:**
    *   The user interface (UI) or the client application that initiated the change should also hold the `currentSequenceNumber` it *observed* when it last fetched the aggregate's state.
    *   This `expectedVersion` (or `expectedSequenceNumber`) is then sent along with the command (e.g., `UpdateCustomerProfileCommand(customerId, newName, newAddress, expectedSequenceNumber)`).

4.  **Conditional Event Appending:**
    *   When your `CustomerApplicationService` receives the command:
        *   It loads the `Customer` aggregate from the `events_store_t`, determining its *actual* `currentSequenceNumber`.
        *   It compares the `command.expectedSequenceNumber` with the `customer.actualCurrentSequenceNumber` (derived from the Event Store).
        *   **If `command.expectedSequenceNumber` does NOT match `customer.actualCurrentSequenceNumber`:** This means another concurrent transaction has already written new events for this aggregate *since the client loaded its state*. A `ConcurrencyException` (or similar domain-specific exception) is thrown.
        *   **If they DO match:** The aggregate's business logic is applied, generating new events. These new events will have `customer.actualCurrentSequenceNumber + 1`, `customer.actualCurrentSequenceNumber + 2`, etc.

5.  **Atomic Persistence (The DB Constraint):**
    *   The new events are then attempted to be saved to `events_store_t` (and `outbox_messages`) within a single database transaction.
    *   If a concurrency conflict was *not* detected at step 4 (meaning two commands arrived almost simultaneously and passed the initial check), the `UNIQUE (aggregate_id, sequence_number)` constraint in the `events_store_t` table will prevent the "lost update." Only the first transaction to successfully insert events with the "next" sequence numbers will succeed. The second will fail with a `DataIntegrityViolationException` (or similar).

### Example Flow:

1.  **User A** fetches `Customer-123`. The current state (replayed from `events_store_t`) shows `sequenceNumber = 5`.
2.  **User B** also fetches `Customer-123`. It also sees `sequenceNumber = 5`.
3.  **User A** sends `UpdateCustomerProfileCommand(customerId="123", newName="Alice", expectedSequenceNumber=5)`.
    *   App Service loads `Customer-123`, actual `sequenceNumber = 5`. Matches `expectedSequenceNumber`.
    *   Generates `CustomerNameChanged` event with `sequenceNumber = 6`.
    *   Attempts to save event(s) to `events_store_t` (and `outbox_messages`). **Succeeds.**
4.  **User B** sends `UpdateCustomerProfileCommand(customerId="123", newAddress="456 Oak", expectedSequenceNumber=5)`.
    *   App Service loads `Customer-123`. It now replays events up to `sequenceNumber = 6`. So, `actualSequenceNumber = 6`.
    *   It compares `command.expectedSequenceNumber=5` with `customer.actualSequenceNumber=6`. **They do NOT match!**
    *   The `CustomerApplicationService` throws a `ConcurrencyException`.
    *   The transaction is rolled back, and no events are written from User B's command.

### Java Implementation Changes

Let's modify the previous `CustomerApplicationService` and add a way to load the aggregate from events.

#### 1. `Customer` Aggregate (Revised)

```java
// domain/Customer.java (Revised)
package com.example.eventoutbox.domain;

import com.example.eventoutbox.domain.events.CustomerAddressChanged;
import com.example.eventoutbox.domain.events.CustomerNameChanged;
import com.example.eventoutbox.domain.events.DomainEvent;
import lombok.Getter;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Getter
public class Customer {
    private final String customerId;
    private String name;
    private String address;
    private long version; // This is the 'sequenceNumber' of the LAST applied event

    private final List<DomainEvent> uncommittedEvents = new ArrayList<>();

    // Constructor for creating a new aggregate
    public Customer(String customerId) {
        this.customerId = customerId;
        this.version = 0; // New aggregates start at version 0
    }

    // Static factory method to load an aggregate from its events
    public static Customer loadFromEvents(String customerId, List<DomainEvent> history) {
        Customer customer = new Customer(customerId);
        history.forEach(customer::applyEvent); // Apply each historical event
        return customer;
    }

    // Method to apply an event to the aggregate's state
    private void applyEvent(DomainEvent event) {
        // This is where you would update the aggregate's internal state
        // based on the specific event type.
        if (event instanceof CustomerNameChanged nameChanged) {
            this.name = nameChanged.getNewName();
        } else if (event instanceof CustomerAddressChanged addressChanged) {
            this.address = addressChanged.getNewAddress();
        }
        this.version = event.getSequenceNumber(); // Update version to the sequence number of the applied event
    }

    // Domain behavior methods that generate new events
    public void changeName(String newName) {
        if (!newName.equals(this.name)) {
            // New events get the *next* sequence number
            long nextSequence = this.version + 1;
            CustomerNameChanged event = new CustomerNameChanged(UUID.randomUUID(), Instant.now(), customerId, nextSequence, newName);
            uncommittedEvents.add(event);
            applyEvent(event); // Apply immediately to current state for consistency
        }
    }

    public void changeAddress(String newAddress) {
        if (!newAddress.equals(this.address)) {
            long nextSequence = this.version + 1;
            CustomerAddressChanged event = new CustomerAddressChanged(UUID.randomUUID(), Instant.now(), customerId, nextSequence, newAddress);
            uncommittedEvents.add(event);
            applyEvent(event);
        }
    }

    public void markEventsCommitted() {
        this.uncommittedEvents.clear();
    }
}
```

#### 2. `ConcurrencyException`

```java
// domain/ConcurrencyException.java
package com.example.eventoutbox.domain;

public class ConcurrencyException extends RuntimeException {
    public ConcurrencyException(String message) {
        super(message);
    }
}
```

#### 3. `CustomerApplicationService` (Revised)

```java
// application/CustomerApplicationService.java (Revised)
package com.example.eventoutbox.application;

import com.example.eventoutbox.domain.ConcurrencyException;
import com.example.eventoutbox.domain.Customer;
import com.example.eventoutbox.domain.events.DomainEvent;
import com.example.eventoutbox.infrastructure.persistence.eventstore.EventStoreEvent;
import com.example.eventoutbox.infrastructure.persistence.eventstore.EventStoreEventRepository;
import com.example.eventoutbox.infrastructure.persistence.outbox.OutboxMessage;
import com.example.eventoutbox.infrastructure.persistence.outbox.OutboxMessageRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CustomerApplicationService {

    private final OutboxMessageRepository outboxMessageRepository;
    private final EventStoreEventRepository eventStoreEventRepository;
    private final ObjectMapper objectMapper;

    // Command now includes expectedVersion
    public record UpdateCustomerProfileCommand(String customerId, String newName, String newAddress, long expectedVersion) {}

    @Transactional
    public void updateCustomerProfile(UpdateCustomerProfileCommand command) {
        // --- 1. Load Aggregate State ---
        List<EventStoreEvent> historicalEvents = eventStoreEventRepository.findByAggregateIdOrderBySequenceNumberAsc(command.customerId());

        Customer customer;
        if (historicalEvents.isEmpty()) {
            customer = new Customer(command.customerId());
            // If it's a new aggregate, expectedVersion must be 0
            if (command.expectedVersion() != 0) {
                 throw new ConcurrencyException("Customer with ID " + command.customerId() + " does not exist or expected version is incorrect.");
            }
        } else {
            // Deserialize historical events to DomainEvent objects
            List<DomainEvent> domainEventsHistory = historicalEvents.stream()
                .map(this::deserializeEventStoreEvent)
                .collect(Collectors.toList());
            customer = Customer.loadFromEvents(command.customerId(), domainEventsHistory);

            // --- 2. OPTIMISTIC CONCURRENCY CHECK ---
            if (customer.getVersion() != command.expectedVersion()) {
                throw new ConcurrencyException(
                    "Customer with ID " + command.customerId() + " has been updated by another user. " +
                    "Expected version " + command.expectedVersion() + " but found " + customer.getVersion() + "."
                );
            }
        }

        // --- 3. Apply Business Logic & Generate Events ---
        if (command.newName() != null) {
            customer.changeName(command.newName());
        }
        if (command.newAddress() != null) {
            customer.changeAddress(command.newAddress());
        }

        // --- 4. Persist Events to Event Store & Outbox (Atomically) ---
        List<DomainEvent> eventsToStore = customer.getUncommittedEvents();
        if (eventsToStore.isEmpty()) {
            return; // No changes, no events to publish
        }

        try {
            List<EventStoreEvent> eventStoreEntities = eventsToStore.stream()
                .map(this::mapToEventStoreEvent)
                .collect(Collectors.toList());
            eventStoreEventRepository.saveAll(eventStoreEntities);

            List<OutboxMessage> outboxMessages = eventsToStore.stream()
                .map(this::mapToOutboxMessage)
                .collect(Collectors.toList());
            outboxMessageRepository.saveAll(outboxMessages);

            customer.markEventsCommitted();
        } catch (DataIntegrityViolationException e) {
            // This catches the UNIQUE constraint violation on (aggregate_id, sequence_number)
            // This means another transaction has just written to this aggregate
            throw new ConcurrencyException(
                "Another concurrent update detected for customer " + command.customerId() + ". " +
                "Please refresh and try again.", e
            );
        } catch (IOException e) {
            throw new RuntimeException("Failed to serialize event to JSON", e);
        }
    }

    // Helper methods for mapping/deserializing (similar to before)
    private OutboxMessage mapToOutboxMessage(DomainEvent event) {
        try {
            return OutboxMessage.builder()
                .id(event.getEventId())
                .aggregateId(event.getAggregateId())
                .aggregateType(event.getAggregateType())
                .eventType(event.getEventType())
                .timestamp(event.getTimestamp())
                .payload(objectMapper.writeValueAsString(event))
                .metadata(null)
                .build();
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize event to JSON: " + event.getEventId(), e);
        }
    }

    private EventStoreEvent mapToEventStoreEvent(DomainEvent event) {
        try {
            return EventStoreEvent.builder()
                .id(event.getEventId())
                .aggregateId(event.getAggregateId())
                .aggregateType(event.getAggregateType())
                .eventType(event.getEventType())
                .timestamp(event.getTimestamp())
                .sequenceNumber(event.getSequenceNumber())
                .payload(objectMapper.writeValueAsString(event))
                .metadata(null)
                .build();
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize event to JSON: " + event.getEventId(), e);
        }
    }

    private DomainEvent deserializeEventStoreEvent(EventStoreEvent eventStoreEvent) {
        try {
            // Assuming your event JSON includes the 'eventType' field for polymorphic deserialization
            return objectMapper.readValue(eventStoreEvent.getPayload(), DomainEvent.class);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize event: " + eventStoreEvent.getId(), e);
        }
    }
}
```

#### 4. `EventStoreEventRepository` (Add find method)

```java
// infrastructure/persistence/eventstore/EventStoreEventRepository.java (Revised)
package com.example.eventoutbox.infrastructure.persistence.eventstore;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface EventStoreEventRepository extends JpaRepository<EventStoreEvent, UUID> {
    List<EventStoreEvent> findByAggregateIdOrderBySequenceNumberAsc(String aggregateId);
}
```

#### 5. `CustomerController` (Handle Exception)

```java
// application/CustomerController.java (Revised)
package com.example.eventoutbox.application;

import com.example.eventoutbox.domain.ConcurrencyException;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/customers")
@RequiredArgsConstructor
public class CustomerController {

    private final CustomerApplicationService customerApplicationService;

    public record UpdateCustomerProfileRequest(String customerId, String newName, String newAddress, long expectedVersion) {}

    @PostMapping("/profile")
    public ResponseEntity<String> updateCustomerProfile(@RequestBody UpdateCustomerProfileRequest request) {
        CustomerApplicationService.UpdateCustomerProfileCommand command =
            new CustomerApplicationService.UpdateCustomerProfileCommand(
                request.customerId(), request.newName(), request.newAddress(), request.expectedVersion()
            );
        customerApplicationService.updateCustomerProfile(command);
        return ResponseEntity.ok("Customer profile update command received and processed.");
    }

    @ExceptionHandler(ConcurrencyException.class)
    public ResponseEntity<String> handleConcurrencyException(ConcurrencyException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(ex.getMessage());
    }
}
```

### How to Handle Concurrency Conflicts on the Client/UI Side:

When `ConcurrencyException` is thrown:

1.  **Inform the User:** Display a message like "This item has been updated by another user. Please refresh the page to see the latest changes and try your update again."
2.  **Retry (less common for user-facing, but possible for background jobs):** For non-interactive or automated processes, you might implement a retry mechanism. This retry would need to:
    *   Fetch the *latest* state of the aggregate from a read model.
    *   Re-create the command based on the original intent and the *newly fetched expected version*.
    *   Re-send the command.
    *   This is typically only done if the change is "safe" to re-apply (e.g., adding an item, not changing a specific value).

By combining the version check in your application service with the `UNIQUE` constraint in your database, you create a robust optimistic concurrency control mechanism that prevents lost updates effectively.

