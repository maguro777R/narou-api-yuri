"""集計を読むための HTML を作る。機械可読な作品一覧は公開しない。"""

from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from scripts.analysis import summarize
from scripts.narou import Cohort, GENRE_NAMES, JST, REPOSITORY_URL, SOURCE_URL

ROOT = Path(__file__).resolve().parents[1]
STATUSES = (("all", "すべて"), ("serial", "連載中"), ("completed", "完結済み"), ("short", "短編"))
MAX_AGE = timedelta(days=14)


def number(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f}"


def bars(items, denominator: int, *, tone: str = "green") -> str:
    if not denominator or not items:
        return '<p class="empty">この条件では集計できる項目がありません。</p>'
    rows = []
    for label, count in items:
        percent = count / denominator * 100
        rows.append(f'''<li class="bar-row">
          <div class="bar-label"><span>{escape(str(label))}</span><span><b>{count:,}</b> <small>作品</small><i>{percent:.1f}%</i></span></div>
          <div class="bar-track" aria-hidden="true"><div class="bar-fill {tone}" style="width:{percent:.3f}%"></div></div>
        </li>''')
    return '<ul class="bars">' + "".join(rows) + '</ul>'


def panel(cohort: Cohort, status_key: str, status_label: str, *, demo: bool) -> str:
    novels = cohort.novels if status_key == "all" else tuple(n for n in cohort.novels if n.status == status_label)
    stats = summarize(novels)
    count = stats["count"]
    short_count = dict(stats["statuses"])["短編"]
    short_percent = f"{short_count / count * 100:.0f}" if count else "—"
    qualifier = "" if status_key == "all" else f"のうち「{status_label}」"
    scope = f"{cohort.label}の週間ポイント上位 {cohort.limit} 作品{qualifier}。週間ポイントが 1 以上の {count:,} 作品を集計。"
    cards = []
    for index, novel in enumerate(novels[:5], start=1):
        title = escape(novel.title)
        title_html = title if demo else f'<a href="{novel.url}" target="_blank" rel="noopener noreferrer">{title}<span class="external" aria-label="新しいタブで開く"> ↗</span></a>'
        cards.append(f'''<li class="book"><span class="book-number">{index:02}</span><div class="book-body">
          <h4>{title_html}</h4><p class="byline">{escape(novel.writer)}</p>
          <div class="book-meta"><span>{escape(GENRE_NAMES.get(novel.genre, "未分類"))}</span><span>{novel.status}</span><span>{number(novel.length)} 字</span></div>
          </div><div class="book-points"><strong>{number(novel.weekly_point)}</strong><span>週間 pt</span></div></li>''')
    genre_panel = ""
    if cohort.key == "all":
        genre_items = [(GENRE_NAMES.get(code, "未分類"), value) for code, value in stats["genres"]]
        genre_panel = f'''<section class="card genre-card"><div class="card-heading"><div><p class="eyebrow">GENRES</p><h3>どのジャンルが多い？</h3></div><span class="subtle">作品数で比較</span></div>
          {bars(genre_items, count, tone="blue")}<p class="chart-note">総合上位の内訳です。各ジャンルの投稿数や、なろう全体の割合ではありません。</p></section>'''
    first = cohort.key == "all" and status_key == "all"
    return f'''<section class="observation" data-genre="{cohort.key}" data-status="{status_key}" aria-label="{escape(cohort.label)}・{status_label}"{'' if first else ' hidden'}>
      <p class="scope">{escape(scope)}</p>
      <div class="metrics">
        <div class="metric"><span>観測した作品</span><strong>{count:,}<small> 作品</small></strong><p>選んだ条件に当てはまる数</p></div>
        <div class="metric"><span>作品の長さの中央値</span><strong>{number(stats['median_length'])}<small> 字</small></strong><p>短い順に並べた真ん中の長さ</p></div>
        <div class="metric"><span>週間ポイントの中央値</span><strong>{number(stats['median_points'])}<small> pt</small></strong><p>読者の評価・ブックマークが対象</p></div>
        <div class="metric"><span>短編の割合</span><strong>{short_percent}<small> %</small></strong><p>この集計対象に占める割合</p></div>
      </div>
      <div class="charts">
        <section class="card keyword-card"{' id="keywords"' if first else ''}><div class="card-heading"><div><p class="eyebrow">KEYWORDS</p><h3>物語につけられた言葉</h3></div><span class="subtle">上位 12 語</span></div>
          <p class="card-intro">作者が登録したキーワードを、作品数で数えています。</p>{bars(stats['keywords'], count)}
          <p class="chart-note">1 作品に複数の語があるため、割合の合計は 100% を超えます。</p></section>
        <div class="chart-stack"><section class="card"><div class="card-heading"><div><p class="eyebrow">FORMAT</p><h3>どんな形で書かれている？</h3></div></div>{bars(stats['statuses'], count, tone='orange')}</section>
        <section class="card"><div class="card-heading"><div><p class="eyebrow">LENGTH</p><h3>物語の長さ</h3></div></div>{bars(stats['lengths'], count, tone='blue')}
          <p class="chart-note">連載は取得時点の総文字数です。区間の上限は含みません。</p></section></div>
      </div>{genre_panel}
      <section class="card books-card"{' id="stories"' if first else ''}><div class="card-heading"><div><p class="eyebrow">READ THE STORIES</p><h3>数字の先にある作品を読む</h3></div><span class="subtle">上位 {min(count, 5)} 作品</span></div>
        <p class="card-intro">気になった作品は、なろうの作品ページへ。</p><ol class="books">{''.join(cards)}</ol>
        {'' if cards else '<p class="empty">この条件に当てはまる作品はありません。</p>'}</section>
    </section>'''


