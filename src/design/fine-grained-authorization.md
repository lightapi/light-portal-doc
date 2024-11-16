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

### Streamlining FGA by Implementing Rule-Based Access Control:

ABAC (Attribute-Based Access Control) focuses on data attributes, PBAC (Policy-Based Access Control) centers on logic, and ReBAC (Relationship-Based Access Control) emphasizes relationships between users and resources. But what if we combined all three to leverage the strengths of each? This is the idea behind **Rule-Based Access Control (RBAC)**.

By embedding a lightweight rule engine, we can integrate multiple rules and actions to achieve the following:  

- **Optimize ABAC**: Reduce the number of required attributes since not all rules depend on them. For example, a standard rule like *"Customer data can only be accessed during working hours"* can be shared across policies.  

- **Flexible Policy Enforcement**: Using a rule engine makes access policies more dynamic and simpler to manage.  

- **Infer Relationships**: Automatically deduce relationships between entities. For instance, the rule engine could grant a user access to a file if they already have permission for the containing folder.  

