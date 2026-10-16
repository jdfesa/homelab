# Media Server Tests

Local tests owned by this VM module. They check reference configuration, public links/privacy, shell syntax, pure storage guards and refusal without explicit `--apply`.

From `media-server/`:

```sh
python3 -m unittest discover -s tests -v
```

Requirements: a Unix-like environment (Linux/macOS), Python 3 standard library and Bash. No root, SSH, Docker daemon, extra Python packages or RTK installation is needed. The tests never format disks or provision a server. They exclude ignored private/runtime directories from public-document scans.

- `test_media_server.py`: configuration, storage status, links, privacy, shell syntax and network-script refusal.
- `test_media_storage_scripts.py`: pure identity/mount guards, destructive-script refusal and Python syntax.
- `test_ssh_public_key.py`: public-key validation, preservation/idempotence, ownership guards and refusal without `--apply`; no SSH or real account changes.
- `test_jellyfin.py`: pure deployment-contract tests for pinned official image, non-root identity, assigned LAN IPv4, NVMe appdata, read-only library and explicit `--apply`; no Docker or network access.

- `test_qbittorrent.py`: contrato puro de imagen inmutable, montajes mínimos, identidad, WebUI LAN, UPnP/auth inicial y guía canónica por servicio en `docs/`; sin despliegue ni HTTP.

- `test_qbittorrent_reset.py`:8 pruebas puras de recuperación WebUI: longitud/entrada, formato PBKDF2/QSettings de la versión fijada, sólo dos claves modificables, rechazo de estructura no esperada, login204/200legacy, digest coherente y rechazo sin `--apply`. No cambia credenciales ni inicia contenedores.

- `test_prowlarr.py`: contrato puro de imagen/identidad/configNVMe/puertoLAN, rechazo de override de autenticación, bootstrap y documentación; confirmaciones de contraseña qBit y ninguna descarga manual.

- `test_radarr.py`:10 pruebas locales del primer despliegue: digest exacto, identidad/mediaGID, único `/data` común sin mounts separados, puerto7878 RFC1918 asignado, autenticación nativa/actualizacionesDocker, rechazo sin `--apply` y documentación/lock coherentes. No inicia contenedores ni modifica medios.

Actual mounts, service guards, reboots and application imports are separate acceptance tests documented in [Storage Guide](../docs/storage-guide.md) and [Roadmap](../ROADMAP.md). To run all repository suites, use the shared [test runner](../../scripts/README.md).
