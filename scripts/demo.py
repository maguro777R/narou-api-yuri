"""画面確認用の架空データ。実 API を使わず再現できる。"""

from scripts.narou import Cohort, Novel, SAMPLE_LIMIT, SOURCES

TITLES = (
    "放課後の図書室で、君の続きを待っている", "魔女と騎士の小さな旅路",
    "隣の席の彼女と、雨上がりの約束", "ふたりで直す、港町の魔法店",
    "女王陛下と庭師の春", "幼なじみと星を探す夜",
    "悪役令嬢はヒロインの手を取る", "名前のない星で、彼女と暮らす",
)
TAGS = (
    "百合 ガールズラブ 学園 青春 女主人公", "百合 冒険 魔法 女主人公",
    "ガールズラブ 日常 ハッピーエンド", "百合 ほのぼの 職業もの",
    "ガールズラブ 身分差 恋愛", "百合 幼なじみ 日常", "百合 悪役令嬢 異世界", "TS百合 SF 冒険",
)


def demo_cohorts() -> tuple[Cohort, ...]:
    groups = []
    for source_index, (source, (label, _, _)) in enumerate(SOURCES.items()):
        novels = tuple(Novel(
            ncode=f"N{source_index * 1000 + index:04}ZZ", title=f"【架空】{TITLES[index % len(TITLES)]}",
            writer="画面確認用の架空作者", genre=(102, 201, 102, 202, 101, 302, 101, 402)[index % 8] if source == "general" else None,
            keyword=TAGS[index % len(TAGS)], first_published="2026-09-01 12:00:00",
            novel_type=2 if index % 3 == 0 else 1, end=0 if index % 3 != 1 else 1,
            episodes=1 if index % 3 == 0 else 40,
            length=(index % 5 + 1) * (1800 if index % 3 == 0 else 17000),
            weekly_point=max(1, 480 - index * 3), is_gl=index % 8 != 7, source=source,
        ) for index in range(120 if source == "general" else 72))
        groups.append(Cohort("all", label, SAMPLE_LIMIT, None, novels, source))
    return tuple(groups)
