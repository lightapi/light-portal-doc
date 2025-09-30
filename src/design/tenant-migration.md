# Tenant Migration and Environment Promotion

This document addresses the reality of tenant migration and environment promotion in an Event Sourcing context. You must preserve the event sequence (aggregate_version) while making necessary adjustments (hostId, new userId UUIDs) to fit the target environment.

---

### Design Strategy: The Event Mutator

The best design is to introduce a specific, configurable pipeline stage—an **Event Mutator**—that runs *after* deserialization but *before* the final DB insert.

We'll define the `replacement` and `enrichment` parameters as JSON/YAML structures and create a separate utility to apply the mutations.

#### 1. Mutation Configuration Format

We'll define the parameters to be a JSON string representing a list of mutation rules.

*   **`replacement` (`-r`):** Find a field with an old value and replace it with a new value.
    *   Example: `[{"field": "hostId", "from": "UUID_A", "to": "UUID_B"}, {"field": "user_id", "from": "ID_X", "to": "ID_Y"}]`
*   **`enrichment` (`-e`):** Find a field and generate a new, unique value for it.
    *   Example: `[{"field": "id", "action": "generateUUID"}, {"field": "userId", "action": "mapAndGenerate", "sourceField": "originalUserId"}]`

#### 2. The `EventMutator` Class

This class will handle parsing the configuration and applying the changes to the `CloudEvent` attributes and the `data` payload.

---

### Refactored `Cli.java` and New `EventMutator` Logic

Here is the updated `Cli.java` and a conceptual `EventMutator` structure.

#### A. New Class: `EventMutator.java`

This class handles the core logic. Since CloudEvents are immutable, any change requires rebuilding the event (`CloudEventBuilder.v1(cloudEvent)`).

