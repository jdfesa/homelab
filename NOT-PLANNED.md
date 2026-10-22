# Not Planned

**Status:** Excluded under current conditions · **Updated:** 2026-10-22.

Servicios descartados para la etapa y el hardware actuales, no prohibiciones permanentes. Este archivo es la referencia canónica de exclusiones; [TODO.md](TODO.md) contiene los servicios seleccionados para implementación futura.

No proponer de nuevo estas incorporaciones mientras se mantengan sus motivos de exclusión. Reevaluarlas sólo ante una solicitud explícita o un cambio relevante en las condiciones indicadas; una reevaluación no autoriza el despliegue.

## Monitoring

| Service | Decision and reason | Reconsider when |
| --- | --- | --- |
| Uptime Kuma | No implementar por ahora: un solo nodo Proxmox, sin UPS y sin presupuesto sostenible para infraestructura adicional. Un monitor en el mismo nodo comparte sus fallos; la exclusión responde a utilidad y coste actuales, no a una imposibilidad técnica de monitorizar aplicaciones en un único nodo. | Si cambia la necesidad o existe presupuesto sostenible para protección eléctrica y monitorización independiente del host. |

## Photos

| Service | Decision and reason | Reconsider when |
| --- | --- | --- |
| Immich | No implementar ahora. Una biblioteca de fotos sería útil, pero no se prioriza su consumo de RAM y recursos frente a las cargas existentes del host de 16 GB. | Tras un upgrade de hardware y una nueva evaluación de capacidad, almacenamiento y recuperación. |

## Local AI

| Workload | Decision and reason | Reconsider when |
| --- | --- | --- |
| Stack de IA local, como Ollama con Open WebUI o ComfyUI | No planificar con el i5-4440 de cuarta generación, 16 GB de RAM compartidos con las cargas actuales y únicamente la iGPU integrada. No hay un caso de uso identificado que justifique dedicarle recursos. No se afirma que toda inferencia local sea técnicamente imposible. | Tras un upgrade adecuado, o si aparece un caso concreto y útil para un modelo extremadamente pequeño cuyo consumo y rendimiento se validen sin perjudicar los servicios existentes. No hay un experimento aprobado. |
