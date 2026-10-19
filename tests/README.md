# Shared Repository Tests

Only cross-cutting inventory/privacy and repository-structure tests live here. VM/LXC-specific tests belong to `<module>/tests/`, with their own README.

From the repository root:

```sh
python3 -m unittest discover -s tests -v
sh scripts/run-tests.sh
```

The first command runs shared tests only; the second also discovers documented module suites. These local checks do not contact servers, mount disks or deploy services. Current suites require Python 3 standard library and Bash, not a running hypervisor or Docker daemon.

`test_publication.py` adds10 local checks using real Git ignore rules and disposable fixtures: nested private paths, visible templates/locks, withheld secret values, scoped lab exception, no project initialization/global-ignore dependence, staged-only secrets, already-tracked private files, binary/symlink review and the two-workload map. Git is required for this suite; it never accesses remotes or modifies this project index.

`test_ci.py` checks the shared workflow's events, read-only hosted execution, pinned actions, complete history, scanner checksum, redacted output flags and reuse of existing guards. It requires no YAML package, network access or credentials. See the [canonical CI scope and limits](../docs/publication-guide.md#repository-ci); use actionlint separately for workflow syntax validation.
