from datetime import datetime, timedelta
import io
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from scripts.freshness import check_url, needs_retirement
from scripts.narou import JST
from scripts.render import render_unavailable


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 6, 23, tzinfo=JST)

    def page(self, age):
        return f'<meta name="narou-collected-at" content="{(self.now - age).isoformat()}">'

    def test_exact_thirteen_day_boundary(self):
        self.assertFalse(needs_retirement(self.page(timedelta(days=13, seconds=-1)), self.now))
        self.assertTrue(needs_retirement(self.page(timedelta(days=13)), self.now))

    def test_unavailable_needs_no_redeployment(self):
        self.assertFalse(needs_retirement(render_unavailable(), self.now))

    def test_missing_naive_and_future_timestamps_fail(self):
        for html in ('<html>error</html>', '<meta name="narou-collected-at" content="2026-09-18T00:00:00">', self.page(timedelta(days=-1))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                needs_retirement(html, self.now)

    def test_unpublished_site_gets_notice_but_network_error_is_reported(self):
        error = HTTPError("https://example.invalid", 404, "missing", {}, io.BytesIO())
        self.assertTrue(check_url("https://example.invalid", self.now, open_url=Mock(side_effect=error)))
        with self.assertRaises(URLError):
            check_url("https://example.invalid", self.now, open_url=Mock(side_effect=URLError("offline")))


if __name__ == "__main__":
    unittest.main()
