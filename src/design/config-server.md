# Config Server

### Default Config Properties

For each config class in light-4j modules, we use annotations to generate schemas for the config files with default values, comments and validation rules.

As one time step, we also generate events to input all the properties into the light-portal. These events will create a base-line of the config properties with default values. All events in this first time population doesn't have a version. 

For each version release, we will create and attach an event.json file with the change to the properties. Most likely, we will add some properties with default values for each release. All events in the is file will have a version associated. Once played on the portal, updates for the version will be populated. 

On the portal ui, we load all properties and default values from database with a union of the base-line properties and all versions below and equal to the current version. 







