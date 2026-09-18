"""python3 -m scripts.build --demo または --live でサイトを作成する。"""

import argparse
from datetime import datetime
from pathlib import Path

from scripts.demo import demo_cohorts
from scripts.narou import JST, collect
from scripts.render import ROOT, render_page, render_unavailable, write_site


def main() -> None:
    parser = argparse.ArgumentParser(description="百合の観測室の公開ページを作ります")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="実 API を取得（ユーザ登録済みの運用者向け）")
    mode.add_argument("--demo", action="store_true", help="架空データで画面を確認")
    mode.add_argument("--unavailable", action="store_true", help="データを含まない休止案内を作成")
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    adult_page = None
    if args.unavailable:
        page = render_unavailable()
    else:
        started = datetime.now(JST)
        cohorts = demo_cohorts() if args.demo else collect()
        page = render_page((cohorts[0],), started, demo=args.demo)
        adult_page = render_page((cohorts[1],), started, demo=args.demo)
    write_site(page, args.output, adult_html=adult_page)
    print(f"ページを作成しました: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
