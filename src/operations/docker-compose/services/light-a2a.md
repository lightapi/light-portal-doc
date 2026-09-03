# Light A2A

`light-a2a` provides optional Agent-to-Agent transport and policy enforcement.
It is placed under the `a2a` Compose profile so the base Portal stack can run
without exposing that transport.

Start it explicitly only when the environment has the required A2A identity,
signing and authorization-context material:

```bash
docker compose --profile a2a up -d
```

## Configuration boundary

The service uses its own Config Server/runtime identity, operational database
role, artifact storage and authorization-context key. Other services may mount
the same key generation through their own protected files, but they should not
share writable secret directories.

The operational bootstrap and runtime-secret initialization jobs must complete
before A2A starts. An open port is not sufficient readiness; verify its policy
generation, signing identity, operational binding and registration.

