"""必要な情報だけを取得する。作品本文・あらすじは取得しない。"""

from __future__ import annotations

import gzip
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))
API_URL = "https://api.syosetu.com/novelapi/api/"
SOURCE_URL = "https://dev.syosetu.com/man/api/"
REPOSITORY_URL = "https://github.com/maguro777R/narou-api-yuri"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
# nt を指定すると、API は novel_type ではなく noveltype を返す。
OUTPUT_FIELDS = "t-n-w-k-gf-nt-e-ga-l-wp-igl"
SOURCES = {
    "general": ("一般向けの百合候補", API_URL, SOURCE_URL),
    "nocturne": ("男性向け R18 の百合候補", "https://api.syosetu.com/novel18api/api/", "https://dev.syosetu.com/xman/api/"),
}
SAMPLE_LIMIT = 500
GENRES = {
    101: "異世界〔恋愛〕", 102: "現実世界〔恋愛〕",
    201: "ハイファンタジー", 202: "ローファンタジー",
    301: "純文学", 302: "ヒューマンドラマ", 303: "歴史",
    304: "推理", 305: "ホラー", 306: "アクション", 307: "コメディー",
    401: "VRゲーム", 402: "宇宙", 403: "空想科学", 404: "パニック",
    9901: "童話", 9902: "詩", 9903: "エッセイ", 9904: "リプレイ",
    9999: "その他",
}
GENRE_NAMES = {**GENRES, 0: "未選択", 9801: "ノンジャンル"}


class DataError(ValueError):
    """不完全なデータを公開しないための検証エラー。"""


@dataclass(frozen=True)
class Novel:
    ncode: str
    title: str
    writer: str
    genre: int | None
    keyword: str
    first_published: str
    novel_type: int
    end: int
    episodes: int
    length: int
    weekly_point: int
    is_gl: bool = False
    source: str = "general"

    @property
    def status(self) -> str:
        if self.novel_type == 2:
            return "短編"
        return "完結済み" if self.end == 0 else "連載中"

    @property
    def url(self) -> str:
        host = "novel18.syosetu.com" if self.source == "nocturne" else "ncode.syosetu.com"
        return f"https://{host}/{self.ncode.lower()}/"


@dataclass(frozen=True)
class Cohort:
    key: str
    label: str
    limit: int
    available: int | None
    novels: tuple[Novel, ...]
    source: str = "general"
    # 検索条件が重なるため、全該当件数を足して母集団の総数にはしない。
    matches: tuple[tuple[str, int], ...] = ()


def integer(row: dict, field: str, minimum: int = 0) -> int:
    value = row.get(field)
    if type(value) is not int or value < minimum:
        raise DataError(f"{field} が正しい整数ではありません")
    return value


def string(row: dict, field: str, *, allow_empty: bool = False) -> str:
    value = row.get(field)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise DataError(f"{field} が正しい文字列ではありません")
    return value


