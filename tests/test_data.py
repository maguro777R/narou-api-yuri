import gzip
import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from scripts.analysis import keywords, summarize
from scripts.narou import Client, DataError, decode_response, parse_novel, parse_response


def row(**changes):
    result = {
        "ncode": "N0001ZZ", "title": "テスト用の架空作品", "writer": "架空の作者",
        "genre": 201, "keyword": "冒険 冒険　友情", "general_firstup": "2026-01-01 12:00:00",
        "noveltype": 1, "end": 1, "general_all_no": 10, "length": 10000, "weekly_point": 100,
    }
    result.update(changes)
    return result


class ParsingTests(unittest.TestCase):
    def test_actual_of_type_field_and_completion_flag(self):
        self.assertEqual(parse_novel(row(noveltype=2, end=0)).status, "短編")
        self.assertEqual(parse_novel(row(end=0)).status, "完結済み")
        self.assertEqual(parse_novel(row(end=1)).status, "連載中")

    def test_unfiltered_api_type_field(self):
        item = row()
        item["novel_type"] = item.pop("noveltype")
        self.assertEqual(parse_novel(item).novel_type, 1)

    def test_metadata_is_not_a_work_and_zero_points_are_excluded(self):
        count, novels = parse_response([{"allcount": 30}, row(), row(ncode="N0002ZZ", weekly_point=0)], limit=100)
        self.assertEqual(count, 30)
        self.assertEqual(len(novels), 1)

    def test_malformed_duplicate_unsorted_or_wrong_genre_fails(self):
        cases = [
            [], [{"allcount": 10}], [{"allcount": 2}, row(), row()],
            [{"allcount": 2}, row(), row(ncode="N0002ZZ", weekly_point=101)],
            [{"allcount": 1}, row(genre=101)],
            [{"allcount": 1}, row(weekly_point="100")],
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(DataError):
                parse_response(payload, limit=100, genre=201)

    def test_empty_genre_is_valid(self):
        self.assertEqual(parse_response([{"allcount": 0}], limit=100), (0, ()))

    def test_plain_and_gzip_json(self):
        body = json.dumps([{"allcount": 0}]).encode()
        self.assertEqual(decode_response(body), decode_response(gzip.compress(body)))
        with self.assertRaises(DataError):
            decode_response(b"<html>maintenance</html>")

    def test_request_uses_weekly_points_and_only_needed_fields(self):
        open_url = Mock(return_value=io.BytesIO(json.dumps([{"allcount": 1}, row()]).encode()))
        Client(open_url=open_url, sleep=Mock()).fetch(limit=100, genre=201)
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["order"], ["weeklypoint"])
        self.assertEqual(params["genre"], ["201"])
        self.assertNotIn("s", params["of"][0].split("-"))

    def test_rate_limit_retries_but_bad_request_does_not(self):
        error = HTTPError("https://example.invalid", 429, "busy", {"Retry-After": "8"}, None)
        open_url = Mock(side_effect=[error, io.BytesIO(b'[{"allcount":0}]')])
        sleep = Mock()
        self.assertEqual(Client(open_url=open_url, sleep=sleep).fetch(limit=100), (0, ()))
        self.assertIn(unittest.mock.call(8), sleep.call_args_list)
        error = HTTPError("https://example.invalid", 403, "denied", {}, None)
        open_url = Mock(side_effect=error)
        with self.assertRaises(HTTPError):
            Client(open_url=open_url, sleep=Mock()).fetch(limit=100)
        self.assertEqual(open_url.call_count, 1)


class AnalysisTests(unittest.TestCase):
    def test_keywords_count_once_per_work_and_normalize_width(self):
        self.assertEqual(keywords("Ｒ１５ R15 冒険　冒険 SF ｓｆ 残酷な描写あり"), {"冒険", "sf"})
        result = summarize((parse_novel(row()), parse_novel(row(ncode="N0002ZZ", keyword="友情"))))
        self.assertEqual(result["keywords"], [("友情", 2), ("冒険", 1)])

    def test_bin_edges_and_median(self):
        novels = tuple(parse_novel(row(ncode=f"N{i:04}ZZ", length=length)) for i, length in enumerate([9999, 10000, 50000, 100000, 300000]))
        result = summarize(novels)
        self.assertEqual([count for _, count in result["lengths"]], [1, 1, 1, 1, 1])
        self.assertEqual(result["median_length"], 50000)

    def test_no_data_is_not_zero_median(self):
        self.assertIsNone(summarize(())["median_length"])


if __name__ == "__main__":
    unittest.main()
