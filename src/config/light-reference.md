# light-reference

## Cors Configuration

As the light-gateway is handling the SPA interaction and cors, we don't need to enable the cors on the reference API. However, the cors handler is still registered in the default handler.yml in case the reference API is used as a standalone service. 

In the light-portal configuration, we need to disable the cors. 

```yaml
# cors.yml
cors.enabled: false
```

## Client Configuration

We need to load the jwk from the oauth-kafka service to validate the incoming jwk tokens. To set up the jwk, add the following lines to the values.yml file.

```yaml
# client.yml
client.tokenKeyServerUrl: https://localhost:6881
client.tokenKeyUri: /oauth2/N2CMw0HGQXeLvC1wBfln2A/keys
```


