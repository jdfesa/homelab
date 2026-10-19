# Homepage Tests

Offline contracts for the published source lock, service hardening, configuration templates and documentation ownership. They do not access private runtime files or connect to the server.

From the repository root:

```sh
rtk proxy python3 -m unittest discover -s homepage/tests -v
```

Passing these tests does not prove deployment, HTTP access, performance or restoration. Runtime verification belongs in the [service setup guide](../docs/service-setup.md).
