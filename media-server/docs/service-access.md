# Service Access Directory

**Updated:** 2026-10-16. Catálogo de interfaces web de los servicios ya desplegados en la VM Debian `media-server`.

## One VM Address, Different Ports

Los servicios actuales comparten **la IP LAN de la VM Debian** y se distinguen por su **puerto publicado**. Desde tablet/computadora se usa `http://<IP_DE_LA_VM>:<PUERTO>`; no la IP interna del contenedor ni necesariamente la IP del host Proxmox, que es otro equipo lógico.

| Service | Function | Web port | LAN URL | Canonical guide |
| --- | --- | --- | --- | --- |
| Jellyfin | Biblioteca y reproducción | TCP8096 | `http://<IP_DE_LA_VM>:8096` | [Jellyfin](jellyfin.md) |
| qBittorrent | Cliente de descargas | TCP8080 | `http://<IP_DE_LA_VM>:8080` | [qBittorrent](qbittorrent.md) |
| Prowlarr | Administración de indexadores | TCP9696 | `http://<IP_DE_LA_VM>:9696` | [Prowlarr](prowlarr.md) |
| Radarr | Gestión de películas | TCP7878 | `http://<IP_DE_LA_VM>:7878` | [Radarr](radarr.md) |

Los puertos coinciden con los manifiestos Compose de estos servicios. Radarr ya está desplegado, con cuenta Forms/Enabled y raíz de películas verificadas; integraciones pendientes. Este catálogo no enumera todos los puertos internos ni afirma que el flujo completo de descargas/reproducción esté probado. Sonarr y otros servicios se añadirán **cuando se desplieguen**, no como accesos ya disponibles.

### Default Versus Published Port

Los puertos de la tabla coinciden con los valores predeterminados de las imágenes usadas, pero **no son inmutables**: la aplicación puede permitir configurar su puerto y Docker puede publicar un puerto de la VM distinto del interno. El navegador utiliza el **puerto publicado en la VM**. Si dos servicios necesitan la misma IP/puerto/protocolo, hay que resolver ese conflicto, por ejemplo publicando uno en otro puerto.

Usar **`http://<IP_DE_LA_VM>:9696`** como ejemplo de Prowlarr: sustituir sólo el placeholder por la IP real de esa instalación. Es más claro que una dirección parcialmente enmascarada; no se debe copiar literalmente como si fuera una URL válida. Registrar siempre lo que declara y publica el Compose, no sólo el supuesto valor por defecto. Actualmente se mantienen8096/8080/9696/7878; no se propone cambiarlos.

Referencias: [Jellyfin networking](https://jellyfin.org/docs/general/post-install/networking/), [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/) y [LinuxServer Prowlarr](https://docs.linuxserver.io/images/docker-prowlarr/).

## Site-Specific Addresses

Las URLs reales y clicables de esta instalación están en **`media-server/.local/service-access.md`**, archivo local excluido del versionado por la regla existente `.local/`. En otra instalación, sustituir `<IP_DE_LA_VM>` por su propia dirección. No incluir contraseñas, tokens o API keys en URLs ni en este catálogo.

### Is a Private IP a Secret?

**Una IP privada no es una credencial ni, por sí sola, una forma de entrar desde Internet.** Los rangos privados se reutilizan en redes distintas y no son direcciones globalmente alcanzables en Internet. Referencia: [RFC1918, Private Address Space](https://www.rfc-editor.org/rfc/rfc1918#section-3) e [IANA IPv4 Special-Purpose Address Space](https://www.iana.org/assignments/iana-ipv4-special-registry/).

Publicar qué IP/puerto corresponde al panel administrativo revela parte del mapa interno. Puede aportar contexto a alguien que ya tenga una vía de acceso, pero no abre esa vía ni equivale a filtrar una contraseña. Ser una dirección privada tampoco sustituye autenticación o controles de red: una publicación mediante router/proxy u otro acceso puede hacer alcanzable el servicio sin cambiar su IP interna.

**Convención de este proyecto:** usar placeholders en la guía pública y valores reales en el archivo local, por reutilización y minimización de detalles del sitio. No porque una IP LAN deba tratarse como secreto crítico. Ocultar la dirección no es un control de seguridad y publicar sólo esa dirección no justifica afirmar que el servidor quedó comprometido. Esta documentación no es una auditoría de exposición actual.

## Update Rule

Al desplegar un servicio nuevo o cambiar un puerto:

1. Confirmar protocolo y **puerto publicado en la VM** en su Compose.
2. Actualizar esta tabla y el catálogo local con la URL real.
3. Mantener su guía propia en `docs/<servicio>.md`, enlazada desde aquí.
4. Registrar el estado comprobado sin presentar servicios futuros como desplegados.

No abrir puertos del router ni modificar la red por el hecho de documentar estos accesos.

**Referencia visual puntual:** por pedido del propietario, el [formulario original Radarr→qBit](radarr.md#reviewed-qbittorrent-client-form--test-passed) conserva la IP LAN de ese laboratorio. No es una URL de plantilla ni un valor que otra persona deba copiar; el catálogo y los ejemplos textuales mantienen placeholders.
