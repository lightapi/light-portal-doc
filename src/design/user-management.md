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

user_position_t (Employee Position Table): Links employees to their positions with effective dates.

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

2. Assign Attributes to Users: Populate attribute_user_t to associate attribute values with users.

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


Format of attributes in JWT token:

Unlike roles, groups and positions that can be concatanated as a string, an attribut is a key/value pair. We need to format multiple attributes into a string and put it into a token. 

Challenges

* Spaces: The primary issue is that simple key-value pairs like key1:value1 key2:value2 will not work when value contain spaces.

* Escaping: We need a way to escape characters that may confuse the parser, for example if the value also contains a :.

* Readability: The format should be reasonably readable for debugging and human consumption.

* Parsing: The format should be easy to parse on the application side.

Options

1. Comma-Separated Key-Value Pairs with Escaping:

  * Format: key1=value1,key2=value2_with_spaces,key3=value3\,with\,commas

  * Escaping: Use backslash \ to escape commas and backslashes within the values. You can also escape spaces to make it more clear \

  * Pros: Simple to implement, relatively easy to parse using splitting by comma and then by =.

  * Cons: Can become hard to read with complex values, requires proper escaping, will become unreadable if \ need to be escaped.

2. Custom Delimiter and Escaping:

  * Format: key1^=^value1~key2^=^value2 with spaces~key3^=^value3~

  * Delimiter: Use ^=^ as delimiter for key and value and use ~ for different attributes.

  * Pros: You can avoid many escaping issues and keep spaces, easier to read than comma separated values.

  * Cons: Need to choose delimiter carefully to make sure it is unique.

3. URL-Encoded Key-Value Pairs:

  * Format: key1=value1&key2=value+with+spaces&key3=value3%2Cwith%2Ccommas

  * Pros: Well-established standard, handles spaces and special characters well.

  * Cons: Requires URL encoding and decoding, slightly more overhead, can be less readable.

  * Recommended Approach: Custom Delimiter with Simple Escaping

We recommend the Custom Delimiter with Simple Escaping approach for your use case. It's a good balance between simplicity, readability, and the ability to handle spaces within values. It avoids the need to rely on complex URL encoding and also avoids the unreadability issue of using comma with backslash escaping.


## JWT Security Claims

Using the tables defined above, follow these steps to create an authorization code token with user security claims:

1. **`uid`**  
   The `entity_id` (e.g., `employee_id` for employees and `customer_id` for customers) should be assigned to the `uid` claim in the JWT. This `uid` will be used by the response transformer to filter the response for the user and must represent a business identifier. 

    Examples:
    - **Employee**: Use the ACF2 ID as the `uid`.
    - **Customer**: Use the CIF ID as the `uid` (e.g., in a banking context).

2. **`role`**  
   Include a list of roles associated with the user.

3. **`grp`**  
   Add a list of groups the user belongs to.

4. **`att`**  
   Include a list of key-value pairs representing user attributes.

5. **`pos`**
   Include a list of positions for the user.

6. **`host`**
   The host of the user.

#### Example Token   

