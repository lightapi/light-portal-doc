# Fine-Grained Authorization

## What is Fine-Grained Authorization?
Fine-grained authorization (FGA) refers to a detailed and precise control mechanism that governs access to resources based on specific attributes, roles, or rules. It's also known as fine-grained access control (FGAC). Unlike coarse-grained authorization, which applies broader access policies (e.g., "Admins can access everything"), fine-grained authorization allows for more specific policies (e.g., "Admins can access user data only if they belong to the same department and the access request is during business hours").

### Key Features
- **Granular Control**: Policies are defined at a detailed level, considering attributes like user role, resource type, action, time, location, etc.
- **Context-Aware**: Takes into account dynamic conditions such as the time of request, user’s location, or other contextual factors.
- **Flexible Policies**: Allows the creation of complex, conditional rules tailored to the organization’s needs.

## Why Do We Need Fine-Grained Authorization?

### 1. **Enhanced Security**
By limiting access based on detailed criteria, fine-grained authorization minimizes the risk of unauthorized access or data breaches.

### 2. **Regulatory Compliance**
It helps organizations comply with legal and industry-specific regulations (e.g., GDPR, HIPAA) by ensuring sensitive data is only accessible under strict conditions.

### 3. **Minimized Attack Surface**
By restricting access to only the required resources and operations, fine-grained authorization reduces the potential impact of insider threats or compromised accounts.

### 4. **Improved User Experience**
Enables personalized access based on roles and permissions, ensuring users see only what they need, which reduces confusion and improves productivity.

### 5. **Auditing and Accountability**
Detailed access logs and policy enforcement make it easier to track and audit who accessed what, when, and why, fostering better accountability.

## Examples of Use Cases
- **Healthcare**: A doctor can only view records of patients they are treating.
- **Government**: A government employee can access to data and documents based on security clearance levels and job roles.
- **Finance**: A teller can only access transactions related to their assigned branch.
- **Enterprise Software**: Employees can edit documents only if they own them or have been granted editing permissions.

## Fine-Grained Authorization in API Access Control

In API access control, fine-grained authorization governs how users or systems interact with specific API endpoints, actions, and data. This approach ensures that access permissions are precisely tailored to attributes, roles, and contextual factors, enabling a secure and customized API experience. As the Light Portal is a platform centered on APIs, the remainder of the design will focus on the API access control context.

## Early Approaches to Fine Grained Authorization

Early approaches to fine grained authorization primarily involved Access Control Lists (ACLs) and Role-Based Access Control (RBAC). These methods laid the foundation for more sophisticated access control mechanisms that followed. Here's an overview of these primary approaches:

### Access Control Lists (ACLs):

* ACLs were one of the earliest forms of fine grained authorization, allowing administrators to specify access permissions on individual resources for each user or group of users.

* In ACLs, permissions are directly assigned to users or groups, granting or denying access to specific resources based on their identities.

* While effective for small-scale environments with limited resources and users, ACLs became cumbersome as organizations grew. Maintenance issues arose, such as the time required to manage access to an increasing number of resources for numerous users.

### Role-Based Access Control (RBAC):

* RBAC emerged as a solution to the scalability and maintenance challenges posed by ACLs. It introduced the concept of roles, which represent sets of permissions associated with particular job functions or responsibilities.

* Users are assigned one or more roles, and their access permissions are determined by the roles they possess rather than their individual identities.

* RBAC can be implemented with varying degrees of granularity. Roles can be coarse-grained, providing broad access privileges, or fine-grained, offering more specific and nuanced permissions based on organizational needs.

* Initially, RBAC appeared to address the limitations of ACLs by providing a more scalable and manageable approach to access control.

### Both ACLs and RBAC have their shortcomings:

* Maintenance Challenges: While RBAC offered improved scalability compared to ACLs, it still faced challenges with role management as organizations expanded. The proliferation of roles, especially fine grained ones, led to a phenomenon known as **role explosion** where the number of roles grew rapidly, making them difficult to manage effectively.

* Security Risks: RBAC's flexibility also posed security risks. Over time, users might accumulate permissions beyond what they need for their current roles, leading to a phenomenon known as **permission creep**. This weakened overall security controls and increased the risk of unauthorized access or privilege misuse.

Following the discussion of early approaches to fine grained authorization, it's crucial to acknowledge that different applications have varying needs for authorization.

