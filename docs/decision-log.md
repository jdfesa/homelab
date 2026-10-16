# Decision Log

## Accepted Decisions

| Date | Decision | Reason / effect |
| --- | --- | --- |
| 2026-10-14 | Construcción gradual orientada a comodidad doméstica | Explorar todos los usos sin imponer prioridad definitiva ni instalar todo de golpe |
| 2026-10-14 | Mantener el nombre `homelab` | Describe adecuadamente un entorno doméstico de aprendizaje y servicios; `home server` enfatiza su utilidad cotidiana |
| 2026-10-14 | README inglés; documentos español, títulos inglés, nombres inglés kebab-case | Preferencia editorial explícita del usuario |
| 2026-10-14 | Separar documentos revisados de captures/notas privadas; ignorar `tmp/` | Preparar publicación futura sin exponer información sensible |
| 2026-10-14 | Configurar clave Ed25519 dedicada y alias SSH desde la Mac | Acceso automático solicitado, probado con BatchMode |
| 2026-10-14 | Inventario de hardware inicial/parcial | El usuario todavía debe conectar HDD adicionales |
| 2026-10-15 | Un módulo autocontenido por VM/LXC con README propio | Raíz limpia para índice y elementos compartidos; guías, roadmap, scripts, pruebas y decisiones operativas pertenecen al módulo |
| 2026-10-15 | Consolidar convenciones Compose en docs y separar pruebas/evidencia por dueño | Sin `docker/` global paralelo ni pruebas específicas en tests comunes; cada módulo mantiene su `.local/` ignorado |

| 2026-10-16 | Un servidor Proxmox y un único monorepositorio homelab | README raíz con hardware/mapa, VM/LXC en módulos; DSM y media-server en mapa, XP de prueba fuera; no inventar LXC ni crear n repos |
| 2026-10-16 | Preparación pública con ignores heredables y preflight local | Privados, runtime y claves excluidos; plantillas/locks visibles. Excepción qBit real conservada por decisión expresa del propietario; no publicar otras credenciales |
| 2026-10-16 | MIT para contenido propio; atribución separada de terceros | Elección del propietario para reutilización comunitaria; PDF público aportado se conserva, no se relicencia ni se inventan sus términos |

| 2026-10-16 | Publicar en jdfesa/homelab con historial gradual | Destino público confirmado por propietario, main y Conventional Commits en inglés por bloques coherentes; un push al final, sin force ni datos privados |

## Operating Safeguards

Durante el inventario inicial del 2026-10-14 no se instalaron apps, actualizaron sistemas, reiniciaron huéspedes, montaron datos DSM, repararon discos ni activó firewall. Se preservaron las claves existentes al autorizar SSH a Proxmox.

La cronología, autorizaciones y elecciones técnicas de la VM multimedia están en su [Decision Log](../media-server/docs/decision-log.md), no se duplican en este registro global. El ordenamiento del repositorio no implicó conexiones SSH, accesos nuevos ni cambios en servidores.

La fase inicial de inventario no publicó archivos ni creó un remoto. El2026-10-16 el propietario creó y confirmó `jdfesa/homelab` público, y autorizó Conventional Commits en inglés, commits graduales ordenados y un push al final; la [guía de publicación](publication-guide.md) conserva el alcance y cómo comprobar sincronización. No se alteran servidores por esta operación Git.

## Open Proposals

| Proposal | Status | Depends on |
| --- | --- | --- |
| Backup independiente y política de restauración | Por diseñar | Inventario de HDD y datos DSM |
| Resolver ensamblado de disco DSM por el host | Revisión pendiente, no tocar en caliente | Backup, ownership y ventana de mantenimiento |
| Firewall y aislamiento de XP | Revisión pendiente | Acceso de consola, reglas y rollback |
| Enlace Gigabit | Evaluación, sin compra decidida | Placa/ranuras, red física y necesidades medidas |
| Trabajo multimedia activo | Consultar el [módulo](../media-server/README.md) | Su roadmap y criterios de aceptación son la fuente de verdad |
| DNS, VPN, fotos, documentos, domótica y multimedia | Exploración | Uso concreto y aceptación progresiva |

## Decision Record Template

Para nuevas decisiones registrar fecha, problema, alternativas, opción elegida, motivos, consecuencias, verificación y rollback. Una propuesta se vuelve accepted solo después de acordarla; una instalación se vuelve completed solo después de verificarla.
