# User Management

## User Type


The `user_type` field is a critical part of the user security profile in the JWT token and can be leveraged for fine-grained authorization. In a multi-tenant environment, `user_type` is presented as a dropdown populated from the reference table configured for the organization. It can be dynamically selected based on the `host` chosen during the user registration process.


#### Supported Standard Dropdown Models

1. **Employee and Customer**  
   - Dropdown values: `E` (Employee), `C` (Customer)  
   - Default model for `lightapi.net` host.
   - Suitable for most organizations.
   
2. **Employee, Personal, and Business**  
   - Dropdown values:  
     - `E` (Employee)  
     - `P` (Personal)  
     - `B` (Business)  
   - Commonly used for banks where personal and business banking are separated.  

#### Database Configuration

- The `user_type` field is nullable in the `user_t` table by default.
- However, you can enforce this field as mandatory in your application via the schema and UI configuration.


#### On-Prem Deployment

In on-premise environments, the `user_type` can determine the authentication method:
- **Employees**: Authenticated via Active Directory.  
- **Customers**: Authenticated via a customer database.

This flexibility allows organizations to tailor the authentication process based on their specific needs and user classifications.

## Handling Users with Multi-Host Access

#### There are two primary ways to handle users who belong to multiple hosts:

1. User-Host Mapping Table:

user_t: This table would not have a host_id and would store core user information that is host-independent. The user_id would be unique across all hosts.

user_host_t (or user_tenant_t): This would be a mapping table to represent the many-to-many relationship between users and hosts.

```
-- user_t (no host_id, globally unique user_id)
CREATE TABLE user_t (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- UUID is recommended
    -- ... other user attributes (e.g., name, email) 
);

-- user_host_t (mapping table)
CREATE TABLE user_host_t (
    user_id UUID NOT NULL,
    host_id UUID NOT NULL,
    -- ... other relationship-specific attributes (e.g., roles within the host)
    PRIMARY KEY (user_id, host_id),
    FOREIGN KEY (user_id) REFERENCES user_t (user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES host_t (host_id) ON DELETE CASCADE -- Assuming you have a hosts_t
);
```

2. Duplicating User Records (Less Recommended):

user_t: You would keep host_id in this table, and the primary key would be (host_id, user_id).

User Duplication: If a user needs access to multiple hosts, you would duplicate their user record in users_t for each host they belong to, each with a different host_id.


#### Why User-Host Mapping is Generally Preferred:

* Data Integrity: Avoids data duplication and the potential for inconsistencies that come with it. If a user's core information (e.g., name, email) changes, you only need to update it in one place in user_t.

* Flexibility: Easier to add or remove a user's access to hosts without affecting their core user data.

* Querying: While you'll need joins to get a user's hosts or a host's users, these joins are straightforward using the mapping table.

* Scalability: Better scalability as your user base and the number of hosts they can access grow.

#### Distributing Tables in a Multi-Host User Scenario:

With the user-host mapping approach:

* user_t: This table would likely be a reference table in Citus (replicated to all nodes) since it does not have a host_id for distribution.

* user_host_t: This table would be distributed by host_id.

* Other tables (e.g., employees_t, api_endpoints_t, etc.): These would be distributed by host_id as before.

When querying, you would typically:

* Start with the user_hosts_t table to find the hosts a user has access to.

* Join with other tables (distributed by host_id) based on the host_id to retrieve tenant-specific data.


## Choosing the Right user_id Primary Key:

Here's a comparison of the options for the user_id primary key in user_t:

#### **1. UUID (`user_id`)**

- **Pros**:
  - **Globally Unique**: Avoids collisions across hosts or when scaling beyond the current setup.
  - **Security**: Difficult to guess or enumerate.
  - **Scalability**: Well-suited for distributed environments like Citus.
- **Cons**:
  - **Storage**: Slightly larger storage size compared to integers.
  - **Readability**: Not human-readable, which can be inconvenient for debugging.
- **Recommendation**:  
  This is generally the **best option** for a `user_id` in a multi-tenant, distributed environment.

