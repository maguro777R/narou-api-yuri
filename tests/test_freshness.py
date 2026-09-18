from datetime import datetime, timedelta
import io
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from scripts.freshness import check_site, check_url, needs_retirement
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

    def test_fresh_general_page_does_not_hide_expired_adult_page(self):
        open_url = Mock(side_effect=[io.BytesIO(self.page(timedelta(days=1)).encode()), io.BytesIO(self.page(timedelta(days=13)).encode())])
        self.assertTrue(check_site("https://example.invalid/project/", self.now, open_url=open_url))
        self.assertEqual([call.args[0].full_url for call in open_url.call_args_list], ["https://example.invalid/project/index.html", "https://example.invalid/project/r18.html"])

    def test_two_unavailable_pages_do_not_need_daily_deployment(self):
        page = render_unavailable().encode()
        self.assertFalse(check_site("https://example.invalid/project", self.now, open_url=Mock(side_effect=[io.BytesIO(page), io.BytesIO(page)])))


if __name__ == "__main__":
    unittest.main()
