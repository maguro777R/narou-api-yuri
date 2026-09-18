import gzip
import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from scripts.analysis import keywords, summarize
from scripts.narou import Client, DataError, collect, decode_response, merge_candidates, parse_novel, parse_response


def row(**changes):
    result = {
        "ncode": "N0001ZZ", "title": "テスト用の架空作品", "writer": "架空の作者",
        "genre": 201, "keyword": "冒険 冒険　友情", "general_firstup": "2026-01-01 12:00:00",
        "noveltype": 1, "end": 1, "general_all_no": 10, "length": 10000, "weekly_point": 100,
        "isgl": 1,
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

    def test_malformed_duplicate_unsorted_or_non_gl_fails(self):
        cases = [
            [], [{"allcount": 10}], [{"allcount": 2}, row(), row()],
            [{"allcount": 2}, row(), row(ncode="N0002ZZ", weekly_point=101)],
            [{"allcount": 1}, row(isgl=0)],
            [{"allcount": 1}, row(weekly_point="100")],
            [{"allcount": 100}, row()],
            [{"allcount": 0}, row()],
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(DataError):
                parse_response(payload, limit=100)

    def test_empty_genre_is_valid(self):
        self.assertEqual(parse_response([{"allcount": 0}], limit=100), (0, ()))

    def test_plain_and_gzip_json(self):
        body = json.dumps([{"allcount": 0}]).encode()
        self.assertEqual(decode_response(body), decode_response(gzip.compress(body)))
        with self.assertRaises(DataError):
            decode_response(b"<html>maintenance</html>")

    def test_request_uses_weekly_points_and_only_needed_fields(self):
        open_url = Mock(return_value=io.BytesIO(json.dumps([{"allcount": 1}, row()]).encode()))
        Client(open_url=open_url, sleep=Mock()).fetch(limit=100)
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["order"], ["weeklypoint"])
        self.assertEqual(params["isgl"], ["1"])
        self.assertIn("igl", params["of"][0].split("-"))
        self.assertNotIn("s", params["of"][0].split("-"))

    def test_yuri_search_is_only_keywords_and_keeps_unflagged_works(self):
        open_url = Mock(return_value=io.BytesIO(json.dumps([{"allcount": 1}, row(isgl=0, keyword="青春 百合")]).encode()))
        _, novels = Client(open_url=open_url, sleep=Mock()).fetch(limit=500, match="yuri")
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["word"], ["百合"])
        self.assertEqual(params["keyword"], ["1"])
        self.assertNotIn("isgl", params)
        self.assertFalse(novels[0].is_gl)
        with self.assertRaises(DataError):
            parse_response([{"allcount": 1}, row(keyword="友情")], limit=500, match="yuri")

    def test_adult_response_must_be_nocturne_and_uses_adult_link(self):
        item = row(nocgenre=1)
        del item["genre"]
        open_url = Mock(return_value=io.BytesIO(json.dumps([{"allcount": 1}, item]).encode()))
        _, novels = Client(open_url=open_url, sleep=Mock()).fetch(limit=500, source="nocturne")
        url = urlparse(open_url.call_args.args[0].full_url)
        params = parse_qs(url.query)
        self.assertEqual(url.path, "/novel18api/api/")
        self.assertEqual(params["nocgenre"], ["1"])
        self.assertIn("ng", params["of"][0].split("-"))
        self.assertNotIn("g", params["of"][0].split("-"))
        self.assertIsNone(novels[0].genre)
        self.assertEqual(novels[0].url, "https://novel18.syosetu.com/n0001zz/")
        for invalid in (0, 2, 3, 4):
            with self.subTest(invalid=invalid), self.assertRaises(DataError):
                parse_novel(row(nocgenre=invalid), source="nocturne")

    def test_union_deduplicates_then_selects_weekly_top(self):
        first = parse_novel(row(weekly_point=50))
        later = parse_novel(row(weekly_point=60))
        second = parse_novel(row(ncode="N0002ZZ", weekly_point=100))
        third = parse_novel(row(ncode="N0003ZZ", weekly_point=60))
        self.assertEqual(merge_candidates(((first, third), (second, later)), limit=2), (second, later))

    def test_collection_keeps_sources_separate_and_never_adds_matching_counts(self):
        general = parse_novel(row())
        adult = parse_novel(row(nocgenre=1), source="nocturne")
        client = Mock()
        client.fetch.side_effect = [(80, (general,)), (20, (general,)), (8, (adult,)), (2, (adult,))]
        cohorts = collect(client)
        self.assertEqual([len(c.novels) for c in cohorts], [1, 1])
        self.assertEqual([c.source for c in cohorts], ["general", "nocturne"])
        self.assertTrue(all(c.available is None for c in cohorts))
        self.assertEqual(cohorts[0].matches, (("gl", 80), ("yuri", 20)))
        self.assertEqual(client.fetch.call_count, 4)

    def test_no_reactions_is_a_valid_empty_observation(self):
        client = Mock()
        client.fetch.return_value = (0, ())
        self.assertEqual(collect(client, sources=("general",))[0].novels, ())

    def test_rate_limit_retries_but_bad_request_does_not(self):
        error = HTTPError("https://example.invalid", 429, "busy", {"Retry-After": "8"}, io.BytesIO())
        open_url = Mock(side_effect=[error, io.BytesIO(b'[{"allcount":0}]')])
        sleep = Mock()
        self.assertEqual(Client(open_url=open_url, sleep=sleep).fetch(limit=100), (0, ()))
        self.assertIn(unittest.mock.call(8), sleep.call_args_list)
        error = HTTPError("https://example.invalid", 403, "denied", {}, io.BytesIO())
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

    def test_selection_terms_are_excluded_without_removing_compound_themes(self):
        self.assertEqual(keywords("百合 ガールズラブ ＧＬ R18 TS百合 学園百合"), {"ts百合", "学園百合"})


if __name__ == "__main__":
    unittest.main()
