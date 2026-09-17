from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.demo import demo_cohorts
from scripts.narou import Cohort, DataError, JST, parse_novel
from scripts.build import main
from scripts.render import render_page, render_unavailable, write_site
from tests.test_data import row


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.scripts, self.links = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))


class RenderTests(unittest.TestCase):
    def test_untrusted_titles_are_escaped(self):
        malicious = '<script>alert("bad")</script>'
        novel = parse_novel(row(title=malicious, writer=malicious, keyword=malicious))
        page = render_page((Cohort("all", "全ジャンル", 500, 1, (novel,)),), datetime.now(JST))
        self.assertNotIn(malicious, page)
        self.assertIn("&lt;script&gt;", page)
        parser = PageParser()
        parser.feed(page)
        self.assertEqual(parser.scripts, [{"src": "./app.js", "defer": None}])
        self.assertIn("https://ncode.syosetu.com/n0001zz/", parser.links)

    def test_all_modes_have_explicit_denominators_and_empty_state(self):
        novel = parse_novel(row())
        page = render_page((Cohort("all", "全ジャンル", 500, 1, (novel,)),), datetime.now(JST))
        self.assertIn('data-status="short"', page)
        self.assertIn('週間ポイントが 1 以上の 0 作品', page)
        self.assertIn('この条件に当てはまる作品はありません', page)

    def test_demo_cannot_link_to_real_work_and_has_no_duplicate_ids(self):
        page = render_page(demo_cohorts(), datetime.now(JST), demo=True)
        parser = PageParser()
        parser.feed(page)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertFalse(any('ncode.syosetu.com' in url for url in parser.links))
        self.assertIn('作品・数値はすべて架空', page)

    def test_unavailable_page_contains_no_work_or_timestamp(self):
        page = render_unavailable()
        self.assertNotIn('narou-collected-at', page)
        self.assertNotIn('class="observation"', page)

    def test_output_is_only_presentation_assets(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            write_site(render_unavailable(), output)
            self.assertEqual({item.name for item in output.iterdir()}, {'index.html', 'styles.css', 'app.js', 'favicon.svg', '.nojekyll'})

    def test_unexpected_data_file_cannot_be_published(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'data.json').write_text('{}')
            with self.assertRaises(ValueError):
                write_site(render_unavailable(), output)
            self.assertFalse((output / 'index.html').exists())

    def test_failed_collection_preserves_previous_page(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'index.html').write_text('previous successful page')
            with patch('sys.argv', ['build', '--live', '--output', directory]), patch('scripts.build.collect', side_effect=DataError('incomplete')):
                with self.assertRaises(DataError):
                    main()
            self.assertEqual((output / 'index.html').read_text(), 'previous successful page')


if __name__ == "__main__":
    unittest.main()