def shell(content: str, *, collected_at: datetime | None, demo: bool = False) -> str:
    date = collected_at.astimezone(JST).strftime("%Y.%m.%d %H:%M") if collected_at else "更新待ち"
    metadata = f'<meta name="narou-collected-at" content="{collected_at.isoformat()}">' if collected_at else ''
    expires = (collected_at + MAX_AGE).isoformat() if collected_at else ''
    banner = '<div class="demo-banner">画面確認用のデモです。作品・数値はすべて架空です。</div>' if demo else ''
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="小説家になろうの週間ポイント上位作品から、ジャンル・キーワード・作品の長さを眺める非公式の観測ノート。">
<meta name="color-scheme" content="light"><meta name="narou-state" content="{'active' if collected_at else 'unavailable'}">{metadata}
<title>なろう観測室 — 物語のいまを眺める</title>
<link rel="icon" href="./favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="./styles.css"><script src="./app.js" defer></script>
</head><body data-expires="{expires}">{banner}<a class="skip-link" href="#main">本文へ移動</a>
<aside class="sidebar"><a class="brand" href="#main"><span class="brand-mark" aria-hidden="true">栞</span><span>なろう観測室<small>NAROU OBSERVATORY</small></span></a>
  <p class="sidebar-label">観測ノート</p><nav aria-label="ページ内"><a class="nav-link active" href="#overview"><span>01</span>今週の概観</a><a class="nav-link" href="#keywords"><span>02</span>キーワード</a><a class="nav-link" href="#stories"><span>03</span>作品を読む</a><a class="nav-link" href="#method"><span>04</span>データの見方</a></nav>
  <div class="sidebar-bottom"><span class="dot"></span> 毎週火曜に観測<p>書く人のための、<br>小さな定点観測。</p><a href="{SOURCE_URL}" target="_blank" rel="noopener noreferrer">データの出典 ↗</a></div></aside>
