"""Offline CI contracts; no GitHub API, downloads, credentials or server access."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


class RepositoryCIContracts(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text()

    def test_push_pull_request_and_manual_checks_have_no_path_filters(self):
        self.assertRegex(self.workflow, r"(?m)^on:\n  push:\n  pull_request:\n  workflow_dispatch:")
        self.assertNotRegex(self.workflow, r"(?m)^\s+(paths|paths-ignore|branches-ignore):")
        self.assertIn("cancel-in-progress: true", self.workflow)

    def test_readonly_hosted_job_has_bounded_runtime(self):
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertIn("runs-on: ubuntu-24.04", self.workflow)
        self.assertIn("timeout-minutes: 15", self.workflow)
        for forbidden in ("pull_request_target:", "workflow_run:", "self-hosted",
                          "write-all", "continue-on-error:", "upload-artifact", "--report-path"):
            with self.subTest(setting=forbidden):
                self.assertNotIn(forbidden, self.workflow)
        self.assertNotRegex(self.workflow, r"\$\{\{\s*secrets\s*(?:\.|\[)")

    def test_only_official_actions_are_pinned_to_full_commit_shas(self):
        actions = re.findall(r"uses:\s*([^@\s]+)@([^\s]+)", self.workflow)
        self.assertEqual({action for action, _ in actions}, {"actions/checkout", "actions/setup-python"})
        self.assertEqual(len(actions), 2)
        for action, revision in actions:
            with self.subTest(action=action):
                self.assertRegex(revision, r"\A[0-9a-f]{40}\Z")

    def test_checkout_includes_history_without_persisting_credentials(self):
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_scanner_release_is_verified_before_extraction_and_execution(self):
        self.assertRegex(self.workflow, r'GITLEAKS_VERSION: "\d+\.\d+\.\d+"')
        self.assertRegex(self.workflow, r'GITLEAKS_SHA256: "[0-9a-f]{64}"')
        checksum = self.workflow.index("sha256sum --check --strict")
        extraction = self.workflow.index('tar -xzf "$archive"')
        execution = self.workflow.index('"$tool_dir/gitleaks" git .')
        self.assertLess(checksum, extraction)
        self.assertLess(extraction, execution)
        self.assertIn("set -euo pipefail", self.workflow)
        self.assertIn("${RUNNER_TEMP}/gitleaks.XXXXXX", self.workflow)
        self.assertIn("--proto '=https' --tlsv1.2", self.workflow)

    def test_history_scan_is_redacted_and_does_not_honor_inline_bypasses(self):
        for option in ("--redact=100", "--ignore-gitleaks-allow", "--log-opts=--all", "--timeout=300"):
            with self.subTest(option=option):
                self.assertIn(option, self.workflow)
        self.assertNotIn("--baseline-path", self.workflow)
        self.assertNotIn("--exit-code=0", self.workflow)

    def test_existing_publication_guards_precede_tests(self):
        preflight = self.workflow.index("python3 scripts/check-publication.py --acknowledge-public-lab-password")
        scan = self.workflow.index('"$tool_dir/gitleaks" git .')
        tests = self.workflow.index("sh scripts/run-tests.sh")
        self.assertLess(preflight, scan)
        self.assertLess(scan, tests)


if __name__ == "__main__":
    unittest.main()