def parse_novel(row: dict, *, source: str = "general") -> Novel:
    if source not in SOURCES:
        raise ValueError("未知の掲載サイトです")
    if not isinstance(row, dict):
        raise DataError("作品情報がオブジェクトではありません")
    ncode = string(row, "ncode").upper()
    if not re.fullmatch(r"N[0-9]{4}[A-Z]+", ncode):
        raise DataError("Nコードの形式が違います")
    # of 指定なしの応答も、テスト・将来の仕様変更時に読み込めるようにする。
    type_key = "noveltype" if "noveltype" in row else "novel_type"
    novel_type, end = integer(row, type_key), integer(row, "end")
    if novel_type not in (1, 2) or end not in (0, 1):
        raise DataError("短編・連載・完結の区分が不正です")
    is_gl = integer(row, "isgl")
    if is_gl not in (0, 1):
        raise DataError("ガールズラブの区分が不正です")
    if source == "nocturne" and integer(row, "nocgenre") != 1:
        raise DataError("ノクターン以外の掲載サイトが含まれています")
    first = string(row, "general_firstup")
    try:
        datetime.strptime(first, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise DataError("初回掲載日の形式が違います") from exc
    return Novel(
        ncode=ncode, title=string(row, "title"), writer=string(row, "writer"),
        genre=integer(row, "genre") if source == "general" else None,
        keyword=string(row, "keyword", allow_empty=True),
        first_published=first, novel_type=novel_type, end=end,
        episodes=integer(row, "general_all_no", 1), length=integer(row, "length"),
        weekly_point=integer(row, "weekly_point"),
        is_gl=bool(is_gl), source=source,
    )


def parse_response(payload: object, *, limit: int, source: str = "general", match: str = "gl") -> tuple[int, tuple[Novel, ...]]:
    if match not in ("gl", "yuri"):
        raise ValueError("未知の百合検索条件です")
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise DataError("API 応答の先頭に件数情報がありません")
    available = integer(payload[0], "allcount")
    novels = tuple(parse_novel(row, source=source) for row in payload[1:])
    if len(novels) > limit or (available > 0 and not novels) or (available == 0 and novels):
        raise DataError("API 応答の作品件数が不正です")
    if available >= limit and len(novels) < limit:
        raise DataError("API 応答が途中で切れている可能性があります")
    if len({novel.ncode for novel in novels}) != len(novels):
        raise DataError("同じ作品が重複しています")
    if match == "gl" and any(not novel.is_gl for novel in novels):
        raise DataError("ガールズラブ設定のない作品が混入しています")
    if match == "yuri" and any("百合" not in novel.keyword for novel in novels):
        raise DataError("百合キーワードのない作品が混入しています")
    points = [novel.weekly_point for novel in novels]
    if points != sorted(points, reverse=True):
        raise DataError("週間ポイント順になっていません")
    # 0 ポイントの同順位作品から傾向を作ると、抽出順の影響が大きすぎる。
    return available, tuple(novel for novel in novels if novel.weekly_point > 0)


def decode_response(body: bytes) -> object:
    if body.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as archive:
            body = archive.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise DataError("API 応答が想定より大きいため停止しました")
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise DataError("API 応答が JSON ではありません") from exc


class Client:
    def __init__(self, *, open_url: Callable = urlopen, sleep: Callable = time.sleep):
        self.open_url, self.sleep = open_url, sleep
        self.requests = 0

    def fetch(self, *, limit: int, source: str = "general", match: str = "gl") -> tuple[int, tuple[Novel, ...]]:
        if not 1 <= limit <= 500:
            raise ValueError("取得件数は 1〜500 にしてください")
        if source not in SOURCES or match not in ("gl", "yuri"):
            raise ValueError("未知の掲載サイトまたは百合検索条件です")
        fields = OUTPUT_FIELDS + ("-ng" if source == "nocturne" else "-g")
        params = {"out": "json", "gzip": 5, "of": fields, "order": "weeklypoint", "lim": limit}
        if source == "nocturne":
            params["nocgenre"] = 1
        if match == "gl":
            params["isgl"] = 1
        else:
            params.update({"word": "百合", "keyword": 1})
        request = Request(
            f"{SOURCES[source][1]}?{urlencode(params)}",
            headers={"User-Agent": f"NarouYuriObservatory/1.0 (+{REPOSITORY_URL})"},
        )
        for attempt in range(3):
            if self.requests:
                self.sleep(2)
            self.requests += 1
            try:
                with self.open_url(request, timeout=30) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                return parse_response(decode_response(body), limit=limit, source=source, match=match)
            except HTTPError as exc:
                exc.close()
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                delay = min(120, max(5, int(retry_after))) if retry_after.isdigit() else 5 * (2 ** attempt)
                self.sleep(delay)
            except (URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise
                self.sleep(5 * (2 ** attempt))
        raise RuntimeError("取得に失敗しました")


def merge_candidates(groups: tuple[tuple[Novel, ...], ...], *, limit: int = SAMPLE_LIMIT) -> tuple[Novel, ...]:
    """同じ作品を一度だけ数える。取得時刻の差は後の応答を採用する。"""
    by_code = {(novel.source, novel.ncode): novel for group in groups for novel in group}
    return tuple(sorted(by_code.values(), key=lambda novel: (-novel.weekly_point, novel.ncode))[:limit])


def collect(client: Client | None = None, *, sources: tuple[str, ...] = tuple(SOURCES)) -> tuple[Cohort, ...]:
    client = client or Client()
    cohorts = []
    for source in sources:
        groups, matches = [], []
        for match in ("gl", "yuri"):
            available, novels = client.fetch(limit=SAMPLE_LIMIT, source=source, match=match)
            groups.append(novels)
            matches.append((match, available))
        novels = merge_candidates(tuple(groups))
        label = SOURCES[source][0]
        cohorts.append(Cohort("all", label, SAMPLE_LIMIT, None, novels, source, tuple(matches)))
        # ログに取得した作品名やキーワードを出さない。
        print(f"取得: {label} / 週間ポイント 1 以上 {len(novels)} 作品", flush=True)
    return tuple(cohorts)
