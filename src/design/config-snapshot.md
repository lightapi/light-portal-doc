# Configuration Snapshot Design

This document describes the design and implementation of the configuration snapshot feature in the light-portal.

## Overview

A configuration snapshot captures the state of an instance's configuration at a specific point in time. It includes all properties, files, and relationships defined for that instance, merging overrides from various levels (Product, Environment, Product Version) into a "burned-in" effective configuration.

Snapshots are created in two scenarios:
1.  **Deployment Trigger:** Automatically created when a deployment occurs (to capture the state being deployed).
2.  **User Trigger:** Manually created by a user via the UI (e.g., to save a milestone).

## Data Model

### Snapshot Header (`config_snapshot_t`)
Captures metadata about the snapshot.
- `snapshot_id`: UUID
- `snapshot_type`: Type of snapshot (e.g., `DEPLOYMENT`, `USER_SAVE`)
- `instance_id`: Target instance
- `host_id`: Tenant identifier
- `deployment_id`: Link to deployment (if applicable)
- `product_version`: Locked product version at time of snapshot
- `service_id`: Locked service ID

### Snapshot Content
Snapshot data is normalizing into shadow tables that mirror the runtime configuration tables. These tables differ from the runtime tables by including a `snapshot_id` and lacking some runtime-specific fields.

Key tables include:
- `snapshot_instance_property_t`
- `snapshot_instance_file_t`
- `snapshot_deployment_instance_property_t`
- `snapshot_product_version_property_t`
- `snapshot_environment_property_t`
- ... (others for APIs, Apps, etc.)

### Effective Configuration (`config_snapshot_property_t`)
A flattened, merged view of all properties for the snapshot. This table represents the "final" configuration values used by the instance.
- Calculated by merging properties from all levels (Deployment > Instance > Product Version > Environment > Product) based on priority.

## Backend Implementation

### Stored Procedure (`create_snapshot`)
Located in `portal-db/postgres/sp_tr_fn.sql`.
This procedure performs the heavy lifting:
1.  Validates the instance and retrieves scope data (product, environment, etc.).
2.  Creates the snapshot header record.
3.  Copies raw data from active runtime tables to snapshot tables (e.g., `instance_property_t` -> `snapshot_instance_property_t`).
4.  **Merges** properties from all levels into `config_snapshot_property_t`.
    - Handles list/map merging (aggregation).
    - Handles scalar overriding (last update wins/priority tiers).

### Persistence Layer (`ConfigPersistenceImpl.java`)
Provides the Java interface to calls the stored procedure:
- `createConfigSnapshot`: Calls `CALL create_snapshot(...)`.
- `getConfigSnapshot`: Retrieves snapshot headers with filtering/sorting.
- `updateConfigSnapshot`: Updates metadata (description).
- `deleteConfigSnapshot`: Deletes a snapshot and its cascaded data (if cascade delete is set up in DB, otherwise manual cleanup might be needed).

## Front End Implementation

### Config Snapshot Page (`ConfigSnapshot.tsx`)
- Displays a list of snapshots for a selected instance.
- Supports filtering by `current`, ID, date, etc.
- **Actions:**
    - **Create:** Navigates to `/app/form/createConfigSnapshot`.
    - **Update:** Fetches fresh data and navigates to update form.
    - **Delete:** Calls `deleteSnapshot` command.

## Gap Analysis & Missing Components

The following components are currently **MISSING** or incomplete:

1.  **Command Handlers:**
    - `CreateConfigSnapshot` handler (for User Trigger) is missing in `config-command`.
    - `DeleteConfigSnapshot` handler is missing in `config-command`.
    - `GetFreshConfigSnapshot` handler is missing (required for the "Update" action in UI).

2.  **Deployment Integration:**
    - `CreateDeployment.java` (in `deployment-command`) does **NOT** call `createConfigSnapshot`.
    - The automatic snapshot creation on deployment is currently not implemented.

3.  **API Definition:**
    - The `createConfigSnapshot` and `deleteConfigSnapshot` endpoints need to be defined in the schema/routing if they are not already.

## Action Plan

1.  **Implement Command Handlers:**
    - Create `CreateConfigSnapshot` handler in `config-command` that invokes `ConfigPersistence.createConfigSnapshot`.
    - Create `DeleteConfigSnapshot` handler in `config-command`.
    - Create `GetFreshConfigSnapshot` handler in `config-query`.

2.  **Integrate with Deployment:**
    - Modify `CreateDeployment.java` (or the platform handler it invokes) to call `ConfigPersistence.createConfigSnapshot` immediately after a successful deployment job is submitted or completed.

3.  **Review Idempotency:**
    - Ensure `create_snapshot` handles re-runs gracefully (Idempotency is partially handled by UUID generation, but business logic should prevent duplicate snapshots for the exact same state if needed).