---

#### **2. Email (`email`)**

- **Pros**:
  - **Human-Readable**: Easy to identify and manage.
  - **Login Identifier**: Often used as a natural login credential.
- **Cons**:
  - **Uniqueness Challenges**: Enforcing global uniqueness across all hosts may require complex constraints or application logic.
  - **Changeability**: If emails change, cascading updates can complicate the database.
  - **Security**: Using emails as primary keys can expose sensitive user data if not handled securely.
  - **Performance**: String comparisons are slower than those for integers or UUIDs.
- **Recommendation**:  
  **Not recommended** as a primary key, especially in a multi-tenant or distributed setup.

---

#### **3. User-Chosen Unique ID (e.g., `username`)**

- **Pros**:
  - **Human-Readable**: Intuitive and user-friendly.
- **Cons**:
  - **Uniqueness Challenges**: Enforcing global uniqueness is challenging and may require complex constraints.
  - **Changeability**: Users may request username changes, causing cascading update issues.
  - **Security**: Usernames are easier to guess or enumerate compared to UUIDs.
- **Recommendation**:  
  **Not recommended** as a primary key in a multi-tenant, distributed environment.

#### In Conclusion:

- **Use a User-Host Mapping Table**:  
  This is the best approach to handle users who belong to multiple hosts in a multi-tenant Citus environment.

- **Use UUID for `user_id`**:  
  UUIDs are the most suitable option for the `user_id` primary key in `user_t` due to their global uniqueness, security, and scalability.

- **Distribute by `host_id`**:  
  Distribute tables that need sharding by `host_id`, and ensure that foreign keys to distributed tables include `host_id`.

- **Use Reference Tables**:  
  For tables like `user_t` that don't have a `host_id`, designate them as reference tables in Citus.

This approach provides a flexible and scalable foundation for managing users with multi-host access in your Citus-based multi-tenant application.


## User Tables

Using a single `user_t` table with a `user_type` discriminator is a good approach for managing both employees and customers in a unified way. Adding optional referral relationships for customers adds a nice dimension as well. Here's a suggested table schema in PostgreSQL, along with explanations and some considerations:

user_t (User Table): This table will store basic information common to both employees and customers.

```
CREATE TABLE user_t (
    user_id                   VARCHAR(24) NOT NULL,
    email                     VARCHAR(255) NOT NULL,
    password                  VARCHAR(1024) NOT NULL,
    language                  CHAR(2) NOT NULL,
    first_name                VARCHAR(32) NULL,
    last_name                 VARCHAR(32) NULL,
    user_type                 CHAR(1) NULL, -- E employee C customer or E employee P personal B business
    phone_number              VARCHAR(20) NULL,
    gender                    CHAR(1) NULL,
    birthday                  DATE NULL,
    country                   VARCHAR(3) NULL,
    province                  VARCHAR(32) NULL,
    city                      VARCHAR(32) NULL,
    address                   VARCHAR(128) NULL,
    post_code                 VARCHAR(16) NULL,
    verified                  BOOLEAN NOT NULL DEFAULT false,
    token                     VARCHAR(64) NULL,
    locked                    BOOLEAN NOT NULL DEFAULT false,
    nonce                     BIGINT NOT NULL DEFAULT 0,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

ALTER TABLE user_t ADD CONSTRAINT user_pk PRIMARY KEY ( user_id );

ALTER TABLE user_t ADD CONSTRAINT user_email_uk UNIQUE ( email );
```

user_host_t (User to host relationship or mapping): 

```
CREATE TABLE user_host_t (
    host_id                   VARCHAR(24) NOT NULL,
    user_id                   VARCHAR(24) NOT NULL,
    -- other relationship-specific attributes (e.g., roles within the host)
    PRIMARY KEY (host_id, user_id),
    FOREIGN KEY (user_id) REFERENCES user_t (user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES host_t (host_id) ON DELETE CASCADE
);

```

employee_t (Employee Table): This table will store employee-specific attributes.

