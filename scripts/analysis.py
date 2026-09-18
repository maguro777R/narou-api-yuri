"""ランキングの母集団を混ぜずに、単純な件数・割合を計算する。"""

import re
import unicodedata
from collections import Counter
from statistics import median

from scripts.narou import Novel

STATUS_ORDER = ("短編", "連載中", "完結済み")
LENGTH_BINS = (
    (10_000, "1 万字未満"), (50_000, "1〜5 万字"),
    (100_000, "5〜10 万字"), (300_000, "10〜30 万字"),
    (None, "30 万字以上"),
)
# 対象を選ぶための語と注意タグは、題材の比較から外す。部分一致では消さない。
EXCLUDED_KEYWORDS = {"r15", "r18", "残酷な描写あり", "ガールズラブ", "百合", "gl"}


def keywords(text: str) -> set[str]:
    tokens = re.split(r"\s+", unicodedata.normalize("NFKC", text).strip())
    return {token.casefold() for token in tokens if token and token.casefold() not in EXCLUDED_KEYWORDS}


def summarize(novels: tuple[Novel, ...]) -> dict:
    keyword_counts: Counter = Counter()
    genre_counts: Counter = Counter()
    status_counts: Counter = Counter()
    length_counts: Counter = Counter()
    for novel in novels:
        keyword_counts.update(keywords(novel.keyword))
        if novel.genre is not None:
            genre_counts[novel.genre] += 1
        status_counts[novel.status] += 1
        for maximum, label in LENGTH_BINS:
            if maximum is None or novel.length < maximum:
                length_counts[label] += 1
                break
    return {
        "count": len(novels),
        "median_length": median([novel.length for novel in novels]) if novels else None,
        "median_points": median([novel.weekly_point for novel in novels]) if novels else None,
        "keywords": sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:12],
        "genres": sorted(genre_counts.items(), key=lambda item: (-item[1], item[0])),
        "statuses": [(status, status_counts[status]) for status in STATUS_ORDER],
        "lengths": [(label, length_counts[label]) for _, label in LENGTH_BINS],
    }
