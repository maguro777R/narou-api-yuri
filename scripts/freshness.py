"""API には接続せず、公開中のページの日付だけを確認する。"""

import argparse
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.narou import JST, MAX_RESPONSE_BYTES
from scripts.render import ROOT, render_unavailable, write_site

# 日次確認の間隔を考慮し、14 日の上限より 1 日早く置き換える。
RETIRE_AFTER = timedelta(days=13)


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").startswith("narou-"):
            self.values[attrs["name"]] = attrs.get("content", "")


def needs_retirement(html: str, now: datetime) -> bool:
    metadata = Metadata()
    metadata.feed(html)
    if metadata.values.get("narou-state") == "unavailable":
        return False
    timestamp = metadata.values.get("narou-collected-at")
    if not timestamp:
        raise ValueError("公開ページに取得日時がありません。手動で確認してください")
    collected_at = datetime.fromisoformat(timestamp)
    if collected_at.tzinfo is None or collected_at > now + timedelta(minutes=5):
        raise ValueError("公開ページの取得日時が不正です")
    return now - collected_at >= RETIRE_AFTER


def check_url(url: str, now: datetime, *, open_url=urlopen) -> bool:
    request = Request(url, headers={"User-Agent": "NarouObservatory-Freshness/1.0", "Cache-Control": "no-cache"})
    try:
        with open_url(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        exc.close()
        if exc.code == 404:
            return True
        raise
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("公開ページが想定より大きいため停止しました")
    return needs_retirement(body.decode("utf-8"), now)


def main():
    parser = argparse.ArgumentParser(description="公開ページの期限を確認します")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    retire = check_url(args.url, datetime.now(JST))
    if retire:
        write_site(render_unavailable(), args.output)
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f"deploy={'true' if retire else 'false'}\n")
    print("期限を迎えたため休止案内を作成しました" if retire else "公開ページは期限内、または休止中です")


if __name__ == "__main__":
    main()
