# Rule Query Service
- [Github Link](https://github.com/lightapi/rule-query)

## 1. GetRule Handler

### Key Steps
1. **Extracting Data**: Extracts various fields such as `offset`, `limit`, `hostId`, `ruleId`, `ruleName`, `ruleVersion`, `ruleType`, `ruleGroup`, `ruleDesc`, `ruleBody`, `ruleOwner`, and `common` from the input map.
2. **Database Query**: Queries the database for rules based on the extracted fields.
3. **Response Handling**: If the query is successful, the rules are returned as a JSON string. If the query fails, an error status is returned.

### Input
- `offset` (Integer): Record offset.
- `limit` (Integer): Record limit.
- `hostId` (String): Host identifier.
- `ruleId` (String): Rule identifier.
- `ruleName` (String): Rule name.
- `ruleVersion` (String): Rule version.
- `ruleType` (String): Rule type.
- `ruleGroup` (String): Rule group.
- `ruleDesc` (String): Rule description.
- `ruleBody` (String): Rule body.
- `ruleOwner` (String): Rule owner.
- `common` (String): Common field.

### Output
- ByteBuffer containing the JSON string of the rules or an error status.

### Endpoint
- `lightapi.net/rule/getRule/0.1.0`

## 2. GetRuleByApiId Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `apiId`, and `apiVersion` from the input map.
2. **Database Query**: Queries the database for rules associated with the given API ID.
3. **Response Handling**: If the query is successful, the rules are returned as a JSON string. If the query fails, an error status is returned.

### Input
- `hostId` (String): Host identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.

### Output
- ByteBuffer containing the JSON string of the rules or an error status.

### Endpoint
- `lightapi.net/rule/getRuleByApiId/0.1.0`

## 3. GetRuleByGroup Handler

### Key Steps
1. **Extracting Data**: Extracts `host` and `groupId` from the input map.
2. **Database Query**: Queries the database for rules associated with the given group ID.
3. **Response Handling**: If the query is successful, the rules are returned as a JSON string. If the query fails, an error status is returned.

### Input
- `host` (String): Host identifier.
- `groupId` (String): Group identifier.

### Output
- ByteBuffer containing the JSON string of the rules or an error status.

### Endpoint
- `lightapi.net/rule/getRuleByGroup/0.1.0`

## 4. GetRuleById Handler

### Key Steps
1. **Extracting Data**: Extracts `ruleId` from the input map.
2. **Database Query**: Queries the database for the rule associated with the given rule ID.
3. **Response Handling**: If the query is successful, the rule is returned as a JSON string. If the query fails, an error status is returned.

### Input
- `ruleId` (String): Rule identifier.

### Output
- ByteBuffer containing the JSON string of the rule or an error status.

### Endpoint
- `lightapi.net/rule/getRuleById/0.1.0`

## 5. GetRuleByType Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `ruleType` from the input map.
2. **Database Query**: Queries the database for rules associated with the given rule type.
3. **Response Handling**: If the query is successful, the rules are returned as a JSON string. If the query fails, an error status is returned.

### Input
- `hostId` (String): Host identifier.
- `ruleType` (String): Rule type.

### Output
- ByteBuffer containing the JSON string of the rules or an error status.

### Endpoint
- `lightapi.net/rule/getRuleByType/0.1.0`
