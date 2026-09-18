"""集計を読むための HTML を作る。機械可読な作品一覧は公開しない。"""

from datetime import datetime, timedelta
from dataclasses import replace
from html import escape
from pathlib import Path

from scripts.analysis import summarize
from scripts.narou import Cohort, DataError, GENRE_NAMES, JST, REPOSITORY_URL, SOURCES

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
    scope = f"{SOURCES[cohort.source][0]}の上位最大 {cohort.limit} 作品から「{cohort.label}」{qualifier}。週間ポイントが 1 以上の {count:,} 作品を集計。"
    small_sample = '<p class="sample-note">対象が 20 作品未満のため、数作品の違いで割合が大きく変わります。</p>' if 0 < count < 20 else ''
    cards = []
    for index, novel in enumerate(novels[:5], start=1):
        title = escape(novel.title)
        title_html = title if demo else f'<a href="{novel.url}" target="_blank" rel="noopener noreferrer">{title}<span class="external" aria-label="新しいタブで開く"> ↗</span></a>'
        cards.append(f'''<li class="book"><span class="book-number">{index:02}</span><div class="book-body">
          <h4>{title_html}</h4><p class="byline">{escape(novel.writer)}</p>
          <div class="book-meta"><span>{escape(GENRE_NAMES.get(novel.genre, "ノクターン"))}</span><span>{novel.status}</span><span>{number(novel.length)} 字</span><span>{'GL 設定あり' if novel.is_gl else '百合キーワードから取得'}</span></div>
          </div><div class="book-points"><strong>{number(novel.weekly_point)}</strong><span>週間 pt</span></div></li>''')
    genre_panel = ""
    if cohort.key == "all" and cohort.source == "general":
        genre_items = [(GENRE_NAMES.get(code, "未分類"), value) for code, value in stats["genres"]]
        genre_panel = f'''<section class="card genre-card"><div class="card-heading"><div><p class="eyebrow">GENRES</p><h3>どのジャンルが多い？</h3></div><span class="subtle">作品数で比較</span></div>
          {bars(genre_items, count, tone="blue")}<p class="chart-note">取得した百合候補の内訳です。各ジャンルの全投稿数や、なろう全体の割合ではありません。</p></section>'''
    first = cohort.key == "all" and status_key == "all"
    return f'''<section class="observation" data-genre="{cohort.key}" data-status="{status_key}" aria-label="{escape(cohort.label)}・{status_label}"{'' if first else ' hidden'}>
      <p class="scope">{escape(scope)}</p>{small_sample}
      <div class="metrics">
        <div class="metric"><span>観測した作品</span><strong>{count:,}<small> 作品</small></strong><p>選んだ条件に当てはまる数</p></div>
        <div class="metric"><span>作品の長さの中央値</span><strong>{number(stats['median_length'])}<small> 字</small></strong><p>短い順に並べた真ん中の長さ</p></div>
        <div class="metric"><span>週間ポイントの中央値</span><strong>{number(stats['median_points'])}<small> pt</small></strong><p>読者の評価・ブックマークが対象</p></div>
        <div class="metric"><span>短編の割合</span><strong>{short_percent}<small> %</small></strong><p>この集計対象に占める割合</p></div>
      </div>
      <div class="charts">
        <section class="card keyword-card"{' id="keywords"' if first else ''}><div class="card-heading"><div><p class="eyebrow">KEYWORDS</p><h3>物語につけられた言葉</h3></div><span class="subtle">上位 12 語</span></div>
          <p class="card-intro">作者が登録したキーワードを、作品数で数えています。</p>{bars(stats['keywords'], count)}
          <p class="chart-note">共通する「百合」「ガールズラブ」「GL」と注意タグを除いています。1 作品に複数の語があるため、割合の合計は 100% を超えます。</p></section>
        <div class="chart-stack"><section class="card"><div class="card-heading"><div><p class="eyebrow">FORMAT</p><h3>どんな形で書かれている？</h3></div></div>{bars(stats['statuses'], count, tone='orange')}</section>
        <section class="card"><div class="card-heading"><div><p class="eyebrow">LENGTH</p><h3>物語の長さ</h3></div></div>{bars(stats['lengths'], count, tone='blue')}
          <p class="chart-note">連載は取得時点の総文字数です。区間の上限は含みません。</p></section></div>
      </div>{genre_panel}
      <section class="card books-card"{' id="stories"' if first else ''}><div class="card-heading"><div><p class="eyebrow">READ THE STORIES</p><h3>数字の先にある作品を読む</h3></div><span class="subtle">上位 {min(count, 5)} 作品</span></div>
        <p class="card-intro">気になった作品は、なろうの作品ページへ。</p><ol class="books">{''.join(cards)}</ol>
        {'' if cards else '<p class="empty">この条件に当てはまる作品はありません。</p>'}</section>
    </section>'''