```
CREATE TABLE employee_t (
    host_id                   VARCHAR(22) NOT NULL,
    employee_id               VARCHAR(50) NOT NULL,  -- Employee ID or number or ACF2 ID. Unique within the host. 
    user_id                   VARCHAR(22) NOT NULL,
    title                     VARCHAR(255) NOT NULL,
    manager_id                VARCHAR(50), -- manager's employee_id if there is one.
    hire_date                 DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, employee_id),
    FOREIGN KEY (host_id, user_id) REFERENCES user_host_t(host_id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, manager_id) REFERENCES employee_t(host_id, employee_id) ON DELETE CASCADE
);
```

customer_t (Customer Table): This table will store customer-specific attributes.

```
CREATE TABLE customer_t (
    host_id                   VARCHAR(24) NOT NULL,
    customer_id               VARCHAR(50) NOT NULL,
    user_id                   VARCHAR(24) NOT NULL,
    -- Other customer-specific attributes
    referral_id               VARCHAR(22), -- the customer_id who refers this customer. 
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, customer_id),
    FOREIGN KEY (host_id, user_id) REFERENCES user_host_t(host_id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, referral_id) REFERENCES customer_t(host_id, customer_id) ON DELETE CASCADE
);
```

position_t (Position Table): Defines different positions within the organization for employees.

```
CREATE TABLE position_t (
    host_id                   VARCHAR(22) NOT NULL,
    position_id               VARCHAR(22) NOT NULL,
    position_name             VARCHAR(255) UNIQUE NOT NULL,
    description               TEXT,
    inherit_to_ancestor       BOOLEAN DEFAULT FALSE,
    inherit_to_sibling        BOOLEAN DEFAULT FALSE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, position_id)
);
```

employee_position_t (Employee Position Table): Links employees to their positions with effective dates.

```
CREATE TABLE employee_position_t (
    host_id                   VARCHAR(22) NOT NULL,
    employee_id               VARCHAR(50) NOT NULL,
    position_id               VARCHAR(22) NOT NULL,
    position_type             CHAR(1) NOT NULL, -- P position of own, D inherited from a decendant, S inherited from a sibling.
    start_date                DATE NOT NULL,
    end_date                  DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, employee_id, position_id),
    FOREIGN KEY (host_id, position_id) REFERENCES position_t(host_id, position_id) ON DELETE CASCADE
);
```

## Authorization Strategies

In order to link users to API endpoints for authorization, we will adpot the following approaches with a rule engine to enforce the policies in the sidecar of the API with access-control middleware handler.


A. Role-Based Access Control (RBAC)

This is a common and relatively simple approach. You define roles (e.g., "admin," "editor," "viewer") and assign permissions to those roles. Users are then assigned to one or more roles.

Role Table:

```
CREATE TABLE role_t (
    host_id                   VARCHAR(22) NOT NULL,
    role_id                   VARCHAR(22) NOT NULL,
    role_name                 VARCHAR(255) UNIQUE NOT NULL,
    description               TEXT,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, role_id)
);

```

Role-Endpoint Permission Table:

```
CREATE TABLE role_permission_t (
    host_id                   VARCHAR(32) NOT NULL,
    role_id                   VARCHAR(32) NOT NULL,
    endpoint_id               VARCHAR(64) NOT NULL,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, role_id, endpoint_id),
    FOREIGN KEY (host_id, role_id) REFERENCES role_t(host_id, role_id) ON DELETE CASCADE,
    FOREIGN KEY (endpoint_id) REFERENCES api_endpoint_t(endpoint_id) ON DELETE CASCADE
);

```

Role-User Assignment Table:

```
CREATE TABLE role_user_t (
    host_id                   VARCHAR(22) NOT NULL,
    role_id                   VARCHAR(22) NOT NULL,
    user_id                   VARCHAR(22) NOT NULL,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, role_id, user_id, start_date),
    FOREIGN KEY (user_id) REFERENCES user_t(user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, role_id) REFERENCES role_t(host_id, role_id) ON DELETE CASCADE
);
```

