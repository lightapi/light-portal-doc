# light-gateway

## Client Credentials Token

All the accesses from the light-gateway to the downstream APIs should have at least one token in the Authorization header. If there is an authorization code token in the Authorization header, then a client credentials token will be added to the X-Scope-Token header by the TokenHandler. 

Since all light portal services have the same scopes (portal.r and portal.w), one token should be enough for accessing all APIs. 

Add the client credentials token config in client.yml section.

```yaml
# Client Credential
client.tokenCcUri: /oauth2/N2CMw0HGQXeLvC1wBfln2A/token
client.tokenCcClientId: f7d42348-c647-4efb-a52d-4c5787421e72
client.tokenCcClientSecret: f6h1FTI8Q3-7UScPZDzfXA
client.tokenCcScope:
  - portal.r
  - portal.w
  - ref.r
  - ref.w
```

Add TokenHandler to the handler.yml section. 

```yaml
# handler.yml
handler.handlers:
  .
  .
  .
  - com.networknt.router.middleware.TokenHandler@token
  .
  .
  .
handler.chains.default:
  .
  .
  .
  - prefix
  - token
  - router

```

Add the TokenHandler configuration token.yml section. 

```yaml
# token.yml
token.enabled: true
token.appliedPathPrefixes:
  - /r
  
```