def shell(content: str, *, collected_at: datetime | None, demo: bool = False, source: str = "general") -> str:
    adult = source == "nocturne"
    label, _, source_url = SOURCES[source]
    date = collected_at.astimezone(JST).strftime("%Y.%m.%d %H:%M") if collected_at else "更新待ち"
    metadata = f'<meta name="narou-collected-at" content="{collected_at.isoformat()}">' if collected_at else ''
    expires = (collected_at + MAX_AGE).isoformat() if collected_at else ''
    banner = '<div class="demo-banner">画面確認用のデモです。作品・数値はすべて架空です。</div>' if demo else ''
    gate = ''
    live = f'<div id="live-content">{content}</div>'
    if adult and collected_at:
        gate = '''<section id="age-gate" class="notice age-gate" aria-labelledby="age-title">
          <p class="eyebrow">18+</p><h2 id="age-title">この先は 18 歳以上の方が対象です。</h2>
          <p>ノクターンノベルズの成人向け作品に関する集計と作品情報を表示します。</p>
          <div class="gate-actions"><button id="confirm-age" type="button">18 歳以上です・集計を見る</button><a href="./index.html">一般向けのページに戻る</a></div>
          <noscript><p>年齢確認には JavaScript が必要です。有効にしてからご利用ください。</p></noscript></section>'''
        # 年齢確認前は DOM に作品情報を展開しない。静的サイトの自己申告式確認。
        live = f'<div id="live-content" hidden></div><template id="adult-content">{content}</template>'
    scope_note = (
        'ノクターンノベルズは男性向けの掲載区分です。実際の読者の性別や、女性同士の恋愛が主題かどうかを示すものではありません。'
        if adult else
        '一般向け API には「男性向け」の分類がありません。このページは読者の性別を限定しない百合候補の観測です。'
    )
    genre_note = 'R18 API に一般向けのジャンル項目はないため、ジャンルを推測して付けません。' if adult else 'ジャンル・形式の切り替えは、取得した上位最大 500 作品の中を絞ります。各ジャンルの全作品を取り直すものではありません。'
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="百合に関係する作品の週間ポイント・キーワード・文字数を眺める、書く人のための非公式な観測ノート。">
{'<meta name="robots" content="noindex, noarchive">' if adult else ''}
<meta name="color-scheme" content="light"><meta name="narou-state" content="{'active' if collected_at else 'unavailable'}">{metadata}
<title>百合の観測室 — {label}</title>
<link rel="icon" href="./favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="./styles.css"><script src="./app.js" defer></script>
</head><body data-expires="{expires}">{banner}<a class="skip-link" href="#main">本文へ移動</a>
<aside class="sidebar"><a class="brand" href="./index.html"><span class="brand-mark" aria-hidden="true">栞</span><span>百合の観測室<small>YURI OBSERVATORY</small></span></a>
  <p class="sidebar-label">観測ノート</p><nav aria-label="ページ内"><a class="nav-link active" href="#overview"><span>01</span>今週の概観</a><a class="nav-link" href="#keywords"><span>02</span>キーワード</a><a class="nav-link" href="#stories"><span>03</span>作品を読む</a><a class="nav-link" href="#method"><span>04</span>データの見方</a></nav>
  <div class="sidebar-bottom"><span class="dot"></span> 毎週火曜に観測<p>ふたりの物語を、<br>数字から見渡す。</p><a href="{source_url}" target="_blank" rel="noopener noreferrer">データの出典 ↗</a></div></aside>