```java
package net.lightapi.importer;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.config.Config;
import com.networknt.utility.UuidUtil;
import io.cloudevents.CloudEvent;
import io.cloudevents.core.builder.CloudEventBuilder;
import net.lightapi.portal.PortalConstants;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class EventMutator {
    private static final Logger logger = LoggerFactory.getLogger(EventMutator.class);
    private final ObjectMapper mapper = Config.getInstance().getMapper();
    
    // Parsed list of rules
    private final List<Map<String, String>> replacementRules;
    private final List<Map<String, String>> enrichmentRules;

    // Map to track generated UUIDs for consistent replacement across events (e.g., old user ID -> new user ID)
    private final Map<String, String> generatedIdMap = new HashMap<>();

    public EventMutator(String replacementJson, String enrichmentJson) {
        this.replacementRules = parseRules(replacementJson);
        this.enrichmentRules = parseRules(enrichmentJson);
    }

    private List<Map<String, String>> parseRules(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            return mapper.readValue(json, new TypeReference<List<Map<String, String>>>() {});
        } catch (IOException e) {
            logger.error("Failed to parse mutation rules JSON: {}", json, e);
            throw new IllegalArgumentException("Invalid JSON format for mutation rules.", e);
        }
    }

    /**
     * Applies all replacement and enrichment rules to a single CloudEvent.
     * @param originalEvent The original CloudEvent object.
     * @return The mutated CloudEvent.
     */
    public CloudEvent mutate(CloudEvent originalEvent) {
        CloudEventBuilder builder = CloudEventBuilder.v1(originalEvent);
        Map<String, Object> dataMap = null;
        
        // Deserialize data payload once (if present)
        if (originalEvent.getData() != null && originalEvent.getData().toBytes().length > 0) {
            try {
                dataMap = mapper.readValue(originalEvent.getData().toBytes(), new TypeReference<HashMap<String, Object>>() {});
            } catch (IOException e) {
                logger.error("Failed to deserialize CloudEvent data for mutation. Skipping data mutation.", e);
                // Continue with just extension mutation
            }
        }
        
        // 1. Apply Replacements
        applyReplacements(builder, dataMap);
        
        // 2. Apply Enrichments
        applyEnrichments(builder, dataMap);

        // Rebuild CloudEvent with mutated data if it was changed
        if (dataMap != null && dataMap.containsKey("__MUTATED_DATA__")) {
             builder.withData(originalEvent.getDataContentType().orElse("application/json"), dataMap.get("__MUTATED_DATA__"));
             // Remove the internal flag
             dataMap.remove("__MUTATED_DATA__");
        }
        
        return builder.build();
    }
    
    // --- Private Mutation Helpers ---

    private void applyReplacements(CloudEventBuilder builder, Map<String, Object> dataMap) {
        for (Map<String, String> rule : replacementRules) {
            String field = rule.get("field");
            String from = rule.get("from");
            String to = rule.get("to");
            if (field == null || from == null || to == null) continue;

            // Check CloudEvent Extensions (including known attributes like host, user)
            Object extensionValue = builder.getExtension(field);
            if (extensionValue != null && extensionValue.toString().equals(from)) {
                builder.withExtension(field, to);
                logger.debug("Replaced extension {} from {} to {}", field, from, to);
            } 
            
            // Check CloudEvent Data Payload
            if (dataMap != null && dataMap.containsKey(field) && dataMap.get(field) != null && dataMap.get(field).toString().equals(from)) {
                dataMap.put(field, to);
                dataMap.put("__MUTATED_DATA__", dataMap); // Flag that data was mutated
                logger.debug("Replaced data field {} from {} to {}", field, from, to);
            }
        }
    }
    
    private void applyEnrichments(CloudEventBuilder builder, Map<String, Object> dataMap) {
        for (Map<String, String> rule : enrichmentRules) {
            String field = rule.get("field");
            String action = rule.get("action");
            if (field == null || action == null) continue;
            
            String generatedId = null;

            if ("generateUUID".equalsIgnoreCase(action)) {
                // Generate and cache a new UUID for the whole import run if needed, or always generate new.
                // For simplicity, we assume we generate a new UUID for the field.
                generatedId = UuidUtil.getUUID().toString();
            } else if ("mapAndGenerate".equalsIgnoreCase(action)) {
                String sourceField = rule.get("sourceField");
                String originalId = null;
                
                // Get the original ID from a source field in the data payload (e.g., from an 'oldUserId' field)
                if (dataMap != null && sourceField != null && dataMap.containsKey(sourceField)) {
                    originalId = dataMap.get(sourceField).toString();
                } 
                // Or get from a specific CloudEvent extension/subject
                else if ("subject".equalsIgnoreCase(sourceField) && builder.getSubject() != null) {
                    originalId = builder.getSubject();
                }

                if (originalId != null) {
                    // Check cache for consistency (e.g., ensure old_user_ID_A always maps to new_user_ID_X)
                    generatedId = generatedIdMap.computeIfAbsent(field + ":" + originalId, k -> UuidUtil.getUUID().toString());
                    logger.debug("Mapped original ID {} to new ID {}", originalId, generatedId);
                } else {
                    // Cannot map, fall back to simple UUID generation if allowed
                    generatedId = UuidUtil.getUUID().toString();
                }
            } else if ("aggregateIdMap".equalsIgnoreCase(action) && field.equals("subject")) {
                // This complex logic is for when a related aggregate ID needs to be updated.
                // E.g., when importing a User, the UserCreatedEvent ID is the new Subject/AggregateId.
                // The actual logic for this is too complex for a generic SMT and relies on a separate lookup service.
                // Skip for this simple mutator.
                continue;
            }

            if (generatedId != null) {
                // Mutate CloudEvent Extensions (Subject, ID, etc.)
                if ("id".equalsIgnoreCase(field)) {
                    builder.withId(generatedId);
                } else if ("subject".equalsIgnoreCase(field)) {
                    builder.withSubject(generatedId);
                } else if (builder.getExtension(field) != null) { // Custom extension
                    builder.withExtension(field, generatedId);
                }
                
                // Mutate Data Payload
                if (dataMap != null && dataMap.containsKey(field)) {
                    dataMap.put(field, generatedId);
                    dataMap.put("__MUTATED_DATA__", dataMap); // Flag that data was mutated
                }
                logger.debug("Enriched field {} with new ID {}", field, generatedId);
            }
        }
    }
}
```

#### B. Updated `Cli.java` to Integrate `EventMutator`