B. User-Based Access Control (UBAC)

This approach assigns permissions directly to users, allowing for very fine-grained control. It's more flexible but can become complex to manage if you have a lot of users and endpoints. It should only be used for temporary access. 

User-Endpoint Permissions Table:

```
CREATE TABLE user_permission_t (
    user_id                   VARCHAR(22) NOT NULL,
    host_id                   VARCHAR(22) NOT NULL,
    endpoint_id               VARCHAR(22) NOT NULL,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, host_id, endpoint_id),
    FOREIGN KEY (user_id) REFERENCES user_t(user_id) ON DELETE CASCADE,
    FOREIGN KEY (endpoint_id) REFERENCES api_endpoint_t(endpoint_id) ON DELETE CASCADE
);

```

C. Group-Based Access Control (GBAC)

You can group users into teams or departments and assign permissions to those groups. This is useful when you want to manage permissions for sets of users with similar access needs.


Groups Table:

```
CREATE TABLE group_t (
    host_id                   VARCHAR(32) NOT NULL,
    group_id                  VARCHAR(32) NOT NULL,
    group_name                VARCHAR(255) UNIQUE NOT NULL,
    description               TEXT,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, group_id)
);
```

Group-Endpoint Permission Table:

```
CREATE TABLE group_permission_t (
    host_id                   VARCHAR(32) NOT NULL,
    group_id                  VARCHAR(32) NOT NULL,
    endpoint_id               VARCHAR(32) NOT NULL,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, group_id, endpoint_id),
    FOREIGN KEY (host_id, group_id) REFERENCES group_t(host_id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (endpoint_id) REFERENCES api_endpoint_t(endpoint_id) ON DELETE CASCADE
);

```

Group-User Membership Table:

```
CREATE TABLE group_user_t (
    host_id                   VARCHAR(22) NOT NULL,
    group_id                  VARCHAR(22) NOT NULL,
    user_id                   VARCHAR(22) NOT NULL,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, group_id, user_id, start_date),
    FOREIGN KEY (user_id) REFERENCES user_t(user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, group_id) REFERENCES group_t(host_id, group_id) ON DELETE CASCADE
);

```

D. Attribute-Based Access Control (ABAC)


Attribute Table:

```
CREATE TABLE attribute_t (
    host_id                   VARCHAR(22) NOT NULL,
    attribute_id              VARCHAR(22) NOT NULL,
    attribute_name            VARCHAR(255) UNIQUE NOT NULL, -- The name of the attribute (e.g., "department," "job_title," "project," "clearance_level," "location").
    attribute_type            VARCHAR(50) CHECK (attribute_type IN ('string', 'integer', 'boolean', 'date', 'float', 'list')), -- Define allowed data types
    description               TEXT,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, attribute_id)
);

```

2. Attribute User Table:

```
CREATE TABLE attribute_user_t (
    host_id                   VARCHAR(22) NOT NULL,
    attribute_id              VARCHAR(22) NOT NULL,
    user_id                   VARCHAR(22) NOT NULL, -- References users_t
    attribute_value           TEXT, -- Store values as strings; you can cast later
    start_date                DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date                  DATE,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, attribute_id, user_id, start_date),
    FOREIGN KEY (user_id) REFERENCES user_t(user_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, attribute_id) REFERENCES attribute_t(host_id, attribute_id) ON DELETE CASCADE
);


```

3. Attribute Permission Table:

```
CREATE TABLE attribute_permission_t (
    host_id                   VARCHAR(32) NOT NULL,
    attribute_id              VARCHAR(32) NOT NULL,
    endpoint_id               VARCHAR(32) NOT NULL, -- References api_endpoints_t
    attribute_value           TEXT,
    update_user               VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_timestamp          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (host_id, attribute_id, endpoint_id),
    FOREIGN KEY (endpoint_id) REFERENCES api_endpoint_t(endpoint_id) ON DELETE CASCADE,
    FOREIGN KEY (host_id, attribute_id) REFERENCES attribute_t(host_id, attribute_id) ON DELETE CASCADE
);
```