<main id="main"><div class="topline"><span>物語を書く、その手がかりに。</span><span class="updated">取得 {date} JST</span></div>
  <header class="hero" id="overview"><p class="eyebrow">A NOTE FOR YURI WRITERS</p><h1>百合の物語、今週の手がかり。</h1><p>どんな題材が並び、どんな作品に反応が集まったのか。<br>週間ポイントから、次に読みたい物語を探します。</p><div class="hero-badge"><span class="dot"></span> 非公式・非商用の観測ノート</div></header>
  <nav class="source-tabs" aria-label="観測する掲載サイト"><a href="./index.html"{' aria-current="page"' if not adult else ''}>一般向け</a><a href="./r18.html"{' aria-current="page"' if adult else ''}>男性向け R18 <small>18 歳以上</small></a></nav>
  <div class="scope-guide"><strong>{label}</strong><p>{scope_note}</p></div>
  <div id="expired" class="notice" role="status" hidden><strong>データの更新を待っています。</strong><p>取得から 14 日以上経ったため、古い観測結果の表示を止めています。</p></div>
  {gate}{live}
  <section class="method" id="method"><p class="eyebrow">HOW TO READ</p><h2>数字を眺めて、気になる作品へ。</h2><div class="method-grid">
  <div><h3>百合候補の拾い方</h3><p>「ガールズラブ」の設定がある作品と、作者のキーワードに「百合」を含む作品を検索し、重複を除いて上位最大 500 作品に絞ります。百合が脇の要素の作品、TS 百合や他の恋愛要素との混在も含みます。本文の内容を確認した分類ではありません。</p></div>
  <div><h3>「今週」と見ている範囲</h3><p>週間ポイントは、ランキング集計時点から過去 7 日以内の評価・ブックマークに基づく API の値です。閲覧人数や前回取得との差ではありません。0 ポイントは除きます。{genre_note}</p></div>
  <div><h3>創作に使うなら</h3><p>多いキーワードで題材を探し、同じ形式で作品の長さを比べ、気になる作品を読んでみてください。多い題材が成功しやすいとは限りません。全投稿作品の割合、読者の性別、前週からの伸びは分かりません。</p></div>
  <div><h3>キーワードの数え方</h3><p>作者の登録語を空白で分け、全角・半角と英字の大小を揃えます。1 作品で同じ語は 1 回だけ数えます。「百合」「ガールズラブ」「GL」「R15」「R18」「残酷な描写あり」は完全一致で除外します。「TS百合」などの複合語や応募タグは含みます。</p></div></div>
  <details><summary>取得方法と数字の限界</summary><p>各掲載サイトで 2 種類の検索を行い、それぞれ週間ポイント上位 500 作品を取得します。一般向けと R18 の通常計 4 回、2 秒以上の間隔で問い合わせます。検索に当てはまらない百合作品は含みません。重複時は後に取得した応答を採用し、同点は N コード順に並べます。取得の時間差や同点の境界で対象が変わることがあります。</p><p>本文とあらすじは取得しません。原データや過去の作品情報を保存・配布せず、図表と上位作品の紹介を公開します。2 種類の検索に重複があるため、API の全該当件数を足して総作品数とはしません。前週比・急上昇は表示しません。</p><p>取得から 8 日で更新遅延を表示し、毎日の確認で 13 日以上のページを休止案内に置き換えます。ブラウザでも 14 日で表示を止めます。自動処理全体が停止した場合は、運用者が公開を止めます。</p></details></section>
  <footer><div><strong>百合の観測室</strong><p>出典: <a href="{source_url}">なろうデベロッパー / {'R18 小説 API' if adult else '小説 API'}</a><br>「小説家になろう」は株式会社ヒナプロジェクトの登録商標です。本サイトは公式サービスではありません。</p></div><div><a href="{REPOSITORY_URL}/issues">お問い合わせ・表示の修正 ↗</a><a href="{REPOSITORY_URL}">このサイトの仕組み ↗</a><a href="https://dev.syosetu.com/site/guideline/">API 利用ガイドライン ↗</a></div></footer>
