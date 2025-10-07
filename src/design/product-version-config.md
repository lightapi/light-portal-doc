# Product Version Config

When using light-portal to manage the configurations for Apis or Apps. The configuration can be overwritten at different level. On top of platform default, the production level and production version level are utilized very often. 

There are two options: 

1. Extract the config files from the product jar and create the events for mapping. This includes all config and config properties in the jar file per product and product version. 

Pros: 
* Can be automatically done with a process.
* Standardized and hardly make mistakes.

Cons:
* It cannot be customized per organization.


2. Manually create events for mappings per product and per product version for the properties that is potentially changeable.

Pros: 

* Flexible and customizable per organization.
* Can be improved in a process.


Cons:

* May take some time to create and maintain the event file for every release.