How it Works:

1. Define Attributes: Define all relevant attributes in attribute_t. Think about all the properties of your users, resources, and environment that might be used in access control decisions.

2. Assign Attributes to Users: Populate user_attribute_t to associate attribute values with users.

3. Assign Attributes to Endpoints: Populate attribute_permission_t to associate attribute values with API endpoints.

4. Write Policies: Create policy rules in rule engine. These rules should use the attribute names defined in attribute_t.

5. Policy Evaluation (at runtime):

* The policy engine receives the subject (user), resource (API endpoint), and action (HTTP method) of the request.

* The engine retrieves the relevant attributes from the user_attribute_t and attribute_permission_t tables.

* The engine evaluates the policy rule from the relevant policies against the attributes.

* Based on the policy evaluation result, access is either granted or denied.



Key Advantages of ABAC:

* Fine-Grained Control: Express very specific access rules.

* Centralized Policy Management: Policies are stored centrally and can be easily updated.

* Flexibility and Scalability: Adapts easily to changing requirements.

* Auditing and Compliance: Easier to audit and demonstrate compliance.

## JWT Security Claims

Using the tables defined above, follow these steps to create an authorization code token with user security claims:

1. **`uid`**  
   Assign the `user_id` to the `uid` claim in the JWT.

2. **`role`**  
   Include a list of roles associated with the user.

3. **`grp`**  
   Add a list of groups the user belongs to.

4. **`att`**  
   Include a list of key-value pairs representing user attributes.


## Group Management and Dynamic Membership

#### 1. Define Groups Related to the Organizational Structure

You can create groups that align with teams, departments, or other organizational units. These groups are relatively static and reflect the overall organizational structure. Use a separate table, `group_t`, as described above to store these groups.

#### 2. Use the Reporting Structure to Derive Dynamic Group Memberships

Instead of directly assigning all users to groups, you can:

- Assign base group memberships to individual users (e.g., only non-managers initially).
- Use the reporting relationships stored in the `report_relationship_t` table to infer additional group memberships based on the organizational hierarchy.

#### 3. Retrieval Logic

1. **Get User's Direct Groups**:  
   Retrieve the groups a user is explicitly assigned to from the `user_group_t` table.

2. **Traverse Up the Reporting Hierarchy**:  
   Use the `report_relationship_t` table to find all the user's ancestors (managers) in the reporting structure.

3. **Inherit Subordinate Group Memberships**:  
   For each ancestor (manager), retrieve the direct reports' group memberships. Add these groups to the manager's effective group memberships. You can control the depth of inheritance (e.g., only inherit from direct reports or up to a certain level in the hierarchy).

4. **Combine and Deduplicate**:  
   Combine the user's direct group memberships with the inherited memberships, removing any duplicates.

#### Example

Let's say:

* Alice is a manager and belongs to the "Management" group.

* Bob reports to Alice and belongs to the "Engineering" group.

* Charlie reports to Bob and belongs to the "Engineering" and "Testing" groups.

When Bob's request comes in:

* Query result contains Bob's direct group: "Engineering".

* Check reporting structure: Bob reports to Alice.

* Get group memberships of Bob's direct reports: "Engineering", "Testing". (These are inherited since Bob is Charlie's manager)

* Bob's effective groups are now "Engineering", "Testing".

When Alice's request comes in:

* Query result contains Alice's direct group: "Management".

* Check reporting structure: Bob and Charlie report to Alice.

* Get group memberships of Alice's direct reports: "Engineering", "Testing" (inherited from Bob and Charlie).

* Alice's effective groups are now "Management", "Engineering", "Testing".

Advantages:

* Reduced Administrative Overhead: You don't have to manually manage group memberships for managers as their teams change.

* Dynamic Access Control: Permissions adapt automatically as the reporting structure evolves.

* Centralized Logic: The inheritance logic is encapsulated in the logic, making it easier to maintain and update.