<main id="main"><div class="topline"><span>物語を書く、その手がかりに。</span><span class="updated">取得 {date} JST</span></div>
  <header class="hero" id="overview"><p class="eyebrow">A NOTE FOR WRITERS</p><h1>今週、反応を集めた物語。</h1><p>どんな言葉が並び、どんな物語が届いているのか。<br>なろうの週間ポイント上位から、創作のヒントを眺めます。</p><div class="hero-badge"><span class="dot"></span> 非公式・非商用の観測ノート</div></header>
  <div id="expired" class="notice" role="status" hidden><strong>データの更新を待っています。</strong><p>取得から 14 日以上経ったため、古い観測結果の表示を止めています。</p></div>
  <div id="live-content">{content}</div>
  <section class="method" id="method"><p class="eyebrow">HOW TO READ</p><h2>数字は、物語を探すための入口。</h2><div class="method-grid">
  <div><h3>「今週」の意味</h3><p>週間ポイントは、API のランキング集計時点から過去 7 日以内に新しく登録された評価やブックマークに基づく値です。閲覧人数や累計ポイントとは違います。</p></div>
  <div><h3>見ている範囲</h3><p>全ジャンルは上位 500 作品、個別ジャンルはそれぞれ上位 100 作品。週間ポイントが 1 以上の作品だけを数えます。形式の切り替えは、この取得済みの上位作品をさらに絞ります。</p></div>
  <div><h3>この数字でわからないこと</h3><p>全投稿作品の割合、題材の成功確率、前週からの伸びは示していません。同ポイントの境界では抽出対象が入れ替わる場合があります。作品の優劣を決める指標ではありません。</p></div>
  <div><h3>キーワードの数え方</h3><p>作者が登録した語を空白で分け、全角・半角と英字の大小を揃えます。同じ作品内の同じ語は 1 回だけ数え、「R15」「残酷な描写あり」は除外します。応募タグは含みます。</p></div></div>
  <details><summary>取得方法と更新について</summary><p>週 1 回、なろう小説 API に 2 秒以上の間隔で通常 21 回問い合わせます。本文とあらすじは取得しません。各問い合わせの時刻は少しずれ、API の反映にも遅れがあります。初版には過去比較やデータの配布機能はありません。</p><p>取得から 8 日以上で更新遅延の表示、14 日以上で結果の表示を停止します。毎日の確認処理でも、13 日以上経った公開ページをデータを含まない案内へ置き換えます。自動処理自体が停止した場合は、運用者が公開を停止します。</p></details></section>
  <footer><div><strong>なろう観測室</strong><p>出典: <a href="{SOURCE_URL}">なろうデベロッパー / なろう小説 API</a><br>「小説家になろう」は株式会社ヒナプロジェクトの登録商標です。本サイトは公式サービスではありません。</p></div><div><a href="{REPOSITORY_URL}/issues">お問い合わせ・表示の修正 ↗</a><a href="{REPOSITORY_URL}">このサイトの仕組み ↗</a><a href="https://dev.syosetu.com/site/guideline/">API 利用ガイドライン ↗</a></div></footer>
</main></body></html>'''


def render_page(cohorts: tuple[Cohort, ...], collected_at: datetime, *, demo: bool = False) -> str:
    options = ''.join(f'<option value="{cohort.key}">{escape(cohort.label)}</option>' for cohort in cohorts)
    radios = ''.join(f'<label><input type="radio" name="status" value="{key}"{ " checked" if key == "all" else ""}><span>{label}</span></label>' for key, label in STATUSES)
    content = f'''<div class="filters"><label class="genre-filter" for="genre">眺めるジャンル<select id="genre">{options}</select></label><fieldset><legend>作品の形式</legend><div class="segmented">{radios}</div></fieldset></div>
    <p id="update-warning" class="notice" hidden>前回の取得から 8 日以上経っています。次の更新をお待ちください。</p>
    <p id="selection-status" class="sr-only" role="status" aria-live="polite"></p>
    <noscript><p class="notice">JavaScript を有効にすると、ジャンル・形式の切り替えと古いデータの非表示が使えます。以下は取得日時点の全ジャンルの結果です。</p></noscript>'''
    content += ''.join(panel(cohort, key, label, demo=demo) for cohort in cohorts for key, label in STATUSES)
    return shell(content, collected_at=collected_at, demo=demo)


def render_unavailable() -> str:
    return shell('<div class="notice"><h2>データの更新を待っています。</h2><p>新しい観測結果を取得できるまで、作品情報と集計の公開を休止しています。</p></div>', collected_at=None)


def write_site(html: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # 新しいページができるまで既存の index.html を書き換えない。
    temporary = output / "index.html.tmp"
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(output / "index.html")
    for name in ("styles.css", "app.js", "favicon.svg"):
        (output / name).write_bytes((ROOT / "web" / name).read_bytes())
    (output / ".nojekyll").touch()
