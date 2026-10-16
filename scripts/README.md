# Shared Homelab Scripts

Only cross-cutting host inventory and repository tooling belong here. VM/LXC provisioning scripts must live in their owning module's `scripts/` directory with a README, not in this shared folder.

| Script | Purpose | Execution boundary |
| --- | --- | --- |
| [collect-inventory.sh](collect-inventory.sh) | Stream the read-only collector to Proxmox and save private evidence | Administration machine with its configured SSH alias; requires RTK and SSH |
| [inventory_host.py](inventory_host.py) | Collect and reduce host/guest inventory without mounting or repairing data | Normally streamed by the collector; not a provisioner |
| [check-publication.py](check-publication.py) | Honor actual nested Git ignores, scan public text/index for common secrets and report explicit lab-password exception | Local Python3 + Git only; disposable metadata, no staging/commit/push, no server/network; not history/OCR scanning |
| [run-tests.sh](run-tests.sh) | Run shared tests and each documented workload module's local suite | Local only; Python 3 and Bash for the current suites, no server access |

From the repository root, `sh scripts/run-tests.sh` runs all suites. `PYTHON` may select a Python interpreter. RTK can optionally wrap the command in the local Codex environment; the test runner itself does not require it.

Read [Operations Runbook](../docs/operations-runbook.md) before inventory collection. Reports belong to the root ignored `.local/inventory/`; workload-private evidence belongs to that workload's ignored `.local/`, never public files.

Before publication: `python3 scripts/check-publication.py --acknowledge-public-lab-password` from the root. The flag acknowledges the single owner-approved real login example, not all secrets. See the [publication guide](../docs/publication-guide.md) for limits and manual review. Without the flag that example blocks the check.
