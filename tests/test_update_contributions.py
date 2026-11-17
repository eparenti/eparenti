from contextlib import redirect_stdout
from datetime import date
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import update_contributions as updater


class ContributionUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.readme = Path(self.temp.name) / "README.md"
        self.original = f"Profile introduction\n{updater.START}\nOld counts\n{updater.END}\nOther projects\n"
        self.readme.write_text(self.original)
        self.today = date(2026, 11, 17)
        self.environment = patch.dict(os.environ, {name: "test-token" for name in updater.ACCOUNTS.values()})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.output = redirect_stdout(StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.counts = dict(zip(updater.FIELDS, (10, 3, 1, 2)), total=20)
        self.period = ("2025-11-16T00:00:00Z", "2026-11-17T23:59:59Z")
        self.result = (self.counts, self.period)

    def test_updates_all_counts_preserves_other_text_and_is_repeatable(self):
        with patch.object(updater, "fetch_counts", return_value=self.result):
            self.assertTrue(updater.update(self.readme, self.today))
            self.assertFalse(updater.update(self.readme, self.today))
        expected = (
            "40 GitHub contributions in the last year across my two accounts "
            "(including 20 commits, 6 pull requests, 2 reviews, 4 issues), "
            "most of them in private repositories. Counted 2026-11-17."
        )
        self.assertEqual(self.readme.read_text(), self.original.replace("Old counts", expected))

    def test_second_account_failure_preserves_previous_paragraph(self):
        with patch.object(updater, "fetch_counts", side_effect=[self.result, ValueError("API failed")]):
            with self.assertRaisesRegex(ValueError, "API failed"):
                updater.update(self.readme, self.today)
        self.assertEqual(self.readme.read_text(), self.original)

    def test_preview_does_not_write(self):
        with patch.object(updater, "fetch_counts", return_value=self.result):
            self.assertTrue(updater.update(self.readme, self.today, check=True))
        self.assertEqual(self.readme.read_text(), self.original)

    def test_missing_token_stops_before_network(self):
        with patch.dict(os.environ, {"TEMPO_CONTRIBUTIONS_TOKEN": ""}):
            with patch.object(updater, "fetch_counts") as fetch:
                with self.assertRaisesRegex(ValueError, "Missing repository secrets"):
                    updater.update(self.readme, self.today)
                fetch.assert_not_called()
        self.assertEqual(self.readme.read_text(), self.original)

    def test_invalid_markers_preserve_file(self):
        for text in ("No markers", self.original + updater.START, updater.END + updater.START):
            with self.subTest(text=text):
                self.readme.write_text(text)
                with self.assertRaises(ValueError):
                    updater.update(self.readme, self.today)
                self.assertEqual(self.readme.read_text(), text)

    def test_different_calendar_periods_preserve_previous_paragraph(self):
        other_period = (self.period[0], "2026-11-18T23:59:59Z")
        with patch.object(updater, "fetch_counts", side_effect=[self.result, (self.counts, other_period)]):
            with self.assertRaisesRegex(ValueError, "different periods"):
                updater.update(self.readme, self.today)
        self.assertEqual(self.readme.read_text(), self.original)

    def response(self, payload, scopes="read:user"):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get.return_value = scopes
        response.read.return_value = json.dumps(payload).encode()
        return response

    def test_partial_graphql_error_is_rejected(self):
        with patch.object(updater, "urlopen", return_value=self.response({"data": {}, "errors": [{}]})):
            with self.assertRaisesRegex(ValueError, "query errors"):
                updater.fetch_counts("eparenti", "test-token")

    def test_wrong_account_is_rejected(self):
        payload = {"data": {"viewer": {"login": "tempo-64"}}}
        with patch.object(updater, "urlopen", return_value=self.response(payload)):
            with self.assertRaisesRegex(ValueError, "token must belong"):
                updater.fetch_counts("eparenti", "test-token")

    def test_missing_private_contribution_scope_is_rejected(self):
        with patch.object(updater, "urlopen", return_value=self.response({}, scopes="repo")):
            with self.assertRaisesRegex(ValueError, "read:user"):
                updater.fetch_counts("eparenti", "test-token")

    def test_missing_or_invalid_counts_are_rejected(self):
        collection = dict(zip(updater.FIELDS, (10, 3, 1, 2)))
        for total in (None, -1, True, "20", 15):
            with self.subTest(total=total):
                payload = {"data": {"viewer": {"login": "eparenti", "contributionsCollection": {
                    **collection, "contributionCalendar": {"totalContributions": total},
                    "startedAt": self.period[0], "endedAt": self.period[1]
                }}}}
                with patch.object(updater, "urlopen", return_value=self.response(payload)):
                    with self.assertRaises(ValueError):
                        updater.fetch_counts("eparenti", "test-token")


if __name__ == "__main__":
    unittest.main()