```java
package net.lightapi.importer;

// ... (Existing imports) ...
import com.networknt.config.JsonMapper;
import com.networknt.db.provider.SqlDbStartupHook;
import com.networknt.monad.Result;
import com.networknt.service.SingletonServiceFactory;
import com.networknt.status.Status;
import com.networknt.utility.Constants;
import com.networknt.utility.UuidUtil; // Used in mutator
import io.cloudevents.CloudEvent;
import io.cloudevents.core.builder.CloudEventBuilder;
import io.cloudevents.core.format.EventFormat;
import io.cloudevents.core.provider.EventFormatProvider;
import io.cloudevents.jackson.JsonFormat;
import net.lightapi.portal.EventTypeUtil;
import net.lightapi.portal.PortalConstants;
import net.lightapi.portal.db.PortalDbProvider;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID; // Used in mutator

public class Cli {
    private static final Logger logger = LoggerFactory.getLogger(Cli.class); // Added logger
    public static PortalDbProvider dbProvider;
    public static SqlDbStartupHook sqlDbStartupHook;

    @Parameter(names={"--filename", "-f"}, required = false,
            description = "The filename to be imported.")
    String filename;

    @Parameter(names={"--batchSize", "-b"}, required = false,
            description = "Number of events to import per database transaction batch. Default is 1000.")
    int batchSize = 1000;

    @Parameter(names={"--replacement", "-r"}, required = false,
            description = "JSON array string of replacement rules: [{'field': 'oldHostId', 'from': 'UUID_A', 'to': 'UUID_B'}].")
    String replacement;

    @Parameter(names={"--enrichment", "-e"}, required = false,
            description = "JSON array string of enrichment rules: [{'field': 'userId', 'action': 'mapAndGenerate', 'sourceField': 'oldUserId'}].")
    String enrichment;

    @Parameter(names={"--help", "-h"}, help = true)
    private boolean help;

    public static void main(String ... argv) throws Exception {
        try {
            // ... (Startup initialization remains the same) ...
            Cli cli = new Cli();
            JCommander jCommander = JCommander.newBuilder().addObject(cli).build();
            jCommander.parse(argv);
            // Assuming SingletonServiceFactory and SqlDbStartupHook setup is correct
            dbProvider = (PortalDbProvider) SingletonServiceFactory.getBean(DbProvider.class);
            cli.run(jCommander);

        } catch (ParameterException e) {
            System.err.println("Command line parameter error: " + e.getLocalizedMessage());
            jCommander.usage();
        } catch (Exception e) {
            System.err.println("An unexpected error occurred during startup or import: " + e.getLocalizedMessage());
            e.printStackTrace();
        }
    }

    public void run(JCommander jCommander) throws Exception {
        if (help) {
            jCommander.usage();
            return;
        }

        logger.info("Starting event import with batch size: {}", batchSize);
        if (replacement != null) logger.info("Replacement rules: {}", replacement);
        if (enrichment != null) logger.info("Enrichment rules: {}", enrichment);

        EventFormat cloudEventFormat = EventFormatProvider.getInstance().resolveFormat(JsonFormat.CONTENT_TYPE);
        if (cloudEventFormat == null) {
            logger.error("No CloudEvent JSON format provider found.");
            throw new IllegalStateException("CloudEvent JSON format not found.");
        }

        // --- Instantiate EventMutator ---
        EventMutator mutator = new EventMutator(replacement, enrichment);
        
        List<CloudEvent> currentBatch = new ArrayList<>(batchSize);
        long importedCount = 0;
        long lineNumber = 0;

        try (BufferedReader reader = new BufferedReader(new FileReader(filename))) {
            String line;
            while((line = reader.readLine()) != null) {
                lineNumber++;
                if(line.startsWith("#") || line.trim().isEmpty()) continue;

                try {
                    // Assuming format: "key value" (where key is user_id, value is the full database row JSON)
                    int firstSpace = line.indexOf(" ");
                    if (firstSpace == -1) {
                        logger.warn("Skipping malformed line {} (no space separator): {}", lineNumber, line);
                        continue;
                    }
                    String dbRowJson = line.substring(firstSpace + 1); // <<< Full DB row JSON

                    // 1. Deserialize the nested CloudEvent (The Fix from prior step)
                    Map<String, Object> dbRowMap = Config.getInstance().getMapper().readValue(dbRowJson, new TypeReference<HashMap<String, Object>>() {});
                    String cloudEventJsonFromPayload = (String) dbRowMap.get("payload"); 
                    CloudEvent cloudEvent = cloudEventFormat.deserialize(cloudEventJsonFromPayload.getBytes(StandardCharsets.UTF_8));
                    
                    // 2. Perform Mutation/Enrichment
                    CloudEvent mutatedEvent = mutator.mutate(cloudEvent);

                    // 3. Finalization/Validation (Transfer critical top-level DB fields to Extensions)
                    // Transferring nonce and aggregateVersion from the exported DB row into the CloudEvent's extensions.
                    Object dbNonceObj = dbRowMap.get("nonce");
                    if (dbNonceObj instanceof Number) {
                        mutatedEvent = CloudEventBuilder.v1(mutatedEvent)
                                .withExtension(PortalConstants.NONCE, ((Number)dbNonceObj).longValue())
                                .build();
                    }
                    Object dbAggVersionObj = dbRowMap.get("aggregateVersion");
                    if (dbAggVersionObj instanceof Number) {
                        mutatedEvent = CloudEventBuilder.v1(mutatedEvent)
                                .withExtension(PortalConstants.EVENT_AGGREGATE_VERSION, ((Number)dbAggVersionObj).longValue())
                                .build();
                    }
                    
                    // 4. Add to current batch.
                    currentBatch.add(mutatedEvent);

                    // If batch is full, process it
                    if (currentBatch.size() >= batchSize) {
                        processBatch(currentBatch); 
                        importedCount += currentBatch.size();
                        currentBatch.clear();
                    }

                } catch (Exception e) {
                    logger.error("Error processing line {}: {}", lineNumber, e.getMessage(), e);
                    // Log and continue to process the rest of the file.
                }
            } // end while loop

            // Process any remaining events in the last batch
            if (!currentBatch.isEmpty()) {
                processBatch(currentBatch);
                importedCount += currentBatch.size();
            }

        } catch (IOException e) {
            logger.error("Error reading file {}: {}", filename, e.getMessage(), e);
            throw e;
        } finally {
            logger.info("Import process finished. Total events successfully imported in batches: {}", importedCount);
        }
        logger.info("All Portal Events have been imported successfully from {}. Have fun!!!", filename);
    }

    /**
     * Processes a batch of CloudEvents by inserting them into the database in a single transaction.
     * @param batch The list of CloudEvents to insert.
     */
    private void processBatch(List<CloudEvent> batch) {
        // --- Transaction Management ---
        // The transaction logic is ideally handled inside dbProvider.insertEventStore
        // or by a wrapper method if insertEventStore doesn't handle transactions internally.
        
        Result<String> eventStoreResult = dbProvider.insertEventStore(batch.toArray(new CloudEvent[0]));
        
        if(eventStoreResult.isFailure()) {
            logger.error("Failed to insert batch of {} events. Rollback occurred. Error: {}", batch.size(), eventStoreResult.getError());
            // In a CLI, failing the batch often means stopping the entire import process 
            // to ensure data integrity, as a full rollback on the entire batch has occurred.
            // If you want to continue, you would need complex tracking of failed batches.
            // For now, logging the error is sufficient, and the method returns.
        } else {
            logger.info("Imported batch of {} records successfully.", batch.size());
        }
    }
}
```

---

### Key Usage Examples for the CLI

When calling the CLI, you pass the mutation rules as a single JSON string (often enclosed in single quotes `'...'` in the shell):

#### 1. Replace Host ID (Tenant Migration)

You moved from `old_host_uuid` to `new_host_uuid`.

```bash
java -jar importer.jar -f events.log -r '[{"field": "hostId", "from": "OLD_HOST_UUID", "to": "NEW_HOST_UUID"}]'
```

#### 2. Replace Host ID and Generate New Aggregate IDs (Full Isolation)

You want to map the old `userId` to a new `userId` and generate new `eventId`s and `subject` (aggregate ID).

```bash
java -jar importer.jar -f events.log \
    -r '[{"field": "hostId", "from": "OLD_HOST_UUID", "to": "NEW_HOST_UUID"}]' \
    -e '[
        {"field": "id", "action": "generateUUID"}, 
        {"field": "subject", "action": "generateUUID"},
        {"field": "originalUserId", "action": "mapAndGenerate", "sourceField": "userId"}
    ]'
```
*(Note: For the user mapping, you would need a custom solution that first reads a mapping table or performs a one-time query to get the `originalUserId` from a previous step, and then uses the mapping to generate the new ID consistently.)*

