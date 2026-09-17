"""画面確認用の架空データ。実 API を使わず再現できる。"""

from scripts.narou import Cohort, GENRES, Novel

TITLES = (
    "夜明けの図書室で、竜と待ち合わせ", "小さな港町の魔法修理店",
    "月曜日だけ開く喫茶店", "星をなくした旅人の手紙", "王宮の庭師は春を待つ",
    "雨の街で見つけた約束", "放課後、もうひとつの世界へ", "名前のない星の航海日誌",
)
TAGS = ("冒険 友情 男主人公", "日常 ほのぼの 職業もの", "女主人公 恋愛 ハッピーエンド", "異世界 魔法 冒険", "青春 学園 成長")


def demo_cohorts() -> tuple[Cohort, ...]:
    groups = []
    all_novels = []
    for genre_index, (genre, label) in enumerate(GENRES.items()):
        novels = tuple(Novel(
            ncode=f"N{genre_index * 100 + index:04}ZZ", title=f"【架空】{TITLES[index % len(TITLES)]}",
            writer="画面確認用の架空作者", genre=genre, keyword=TAGS[index % len(TAGS)],
            first_published="2026-09-01 12:00:00", novel_type=2 if index % 3 == 0 else 1,
            end=0 if index % 3 != 1 else 1, episodes=1 if index % 3 == 0 else 40,
            length=(index % 5 + 1) * (1800 if index % 3 == 0 else 17000),
            weekly_point=max(1, 8400 - genre_index * 220 - index * 91),
        ) for index in range(100))
        groups.append(Cohort(str(genre), label, 100, 100, novels))
        all_novels.extend(novels)
    overall = tuple(sorted(all_novels, key=lambda novel: -novel.weekly_point)[:500])
    return (Cohort("all", "全ジャンル", 500, len(all_novels), overall), *groups)