</main></body></html>'''


def render_page(cohorts: tuple[Cohort, ...], collected_at: datetime, *, demo: bool = False) -> str:
    if len(cohorts) != 1:
        raise DataError("1 ページに複数の掲載サイトを混ぜることはできません")
    cohort = cohorts[0]
    if any(n.source != cohort.source for n in cohort.novels):
        raise DataError("集計対象に別の掲載サイトが混入しています")
    views = [replace(cohort, key="all", label="すべての候補")]
    if cohort.source == "general":
        views.extend(replace(cohort, key=str(code), label=GENRE_NAMES.get(code, "未分類"), novels=tuple(n for n in cohort.novels if n.genre == code))
                     for code in sorted({n.genre for n in cohort.novels}))
    options = ''.join(f'<option value="{view.key}">{escape(view.label)}</option>' for view in views)
    radios = ''.join(f'<label><input type="radio" name="status" value="{key}"{ " checked" if key == "all" else ""}><span>{label}</span></label>' for key, label in STATUSES)
    content = f'''<div class="filters"><label class="genre-filter" for="genre">取得した候補を絞る<select id="genre">{options}</select></label><fieldset><legend>作品の形式</legend><div class="segmented">{radios}</div></fieldset></div>
    <p id="update-warning" class="notice" hidden>前回の取得から 8 日以上経っています。次の更新をお待ちください。</p>
    <p id="selection-status" class="sr-only" role="status" aria-live="polite"></p>
    <noscript><p class="notice">JavaScript を有効にすると、条件の切り替えと古いデータの非表示が使えます。以下は取得日時点の全候補の結果です。</p></noscript>'''
    content += ''.join(panel(view, key, label, demo=demo) for view in views for key, label in STATUSES)
    return shell(content, collected_at=collected_at, demo=demo, source=cohort.source)


def render_unavailable(*, source: str = "general") -> str:
    return shell('<div class="notice"><h2>データの更新を待っています。</h2><p>新しい観測結果を取得できるまで、作品情報と集計の公開を休止しています。</p></div>', collected_at=None, source=source)


def write_site(html: str, output: Path, *, adult_html: str | None = None) -> None:
    allowed = {"index.html", "index.html.tmp", "r18.html", "r18.html.tmp", "styles.css", "app.js", "favicon.svg", ".nojekyll"}
    if output.is_symlink():
        raise ValueError("出力先にシンボリックリンクは指定できません")
    output.mkdir(parents=True, exist_ok=True)
    for item in output.iterdir():
        if item.name not in allowed or item.is_symlink() or not item.is_file():
            raise ValueError("出力先に想定外のファイルがあります。空の専用フォルダを指定してください")
    pages = {"index.html": html, "r18.html": adult_html if adult_html is not None else render_unavailable(source="nocturne")}
    for name in ("styles.css", "app.js", "favicon.svg"):
        (output / name).write_bytes((ROOT / "web" / name).read_bytes())
    (output / ".nojekyll").touch()
    for name, page in pages.items():
        temporary = output / (name + ".tmp")
        temporary.write_text(page, encoding="utf-8")
    # 休止時も必ず両ページを置き換え、古い R18 情報を残さない。
    for name in pages:
        (output / (name + ".tmp")).replace(output / name)
