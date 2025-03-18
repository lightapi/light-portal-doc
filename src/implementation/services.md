# Portal Services
This section provides an overview of the services utilized by Light Portal. Each service is implemented as a separate repository and is initialized during the hybrid-query or hybrid-command startup process. These services are designed to handle specific functionalities within the portal and may interact with one another to execute complex operations.

Light Portal adopts the Command Query Responsibility Segregation (CQRS) pattern, categorizing services into two types: Query and Command. Query services manage read operations, while Command services handle write operations, ensuring a clear separation of responsibilities.

## Attribute Service
### Attribute Query Service
Handles queries related to attributes.

#### Important Links
  - [Github Link](https://github.com/lightapi/attribute-query)
  - [Design Doc](./services/attribute-query.md)

#### Services Used
**--**

### Attribute Command Service
Handles commands related to attributes.

#### Important Links
  - [Github Link](https://github.com/lightapi/attribute-command)
  - [Design Doc](./services/attribute-command.md)

#### Services Used
- `user-query`

* * *

## Client Service
### Client Query Service
Handles queries related to clients.

#### Important Links
  - [Github Link](https://github.com/lightapi/client-query)
  - [Design Doc](./services/client-query.md)

#### Services Used
**--**

### Client Command Service
Handles commands related to clients.

#### Important Links
  - [Github Link](https://github.com/lightapi/client-command)
  - [Design Doc](./services/client-command.md)

#### Services Used
- `user-query`

* * *

## Config Service
### Config Query Service
Handles queries related to configurations.

#### Important Links
  - [Github Link](https://github.com/lightapi/config-query)
  - [Design Doc](./services/config-query.md)

#### Services Used
**--**

### Config Command Service
Handles commands related to configurations.

#### Important Links
  - [Github Link](https://github.com/lightapi/config-command)
  - [Design Doc](./services/config-command.md)

#### Services Used
- `user-query`
- `config-query`

* * *

## Deployment Service
### Deployment Query Service
Handles queries related to deployments.

#### Important Links
  - [Github Link](https://github.com/lightapi/deployment-query)
  - [Design Doc](./services/deployment-query.md)

#### Services Used
**--**

### Deployment Command Service
Handles commands related to deployments.

#### Important Links
  - [Github Link](https://github.com/lightapi/deployment-command)
  - [Design Doc](./services/deployment-command.md)

#### Services Used
- `user-query`

* * *

## Group Service
### Group Query Service
Handles queries related to groups.

#### Important Links
  - [Github Link](https://github.com/lightapi/group-query)
  - [Design Doc](./services/group-query.md)

#### Services Used
**--**

### Group Command Service
Handles commands related to groups.

#### Important Links
  - [Github Link](https://github.com/lightapi/group-command)
  - [Design Doc](./services/group-command.md)

#### Services Used
- `user-query`

* * *

## Host Service
### Host Query Service
Handles queries related to hosts.

#### Important Links
  - [Github Link](https://github.com/lightapi/host-query)
  - [Design Doc](./services/host-query.md)

#### Services Used
**--**

### Host Command Service
Handles commands related to hosts.

#### Important Links
  - [Github Link](https://github.com/lightapi/host-command)
  - [Design Doc](./services/host-command.md)

#### Services Used
- `user-query`

* * *

## Instance Service
### Instance Query Service
Handles queries related to instances.

#### Important Links
  - [Github Link](https://github.com/lightapi/instance-query)
  - [Design Doc](./services/instance-query.md)

#### Services Used
**--**

### Instance Command Service
Handles commands related to instances.

#### Important Links
  - [Github Link](https://github.com/lightapi/instance-command)
  - [Design Doc](./services/instance-command.md)

#### Services Used
- `user-query`

* * *

## OAuth Service
### OAuth Query Service
Handles queries related to OAuth.

#### Important Links
  - [Github Link](https://github.com/lightapi/oauth-query)
  - [Design Doc](./services/oauth-query.md)

#### Services Used
**--**

### OAuth Command Service
Handles commands related to OAuth.

#### Important Links
  - [Github Link](https://github.com/lightapi/oauth-command)
  - [Design Doc](./services/oauth-command.md)

#### Services Used
- `user-query`
- `oauth-query`

* * *

## Position Service
### Position Query Service
Handles queries related to positions.

#### Important Links
  - [Github Link](https://github.com/lightapi/position-query)
  - [Design Doc](./services/position-query.md)

#### Services Used
**--**

### Position Command Service
Handles commands related to positions.

#### Important Links
  - [Github Link](https://github.com/lightapi/position-command)
  - [Design Doc](./services/position-command.md)

#### Services Used
- `user-query`

* * *

## Product Service
### Product Query Service
Handles queries related to products.

#### Important Links
  - [Github Link](https://github.com/lightapi/product-query)
  - [Design Doc](./services/product-query.md)

#### Services Used
**--**

### Product Command Service
Handles commands related to products.

#### Important Links
  - [Github Link](https://github.com/lightapi/product-command)
  - [Design Doc](./services/product-command.md)

#### Services Used
- `user-query`

* * *

## Role Service
### Role Query Service
Handles queries related to roles.

#### Important Links
  - [Github Link](https://github.com/lightapi/role-query)
  - [Design Doc](./services/role-query.md)

#### Services Used
**--**

### Role Command Service
Handles commands related to roles.

#### Important Links
  - [Github Link](https://github.com/lightapi/role-command)
  - [Design Doc](./services/role-command.md)

#### Services Used
- `user-query`

* * *

## Rule Service
### Rule Query Service
Handles queries related to rules.

#### Important Links
  - [Github Link](https://github.com/lightapi/rule-query)
  - [Design Doc](./services/rule-query.md)

#### Services Used
- `service-query`

### Rule Command Service
Handles commands related to rules.

#### Important Links
  - [Github Link](https://github.com/lightapi/rule-command)
  - [Design Doc](./services/rule-command.md)

#### Services Used
- `user-query`
- `host-query`

* * *

## Service Service
### Service Query Service
Handles queries related to services.

#### Important Links
  - [Github Link](https://github.com/lightapi/service-query)
  - [Design Doc](./services/service-query.md)

#### Services Used
**--**

### Service Command Service
Handles commands related to services.

#### Important Links
  - [Github Link](https://github.com/lightapi/service-command)
  - [Design Doc](./services/service-command.md)

#### Services Used
- `user-query`

* * *

## User Service
### User Query Service
Handles queries related to users.

#### Important Links
  - [Github Link](https://github.com/lightapi/user-query)
  - [Design Doc](./services/user-query.md)

#### Services Used
**--**

### User Command Service
Handles commands related to users. 

#### Important Links
  - [Github Link](https://github.com/lightapi/user-command)
  - [Design Doc](./services/user-command.md)

#### Services Used
- `user-query`
- `service-query`