```
eyJraWQiOiJUal9sX3RJQlRnaW5PdFFiTDBQdjV3IiwiYWxnIjoiUlMyNTYifQ.eyJpc3MiOiJ1cm46Y29tOm5ldHdvcmtudDpvYXV0aDI6djEiLCJhdWQiOiJ1cm46Y29tLm5ldHdvcmtudCIsImV4cCI6MTczNDA2NDU5NSwianRpIjoicEs4WEtDZkU1aVFSdWdlQThJWXBwZyIsImlhdCI6MTczNDA2Mzk5NSwibmJmIjoxNzM0MDYzODc1LCJ2ZXIiOiIxLjAiLCJ1aWQiOiJzaDM1IiwidXR5IjoiRSIsImNpZCI6ImY3ZDQyMzQ4LWM2NDctNGVmYi1hNTJkLTRjNTc4NzQyMWU3MiIsImNzcmYiOiItTUN4OGhZRlF1bVZ3NFZkRDVHbEd3Iiwic2NwIjpbInBvcnRhbC5yIiwicG9ydGFsLnciLCJyZWYuciIsInJlZi53Il0sInJvbGUiOiJhZG1pbiB1c2VyIiwiYzEiOiIzNjEiLCJjMiI6IjY3IiwiZ3JwIjoiZGVsZXRlIGluc2VydCBzZWxlY3QgdXBkYXRlIiwiYXR0IjoiY291bnRyeV49XkNBTn5wZXJhbmVudCBlbXBsb3llZV49XnRydWV-c2VjdXJpdHlfY2xlYXJhbmNlX2xldmVsXj1eMiIsInBvcyI6IkFQSVBsYXRmb3JtRGVsaXZlcnkiLCJob3N0IjoiTjJDTXcwSEdRWGVMdkMxd0JmbG4yQSJ9.Gky_rR9hreP04GZm-0H_HBBAeDIPhQ9tsNuZclUzTdkMrYay40kcNk4jWkPdMcxfIfIbGj2eqSQgNhkBuym2yc6HsRF0nukZhYSGklVNXFe3R-0DdKwxxWyqvXyWDvrQtme0ttT2tYGTRRCZXnHDRMUFeDSz7kVjjIj3WymjFyxWBnWnBOjYqDL34652Fb8c7hWME0nSxbWO0ZvPRDhRM-l0nDGNm2ojq-3sjaU_pRywYahXP-wtnNSLwvctFgONPWSM9Ie6FqwRmYBFVo8OE0VdTRvUfnO4mL1O2UbTfxzbNJFv4HP1mSZG_SSB5j3t_RuZLfUMIajFi105ze2PUg
```

And the payload: 

```
{
  "iss": "urn:com:networknt:oauth2:v1",
  "aud": "urn:com.networknt",
  "exp": 1734064595,
  "jti": "pK8XKCfE5iQRugeA8IYppg",
  "iat": 1734063995,
  "nbf": 1734063875,
  "ver": "1.0",
  "uid": "sh35",
  "uty": "E",
  "cid": "f7d42348-c647-4efb-a52d-4c5787421e72",
  "csrf": "-MCx8hYFQumVw4VdD5GlGw",
  "scp": [
    "portal.r",
    "portal.w",
    "ref.r",
    "ref.w"
  ],
  "role": "admin user",
  "c1": "361",
  "c2": "67",
  "grp": "delete insert select update",
  "att": "country^=^CAN~peranent employee^=^true~security_clearance_level^=^2",
  "pos": "APIPlatformDelivery",
  "host": "N2CMw0HGQXeLvC1wBfln2A"
}
```

## Group and Position Management

#### Define Groups Related to User Category

You can create groups that align with teams, departments, or other organizational units. These groups are relatively static and reflect the overall organizational structure. Use a separate table, `group_t`, as described earlier, to store these groups. Groups can be applied to all users regardless of their user type.

#### Use the Employee Reporting Structure to Manage Positions

Positions are similar to groups in managing user permissions, but they leverage the organizational reporting structure to propagate permissions between team members and their direct manager.

* Position Flags

  Each position in the `position_t` table has two flags:
- **`inherit_to_ancestor`**: Determines if the position is inherited by a subordinate.
- **`inherit_to_sibling`**: Determines if the position is inherited by team members (siblings) under the same manager.

* Responsibilities

  The application is responsible for propagating positions:
- **Between Siblings**: Assigning inherited positions to team members under the same manager.
- **To the Manager**: Assigning inherited positions to the direct manager.

* User Interface for Position Management

  A user interface (UI) can be implemented to simplify position management:

- **Feature**: List all potential inherited positions for selection when adding a new user or changing a manager.
- **Functionality**: Allow administrators to choose specific positions to inherit for users and managers dynamically.

#### Use Both Groups and Positions

You can choose to use both groups and positions for your organization. However, you need to ensure that groups and positions categorize users across different dimensions. In general, groups should be used for customers, while positions should be used for employees.

#### User Login Query

