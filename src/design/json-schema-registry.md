# JSON Schema Registry

JSON Schema is a declarative language that provides a standardized way to describe and validate JSON data. 

### What it does

JSON Schema defines the structure, content, data types, and constraints of JSON documents. It's an IETF standard that helps ensure the consistency and integrity of JSON data across applications.


### How it works

JSON Schema uses keywords to define data properties. A JSON Schema validator checks if JSON documents conform to the schema. 

### What it's useful for

* Describing existing data formats
* Validating data as part of automated testing
* Submitting client data
* Defining how a record should be organized

### What is a JSON Schema Registry

The JSON Schema Registry provides a centralized service for your JSON schemas with RESTful endpoints for storing and retrieving JSON schemas. 

When using data in a distributed application with many RESTful APIs, it is important to ensure that it is well-formed and structured. If data is sent without prior validation, errors may occur on the services. A schema registry provides a way to ensure that the data is validated before it is sent and validated after it is received. 


A schema registry is a service used to define and confirm the structure of data that is sent between consumers and providers. In a schema registry, developers can define what the data should look like and how it should be validated. The schemas can be utilized in the OpenAPI specifications to ensure that schemas can be externalized. 

Schema records can also help ensure forward and backward compatibility when changes are made to the data structure. When a schema record is used, the data transfered with more schema information that can be used to ensure that applications reading the data can interpret it. 


Given the API consumers and providers can belong to different groups or organizations, it is necessary to have a centralized service to manage the schemas so that they can be shared between them. This is why we have implemented this service as part of the light-portal. 


### Schema Specification Version

The registry is heterogeneous registry as it can store schemas of different schema draft versions. By default the registry is configured to store schemas of Draft 2020-12. When a schema is added, the version which is currently is set, is what the schema is saved as.

The following list contains all supported specification versions. 

* Draft 4
* Draft 6
* Draft 7
* 2019-09
* 2020-12

### Schema Version

Once a schema is registed into the registry, it will be assigned as version 1. Each time it is updated, the version number will increase 1. When the schema is retrieve, the version number can be part of the URL to indicate that exact version will be retrieved. If version number is not in the URL, the latest version will be retrieved. 


### Access Endpoint


### Table Structure




