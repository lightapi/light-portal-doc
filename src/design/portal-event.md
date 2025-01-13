# Portal Event

Light Portal is using event sourcing and CQRS. Any update to the system will generate an event and there are hundreds of event types. 

All events are in Avro format and will be pushed to a Kafka cluster for stream processing. Each event has an EventId that contains common info for events and it is reside in light-kafka repo. 

Here is one of the events in the light-portal.

```
{
  "type": "record",
  "name": "ApiRuleCreatedEvent",
  "namespace": "net.lightapi.portal.market",
  "fields": [
    {
      "name": "EventId",
      "type": {
        "type": "record",
        "name": "EventId",
        "namespace": "com.networknt.kafka.common",
        "fields": [
          {
            "name": "id",
            "type": "string",
            "doc": "a unique identifier"
          },
          {
            "name": "nonce",
            "type": "long",
            "doc": "the number of the transactions for the user"
          },
          {
            "name": "timestamp",
            "type": "long",
            "default": 0,
            "doc": "time the event is recorded"
          },
          {
            "name": "derived",
            "type": "boolean",
            "default": false,
            "doc": "indicate if the event is derived from event processor"
          }
        ]
      }
    },
    {
      "name": "hostId",
      "type": "string",
      "doc": "host id"
    },
    {
      "name": "apiId",
      "type": "string",
      "doc": "api id"
    },
    {
      "name": "ruleIds",
      "type": {
        "type": "array",
        "items": "string"
      },
      "doc": "one or many rule ids that link to the apiId"
    }
  ]
}

```

## Kafka Key

When pushing events into a Kafka topic, the record key will be used to distribute record between different Kafka partitions. Here is the key selection for the system. 

* multi-tenent

The key will be the hostId

* single-tenent

The key will be the userId