Here is the query to run against the database tables upon a user login request:

```sql
SELECT
    u.user_id,
    u.user_type,
    CASE
        WHEN u.user_type = 'E' THEN e.employee_id
        WHEN u.user_type = 'C' THEN c.customer_id
        ELSE NULL
    END AS entity_id,
    CASE WHEN u.user_type = 'E' THEN string_agg(DISTINCT p.position_name, ' ' ORDER BY p.position_name) ELSE NULL END AS positions,
    string_agg(DISTINCT r.role_name, ' ' ORDER BY r.role_name) AS roles,
    string_agg(DISTINCT g.group_name, ' ' ORDER BY g.group_name) AS groups,
     CASE
        WHEN COUNT(DISTINCT at.attribute_name || '^=^' || aut.attribute_value) > 0 THEN string_agg(DISTINCT at.attribute_name || '^=^' || aut.attribute_value, '~' ORDER BY at.attribute_name || '^=^' || aut.attribute_value)
        ELSE NULL
    END AS attributes
FROM
    user_t AS u
LEFT JOIN
    user_host_t AS uh ON u.user_id = uh.user_id
LEFT JOIN
    role_user_t AS ru ON u.user_id = ru.user_id
LEFT JOIN
    role_t AS r ON ru.host_id = r.host_id AND ru.role_id = r.role_id
LEFT JOIN
    attribute_user_t AS aut ON u.user_id = aut.user_id
LEFT JOIN
    attribute_t AS at ON aut.host_id = at.host_id AND aut.attribute_id = at.attribute_id
LEFT JOIN
    group_user_t AS gu ON u.user_id = gu.user_id
LEFT JOIN
    group_t AS g ON gu.host_id = g.host_id AND gu.group_id = g.group_id
LEFT JOIN
    employee_t AS e ON uh.host_id = e.host_id AND u.user_id = e.user_id
LEFT JOIN
    customer_t AS c ON uh.host_id = c.host_id AND u.user_id = c.user_id
LEFT JOIN
    employee_position_t AS ep ON e.host_id = ep.host_id AND e.employee_id = ep.employee_id
LEFT JOIN
    position_t AS p ON ep.host_id = p.host_id AND ep.position_id = p.position_id
WHERE
    u.email = 'steve.hu@lightapi.net'
GROUP BY
    u.user_id, u.user_type, e.employee_id, c.customer_id;
```

And here is an example result from the test database:

```
utgdG50vRVOX3mL1Kf83aA  E   sh35    APIPlatformDelivery admin user  delete insert select update country^=^CAN~peranent employee^=^true~security_clearance_level^=^2
```

#### Parse Attribute String

The query above returns attributes in a customized format. These attributes can be parsed using the `Util.parseAttributes` method available in the **light-4j utility module**


## Portal View and Default Role

Given the flexibility of fine-grained authorization approaches, users can choose one or more methods to suit their business requirements. However, in scenarios where **RBAC (Role-Based Access Control)** is not utilized, the `role` claim may not exist in the custom claims of the JWT token.

#### Handling Missing `role` in JWT
For the **portal-view** application, at least one role is required to filter menu items. To address cases where no roles are present in the JWT:

1. **Default Role Assignment**:  
   If the `role` claim is absent in the JWT, the system will:
   - Assign a default role, `"user"`, to ensure compatibility.
   - Include this role in a `roles` field in the browser cookie.

2. **Cookie Roles Field**:  
   - The `roles` field in the cookie will contain a single role: `"user"`.
   - This ensures the **portal-view** can still function as expected by displaying the appropriate menu items for users.

#### Example Workflow
1. A user authenticates, and their JWT is generated without a `role` claim.  
2. During authentication handling:
   - The StatelessAuthHandler checks for the presence of the `role` claim.
   - If no roles are found, the `"user"` role is added to the `roles` field in the cookie.  
3. The **portal-view** reads the `roles` field from the cookie to filter menu items appropriately. 

This approach provides a seamless experience while maintaining compatibility with applications requiring roles for authorization or UI customization.