Whether to use fine grained or coarse-grained controls depends on the specific project. Controlling access becomes trickier due to the spread-out nature of resources and differing levels of detail needed across components. Let’s delve into the differentiating factors:

## Standard Models for Implementing FGA

There are several standard models for implementing FGA:

* `Attribute-Based Access Control (ABAC)`: In [ABAC](https://en.wikipedia.org/wiki/Attribute-based_access_control), access control decisions are made by evaluating attributes such as user roles, resource attributes (e.g., type, size, status), requested action, current date and time, and any other relevant contextual information. ABAC allows for very granular control over access based on a wide range of attributes.

* `Policy-Based Access Control (PBAC)`: [PBAC](https://www.nextlabs.com/what-is-policy-based-access-control/) is similar to ABAC but focuses more on defining policies than directly evaluating attributes. Policies in PBAC typically consist of rules or logic that dictate access control decisions based on various contextual factors. While ABAC relies heavily on data (attributes), PBAC emphasizes using logic to determine access.

* Relationship-Based Access Control (ReBAC): [ReBAC](https://en.wikipedia.org/wiki/Relationship-based_access_control) emphasizes the relationships between users and resources, as well as relationships between different resources. By considering these relationships, ReBAC provides a powerful and expressive model for describing complex authorization contexts. This can involve the attributes of users and resources and their interactions and dependencies.

Each of these models offers different strengths and may be more suitable for different scenarios. FGA allows for fine grained control over access, enabling organizations to enforce highly specific access policies tailored to their requirements.

## Streamlining FGA by Implementing Rule-Based Access Control:

ABAC (Attribute-Based Access Control) focuses on data attributes, PBAC (Policy-Based Access Control) centers on logic, and ReBAC (Relationship-Based Access Control) emphasizes relationships between users and resources. But what if we combined all three to leverage the strengths of each? This is the idea behind **Rule-Based Access Control (RuBAC)**.

By embedding a lightweight rule engine, we can integrate multiple rules and actions to achieve the following:

- **Optimize ABAC**: Reduce the number of required attributes since not all rules depend on them. For example, a standard rule like *"Customer data can only be accessed during working hours"* can be shared across policies.

- **Flexible Policy Enforcement**: Using a rule engine makes access policies more dynamic and simpler to manage.

- **Infer Relationships**: Automatically deduce relationships between entities. For instance, the rule engine could grant a user access to a file if they already have permission for the containing folder.


## Principle of Least Privilege

The [principle of least privilege access control](https://www.cyberark.com/what-is/least-privilege/) widely referred to as least privilege, and PoLP is the security concept in which user(s) (employee(s)) are granted the minimum level of access/permissions to the app, data, or system that is required to perform his/her job functions.

To ensure PoLP is effectively enforced, we've compiled a list of best practices:

* **Conduct a thorough privilege audit**: As we know, visibility is critical in an access environment, so conducting regular or periodic access audits of all privileged accounts can help your team gain complete visibility. This audit includes reviewing privileged accounts and credentials held by employees, contractors, and third-party vendors, whether on-premises, accessible remotely, or in the cloud. However, your team must also focus on default and hard-coded credentials, which IT teams often overlook.

* **Establish the least privilege as the default**: Start by granting new accounts the minimum privileges required for their tasks and eliminate or reconfigure default permissions on new systems or applications. Further, use role-based access control to help your team determine the necessary privileges for a new account by providing general guidelines based on roles and responsibilities. Also, your team needs to update and adjust access level permissions when the user's role changes; this will help prevent privilege creep.

* **Enforce separation of privileges**: Your team can prevent over-provisioning by limiting administrator privileges. Firstly, segregate administrative accounts from standard accounts, even if they belong to the same user, and isolate privileged user sessions. Then, grant administrative privileges (such as read, write, and execute permissions) only to the extent necessary for the user to perform their specific administrative tasks. This will help your team prevent granting users unnecessary or excessive control over critical systems, which could lead to security vulnerabilities or misconfigurations.

* **Provide just-in-time, limited access**: To maintain least-privilege access without hindering employee workflows, combine role-based access control with time-limited privileges. Further, replace hard-coded credentials with dynamic secrets or use one-time-use/temporary credentials. This will help your team grant temporary elevated access permissions when users need it, for instance, to complete specific tasks or short-term projects.

* **Keep track and evaluate privileged access**: Continuously monitor authentications and authorizations across your API platform and ensure all the individual actions are traceable. Additionally, record all authentication and authorizaiton sessions comprehensively, and use automated tools to swiftly identify any unusual activity or potential issues. These best practices are designed to enhance the security of your privileged accounts, data, and assets while ensuring compliance adherence and improving operational security without disrupting user workflows.

## OpenAPI Specification Extensions

OpenAPI uses the term security scheme for authentication and authorization schemes. OpenAPI 3.0 lets you describe APIs protected using the following [security schemes](https://swagger.io/docs/specification/v3_0/authentication/). The fine-grained authorization is just another layer of security and it is natural to define the fine-grained authorization in the same specification. It can be done with OpenAPI specification extensions.

Extensions (also referred to as specification extensions or vendor extensions) are custom properties that start with x-, such as x-logo. They can be used to describe extra functionality that is not covered by the standard OpenAPI Specification. Many API-related products that support OpenAPI make use of extensions to document their own attributes, such as Amazon API Gateway, ReDoc, APIMatic and others.

As OpenAPI specification openapi.yaml is loaded during the light-4j startup, the extensions will be available at runtime in cache for each endpoint just like the scopes definition. The API owner can define the following two extensions for each endpoint:

* **x-request-access**: This section allows designer to specify one or more **rules** as well as one or more security **attributes** for the input of the rules. For example, roles, location etc. The rule result will decide if the user has access to the endpoint based on the security attributes from the JWT token in the request chain.

* **x-response-filter**: This section is similar to the above; however, it works on the response chain. The rule result will decide which row or column of the response JSON will return to the user based on the security profile from the JWT token.

Example of OpenAPI specification with fine-grained authorization.

```
paths:
  /accounts:
    get:
      summary: "List all accounts"
      operationId: "listAccounts"
      x-request-access:
        rule: "account-cc-group-role-auth"
        roles: "manager teller customer"
      x-response-filter:
        rule: "account-row-filter"
        teller:
          status: open
        customer:
          status: open
          owner: @user_id
        rule: "account-col-filter"
          teller: ["num","owner","type","firstName","lastName","status"]
          customer: ["num","owner","type","firstName","lastName"]
      security:
      - account_auth:
        - "account.r"

```


## FGA Rules for AccessControlHandler

With the above specification loaded during the runtime, the rules will be loaded during the server startup for the service as well. In the Rule Registry on the light-portal, we have a set of built-in rules that can be picked as fine-grained policies for each API. Here is an example of rule for the above specification in the x-request-access.

```
account-cc-group-role-auth:
  ruleId: account-cc-group-role-auth
  host: lightapi.net
  description: Role-based authorization rule for account service and allow cc token and transform group to role.
  conditions:
    - conditionId: allow-cc
      variableName: auditInfo
      propertyPath: subject_claims.ClaimsMap.user_id
      operatorCode: NIL
      joinCode: OR
      index: 1
    - conditionId: manager
      variableName: auditInfo
      propertyPath: subject_claims.ClaimsMap.groups
      operatorCode: CS
      joinCode: OR
      index: 2
      conditionValues:
        - conditionValueId: manager
          conditionValue: admin
    - conditionId: teller
      variableName: auditInfo
      propertyPath: subject_claims.ClaimsMap.groups
      operatorCode: CS
      joinCode: OR
      index: 3
      conditionValues:
        - conditionValueId: teller
          conditionValue: frontOffice
    - conditionId: allow-role-jwt
      variableName: auditInfo
      propertyPath: subject_claims.ClaimsMap.roles
      operatorCode: NNIL
      joinCode: OR
      index: 4
  actions:
    - actionId: match-role
      actionClassName: com.networknt.rule.FineGrainedAuthAction
      actionValues:
        - actionValueId: roles
          value: $roles

```

All rules are managed by the light-portal and shared by all the services. In addition, developers can create their customized rules for their own services.

## Response Filter

There are two type of filters. Row and Column. 


#### Row

For row filter, we need to check the condition defined for some of the properties in order to make the filter decision. In database, for each endpoint, we have colName, operator and colValue defined for the condition. 

The operator supports the following enum: ["=","!=","<",">","<=",">=","in","not in", "range"]

For the colValue, we do support variables from the jwt token with @. For example, @eid will be replaced with the eid claim from the jwt token. 


#### Col

For column filter, we need to include a list of columns or exclude a list of columns in json format.

["accountNo","firstName","lastName"]

or 

!["status"]


