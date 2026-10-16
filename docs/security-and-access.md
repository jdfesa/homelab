# Security and Access

**Updated:** 2026-10-16 (publication review; host observations remain dated2026-10-14).

## SSH Access

Desde la Mac administradora:

```sh
rtk proxy ssh proxmox-homelab
```

Para comprobar que no existe fallback a una contraseña:

```sh
rtk proxy ssh -o BatchMode=yes proxmox-homelab 'hostname; id -un'
```

La prueba devolvió `pve` y `root`. SSH sin contraseña significa **autenticación por clave**, no acceso sin autenticación. El comando convencional `ssh proxmox-homelab` también sirve; los ejemplos usan RTK según las instrucciones del entorno.

### Client Configuration

- Clave dedicada Ed25519 en `~/.ssh/id_ed25519_proxmox_homelab`, fuera del repositorio.
- Clave privada sin passphrase para permitir el acceso automático solicitado, permisos `600`.
- Alias `proxmox-homelab` en `~/.ssh/config`; configuración anterior preservada.
- `IdentitiesOnly yes`, `PreferredAuthentications publickey`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`.
- `StrictHostKeyChecking yes`; no usar `StrictHostKeyChecking=no` ante un cambio de huella.
- Sin agent forwarding ni X11 forwarding; keepalive de 30 s.

La dirección y huellas conocidas quedan en notas locales, no en los documentos públicos. No se comparó la huella con la consola física en esta sesión: se reutilizó la confianza previamente registrada en `known_hosts` para el acceso definitivo.

### Server Configuration

Se agregó una clave pública con restricciones `no-agent-forwarding,no-X11-forwarding`. Las claves anteriores se conservaron. El archivo `/root/.ssh/authorized_keys` es un enlace a `/etc/pve/priv/authorized_keys`; no reemplazar ese symlink ni sobrescribir el archivo completo.

Se guardó una copia del contenido previo en `/root/.ssh/authorized_keys.pre-homelab-20261014`. En la Mac se preservó la configuración previa en `~/.ssh/config.pre-homelab-20261014`.

No se deshabilitó la autenticación por contraseña del servidor, se cambió la contraseña root ni se reinició SSH. El alias del cliente no permite fallback, pero otros clientes siguen sujetos a la configuración existente del servidor.

### Trade-offs and Revocation

Una clave sin passphrase autorizada como root permite que quien la obtenga administre el Proxmox. Proteger la Mac con bloqueo de sesión, cifrado de disco y copias seguras; no se verificó aquí el estado de esas protecciones. Una alternativa futura es clave cifrada con agente/Keychain o clave hardware, validando primero el comportamiento desatendido requerido.

Para revocar: desde una sesión/consola alternativa verificada, retirar **solo** la línea identificada como `jd-mac-proxmox-homelab`; preservar las claves de Proxmox y otros administradores. Quitar después el bloque del alias y la clave local si ya no se necesita. No restaurar ciegamente una copia antigua, porque podría eliminar claves agregadas posteriormente.

La contraseña se compartió en el chat y no se escribió en archivos, comandos de shell ni documentos. Conviene rotarla mediante un canal privado/consola cuando se valide el acceso de recuperación; no se rotó automáticamente.

## Network Boundaries

Se observaron cero reglas nftables/iptables/ip6tables y políticas ACCEPT; no dar por habilitado el firewall porque los daemons estén running o una NIC tenga `firewall=1`. Activarlo requiere diseñar reglas, preservar SSH/web, acceso por consola y una prueba de recuperación. No se cambió durante este relevamiento.

- Mantener Proxmox, DSM y paneles administrativos fuera de exposición WAN directa.
- Revisar el dashboard en TCP 8008, rpcbind y SPICE: confirmar necesidad, autenticación y alcance.
- No se inspeccionaron router, port forwarding ni IPv6 WAN: no afirmar que no hay exposición pública.
- Antes de arrancar Windows XP, definir red aislada o NIC desconectada; no usarlo para navegar o guardar credenciales actuales.
- Para acceso remoto, evaluar VPN y ACLs antes que abrir puertos generales.

## Data Protection

- No montar ni modificar desde el host el HDD que está usando DSM.
- Resolver backups independientes antes de migraciones, reparaciones o nuevas cargas con datos valiosos.
- Verificar la cobertura del HDD físico en cualquier backup de la VM: no asumir que el disco de arranque representa todos los datos ni que un passthrough está siempre excluido.
- Un backup dentro de DSM depende de la VM para recuperación: documentar cómo recuperar datos sin ella.
- RAID, snapshots, sincronización y una copia en otro directorio del mismo disco no sustituyen un backup independiente con retención y restauración probada.

## Public Repository Checklist

Antes de publicar o compartir diffs:

- Revisar contenido e historial, no solo el estado actual de los archivos.
- No incluir claves privadas/públicas de administración, cookies, API tokens, exports completos de Proxmox/DSM ni archivos personales. Excepción expresa del propietario: únicamente el [ejemplo real qBit](../media-server/docs/qbittorrent.md#laboratory-login-example); no extenderla a otros accesos.
- Omitir seriales, MACs y destinos de backup privados; usar placeholders para direcciones reutilizables. La captura original aprobada del formulario qBit conserva una IP LAN como excepción visual, no como secreto ni control de acceso.
- Mantener `.local/`, `tmp/`, backups y exports fuera de Git.
- Usar `.env.example` únicamente con valores ficticios; nunca copiarle un `.env` real.
- Usar un detector de secretos antes del primer push y revisar los resultados manualmente.
- No usar `git add -f` para saltar los ignores por comodidad.

`.gitignore` no protege un archivo ya versionado ni borra secretos del historial. Si hay una filtración, revocar/rotar el secreto: eliminar el archivo visible no es suficiente.

La revisión local y las excepciones confirmadas al preparar GitHub público se detallan en [Public Repository Guide](publication-guide.md). Las reglas raíz se heredan en todos los módulos; media-server añade las propias de su runtime. No hubo cambios de red/servicios durante esa preparación.
