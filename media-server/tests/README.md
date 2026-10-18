# Media Server Tests

Pruebas locales de contratos reproducibles: configuración, montajes, identidad, imágenes fijadas, enlaces de documentación, guardas y rechazo sin `--apply`. No dependen de una descarga concreta, una cola viva ni del historial del agente.

Desde `media-server/`:

```sh
python3 -m unittest discover -s tests -v
```

Desde la raíz del repo:

```sh
sh scripts/run-tests.sh
```

Requieren Python3 estándar (3.10+ para el extractor) y Bash; no root, SSH, Docker ni RTK instalado para ejecutar la suite. No formatean discos, despliegan servicios ni contactan la VM. La integración opcional del extractor genera un MKV diminuto si `ffmpeg` y `ffprobe` están disponibles; se omite si faltan. En el entorno del agente, los comandos de shell se envuelven con RTK según AGENTS.md.

| Archivo | Contrato |
| --- | --- |
| `test_media_server.py` | Referencia VM/almacenamiento, privacidad, links y shell |
| `test_media_storage_scripts.py` | Identidad/montaje, rechazo destructivo y sintaxis Python |
| `test_ssh_public_key.py` | Validación/preservación de clave, propietarios y rechazo sin apply |
| `test_jellyfin.py` | Imagen oficial inmutable, UID/GID, LAN y biblioteca RO |
| `test_samba.py` | Sólo Movies/TV, autenticación SMB3, allowlist LAN, permisos y guarda de montaje; no contacta el servidor |
| `test_qbittorrent.py` | Montajes mínimos, WebUI/auth, capacidades verificadas separadas de límites y ausencia de inventarios temporales |
| `test_qbittorrent_reset.py` | Entrada privada, formato PBKDF2, sólo dos claves modificables, login y rechazo de estado no esperado |
| `test_torrent_cleanup.py` | Clientes falsos, preservación de completos, ventanas de progreso y gracia semanal, migración, stop/revalidación de lentos activos, rutas/hardlinks, autenticación, simulación, auditoría/estado, errores/pending y unidades sin borrado habilitado |
| `test_prowlarr.py` | Config NVMe sin HDD, autenticación nativa y fuentes guardadas |
| `test_radarr.py` | Bind común, imagen exacta, perfil HD equivalente, idiomas y renombrado |
| `test_sonarr.py` | Imagen exacta, bind común, Forms nativo, perfil HD, conexiones y separación de aceptación pendiente |
| `test_bazarr.py` | Imagen fijada, biblioteca sin downloads, LAN, bootstrap Forms privado y política bilingüe |
| `test_embedded_subtitles.py` | Selección inglesa, temporadas, ambigüedad/bitmap, rutas/symlinks, simulación, no sobrescritura, validación SRT, cambios del origen, limpieza de temporales y tiempos/texto en MKV sintético opcional |
| `test_subtitle_batches.py` | Particiones completas de hasta20, fuentes congeladas, ZIP inseguro/incompleto/residual, nombres/UTF-8/cues/tiempos, un SRT restante, integridad al reanudar y copia idempotente sin sobrescribir traducciones; sin navegador ni red |

La [validación real del flujo](../docs/validation.md) es independiente de estos tests; no se deduce de una suite local exitosa.
