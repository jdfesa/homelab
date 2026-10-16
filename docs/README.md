# Shared Homelab Documentation

Only host-wide inventory, policy and conventions belong here. Each VM/LXC owns its operational procedures, decisions, roadmap, scripts and tests inside its own module.

- [Repository layout](repository-layout.md) — ownership rules and workload-module contract.
- [Hardware inventory](hardware-inventory.md) and [planned hardware](planned-hardware.md) — physical host and device ownership.
- [Installed services](installed-services.md) — cross-workload resource map and host inventory, not duplicate VM recipes.
- [Service roadmap](service-roadmap.md) — broad exploration; concrete rollout plans belong to modules.
- [Public repository guide](publication-guide.md) — review findings, nested ignores, known public exceptions and first-push checklist.
- [Security and access](security-and-access.md) — shared publication and access safeguards.
- [Operations runbook](operations-runbook.md) — host discovery and cross-cutting maintenance.
- [Stack guide](stack-guide.md) — common Compose conventions, not service manifests.
- [Decision log](decision-log.md) — repository/host decisions; workload decisions stay with their module.

For active media work, start at [media-server](../media-server/README.md).
