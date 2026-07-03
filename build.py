#!/usr/bin/env python3
"""build.py - Static site generator for 残影集 (Canying Ji)

Reads markdown files from content/articles/ and content/poems/,
generates a complete static site in public/.
"""

import sys
import io
import os
import json
import re
import shutil
from pathlib import Path

# ── Windows UTF-8 stdout wrapper ──────────────────────────────────────────
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ── Auto-install markdown if missing ──────────────────────────────────────
try:
    import markdown
except ImportError:
    import subprocess
    print("[build] Installing markdown library...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'markdown'])
    import markdown

import yaml

# ── Paths ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / 'content'
ARTICLES_DIR = CONTENT_DIR / 'articles'
POEMS_DIR = CONTENT_DIR / 'poems'
PUBLIC_DIR = ROOT / 'public'
CONFIG_PATH = ROOT / 'config.json'

# ── Load config ───────────────────────────────────────────────────────────
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# ── Markdown converter ────────────────────────────────────────────────────
md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc'])

# ── Helpers ───────────────────────────────────────────────────────────────

def parse_frontmatter(filepath):
    """Parse YAML frontmatter and markdown body from a .md file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match YAML frontmatter between --- delimiters
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {filepath}")

    frontmatter_yaml = match.group(1)
    body = content[match.end():]

    meta = yaml.safe_load(frontmatter_yaml)

    # Derive slug from filename
    stem = filepath.stem
    meta['slug'] = stem

    # Parse date
    if isinstance(meta.get('date'), str):
        meta['date'] = meta['date']
    else:
        meta['date'] = str(meta.get('date', ''))

    return meta, body


def collect_works():
    """Collect all articles and poems, return sorted list."""
    works = []

    for directory, work_type in [(ARTICLES_DIR, 'article'), (POEMS_DIR, 'poem')]:
        if directory.exists():
            for md_file in sorted(directory.glob('*.md')):
                try:
                    meta, body = parse_frontmatter(md_file)
                    meta['type'] = work_type
                    meta['html_body'] = md.convert(body)
                    # Plain text excerpt for search index
                    plain_text = re.sub(r'<[^>]+>', '', meta['html_body'])
                    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                    meta['plain_text'] = plain_text[:500]
                    works.append(meta)
                except Exception as e:
                    print(f"[WARN] Failed to parse {md_file}: {e}")

    # Sort by date, newest first
    works.sort(key=lambda w: w.get('date', ''), reverse=True)
    return works


def build_series_data(works):
    """Build series list with counts."""
    series_counts = {}
    for w in works:
        series = w.get('series', '未分类')
        series_counts[series] = series_counts.get(series, 0) + 1

    series_list = []
    for name, count in series_counts.items():
        info = config.get('series', {}).get(name, {})
        series_list.append({
            'name': name,
            'count': count,
            'icon': info.get('icon', '📄'),
            'color': info.get('color', '#888'),
        })

    return series_list


# ── HTML Templates ────────────────────────────────────────────────────────

def render_page(title, content, site_config=None, extra_head='', og_title=None, og_description=None, og_image=None):
    """Wrap content in a full HTML document."""
    if site_config is None:
        site_config = config
    og_title = og_title or title
    og_description = og_description or site_config['description']
    og_image_meta = f'<meta property="og:image" content="{og_image}">' if og_image else ''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {site_config['site_name']}</title>
    <meta name="description" content="{site_config['description']}">
    <meta name="author" content="{site_config['author']}">
    <meta property="og:title" content="{og_title} - {site_config['site_name']}">
    <meta property="og:description" content="{og_description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://beinanji.netlify.app">
    <meta property="og:site_name" content="{site_config['site_name']}">
    <meta name="twitter:card" content="summary_large_image">
    {og_image_meta}
    <link rel="stylesheet" href="/style.css">
    <link rel="stylesheet" href="/cover.css">
    {extra_head}
</head>
<body>
    <header class="site-header">
        <div class="header-inner">
            <a href="/" class="site-logo">
                <a href="/about.html" class="avatar-link" title="关于作者"><span class="avatar">{site_config['avatar_text']}</span></a>
                <span class="site-title">{site_config['site_name']}</span>
            </a>
            <nav class="site-nav">
                <a href="/">首页</a>
                <a href="/article/">文章</a>
                <a href="/poem/">诗歌</a>
                <a href="/tags.html">标签</a>
                <a href="#" class="theme-toggle" title="切换暗色/亮色模式" onclick="event.preventDefault();
var current=document.documentElement.getAttribute('data-theme');
var next=current==='light'?null:'light';
document.documentElement.setAttribute('data-theme',next);
this.innerHTML=next==='light'?'☀️':'🌙';
localStorage.setItem('theme',next||'dark');
">🌙</a>
                <div class="search-box">
                    <input type="text" id="search-input" placeholder="搜索..." autocomplete="off">
                    <div id="search-results" class="search-results"></div>
                </div>
            </nav>
        </div>
    </header>
    <main class="site-main">
{content}
    </main>
    <footer class="site-footer">
        <p>&copy; 2026 {site_config['author']} · {site_config['site_name']} · 保留所有权利</p>
        <p class="footer-desc">{site_config['description']}</p>
    </footer>
    <script src="/search.js"></script>
</body>
</html>'''


def gradient_css_class(cover_id):
    """Map cover identifier to a CSS class."""
    if not cover_id:
        return 'cover-gradient-default'
    # Remove 'gradient-' prefix if present, keep the rest
    name = cover_id.replace('gradient-', '')
    return f'cover-{name}'


def render_cover(cover_id, title):
    """Render a cover div with gradient background."""
    css_class = gradient_css_class(cover_id)
    return f'''<div class="cover {css_class}">
    <div class="cover-overlay">
        <h1 class="cover-title">{title}</h1>
    </div>
</div>'''


def render_homepage(works, series_list):
    """Render the homepage with all works."""
    # Build series filter buttons
    series_buttons_html = '<div class="series-filters">\n'
    series_buttons_html += '<button class="series-btn active" data-series="all">全部</button>\n'
    for s in series_list:
        series_buttons_html += f'<button class="series-btn" data-series="{s["name"]}">{s["icon"]} {s["name"]}<span class="count">{s["count"]}</span></button>\n'
    series_buttons_html += '</div>'

    # Build work cards
    cards_html = ''
    for w in works:
        wtype = w['type']
        wtype_label = '文章' if wtype == 'article' else '诗歌'
        series_info = config.get('series', {}).get(w.get('series', ''), {})
        series_icon = series_info.get('icon', '📄')
        series_color = series_info.get('color', '#888')
        date_str = w.get('date', '')
        excerpt = w.get('excerpt', '')
        cover_class = gradient_css_class(w.get('cover', ''))
        tags_html = ''.join(f'<span class="tag">{t}</span>' for t in w.get('tags', []))

        cards_html += f'''
<div class="work-card" data-series="{w.get("series", "")}" data-type="{wtype}">
    <a href="/{wtype}/{w["slug"]}.html" class="card-cover {cover_class}">
        <div class="card-cover-inner">
            <span class="card-type-badge">{wtype_label}</span>
            <h2 class="card-title">{w["title"]}</h2>
        </div>
    </a>
    <div class="card-body">
        <div class="card-meta">
            <span class="card-series" style="color:{series_color}">{series_icon} {w.get("series", "")}</span>
            <span class="card-date">{date_str}</span>
        </div>
        <p class="card-excerpt">{excerpt}</p>
        <div class="card-tags">{tags_html}</div>
    </div>
</div>'''

    homepage_content = f'''
<section class="hero">
    <h1 class="hero-title">{config["site_name"]}</h1>
    <p class="hero-subtitle">{config["subtitle"]}</p>
    <p class="hero-desc">{config["description"]}</p>
</section>

<section class="works-section">
    <h2 class="section-title">作品</h2>
    {series_buttons_html}
    <div class="works-grid">
        {cards_html}
    </div>
</section>
'''
    return render_page('首页', homepage_content)


def extract_toc(html_body):
    """Extract h2 and h3 headings from HTML to build a table of contents."""
    headings = re.findall(
        r'<h([23])(?:\s[^>]*?id="([^"]+)")?[^>]*?>(.+?)</h[23]>',
        html_body
    )
    if not headings:
        return '', set()
    items = []
    used_ids = set()
    # First pass: collect all heading texts for id generation
    for level, existing_id, text in headings:
        clean = re.sub(r'<[^>]+>', '', text).strip()
        if not existing_id:
            slug = re.sub(r'[^\w\u4e00-\u9fff]+', '-', clean).strip('-').lower()
            if not slug:
                slug = 'section'
            # Ensure unique
            base = slug
            n = 1
            while slug in used_ids:
                slug = f'{base}-{n}'
                n += 1
        else:
            slug = existing_id
        used_ids.add(slug)
        items.append((level, slug, clean))
    toc_html = ''
    for level, slug, text in items:
        cls = 'toc-h3' if level == '3' else ''
        toc_html += f'<li class="toc-item {cls}"><a href="#{slug}">{text}</a></li>'
    return toc_html, used_ids

def add_heading_ids(html_body, used_ids):
    """Add id attributes to h2/h3 tags that lack them."""
    def replace_id(m):
        level = m.group(1)
        existing_id = m.group(2)
        attrs = m.group(3)
        text = m.group(4)
        rest = m.group(5)
        if existing_id:
            return m.group(0)
        clean = re.sub(r'<[^>]+>', '', text).strip()
        slug = re.sub(r'[^\w\u4e00-\u9fff]+', '-', clean).strip('-').lower()
        if not slug:
            slug = 'section'
        base = slug
        n = 1
        while slug in used_ids:
            slug = f'{base}-{n}'
            n += 1
        used_ids.add(slug)
        return f'<h{level} id="{slug}"{attrs}>{text}{rest}'
    return re.sub(r'<h([23])(\s[^>]*?id="([^"]+)")?([^>]*?)>(.+?)</h[23]>', replace_id, html_body, flags=re.DOTALL)

def render_detail(work):
    """Render an article or poem detail page."""
    wtype = work['type']
    series_info = config.get('series', {}).get(work.get('series', ''), {})
    series_icon = series_info.get('icon', '📄')
    series_color = series_info.get('color', '#888')
    date_str = work.get('date', '')
    tags_html = ''.join(f'<span class="tag">{t}</span>' for t in work.get('tags', []))
    cover_id = work.get('cover', '')

    cover_html = render_cover(cover_id, work['title'])

    # Build TOC
    toc_html, used_ids = extract_toc(work['html_body'])
    html_with_ids = add_heading_ids(work['html_body'], used_ids)

    # TOC sidebar (hidden if no headings)
    toc_sidebar_html = ''
    if toc_html:
        toc_sidebar_html = f'''<aside class="toc">
        <div class="toc-title">目录</div>
        <ul class="toc-list">
            {toc_html}
        </ul>
    </aside>'''

    # OG image for detail pages (simple gradient-based OG image URL)
    og_image_url = f"https://beinanji.netlify.app/og/{work['type']}/{work['slug']}.png"

    content_html = f'''
<article class="detail-page">
    {cover_html}
    <div class="detail-layout">
        <div class="detail-content">
            <div class="detail-meta">
                <a href="/?series={work.get("series", "")}" class="detail-series" style="color:{series_color}">{series_icon} {work.get("series", "")}</a>
                <span class="detail-date">{date_str}</span>
            </div>
            <div class="detail-body">
                {html_with_ids}
            </div>
            <div class="detail-tags">
                {tags_html}
            </div>
            <div class="detail-back">
                <a href="/" class="back-link">&larr; 返回首页</a>
            </div>
        </div>
        {toc_sidebar_html}
    </div>
</article>
'''
    return render_page(work['title'], content_html,
                       og_title=work.get('seo_title', work['title']),
                       og_description=work.get('excerpt', config['description']),
                       og_image=og_image_url)


def build_search_index(works):
    """Generate search-index.json for client-side search."""
    index = []
    for w in works:
        index.append({
            'title': w.get('title', ''),
            'slug': w.get('slug', ''),
            'type': w.get('type', ''),
            'series': w.get('series', ''),
            'tags': w.get('tags', []),
            'date': w.get('date', ''),
            'excerpt': w.get('excerpt', ''),
            'text': w.get('plain_text', ''),
        })
    return index


def render_tags_page(works):
    """Render the tags cloud page."""
    # Group all tags
    tag_counts = {}
    tag_works = {}
    for w in works:
        for tag in w.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if tag not in tag_works:
                tag_works[tag] = []
            tag_works[tag].append(w)

    # Sort by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = sorted_tags[0][1] if sorted_tags else 1

    # Build tag cloud HTML
    tags_html = ''
    for tag, count in sorted_tags:
        # Font size: 0.85em to 2em scaled by frequency
        ratio = count / max_count
        size = 0.85 + ratio * 1.15
        tags_html += f'<a href="#tag-{tag}" class="tag-cloud-item" style="font-size:{size:.2f}em" data-tag="{tag}">{tag}<span class="tag-count">{count}</span></a>\n'

    # Build tagged works panels
    sections_html = ''
    for tag, count in sorted_tags:
        tw = tag_works[tag]
        cards = ''
        for w in tw:
            wtype = w['type']
            wtype_label = '文章' if wtype == 'article' else '诗歌'
            series_info = config.get('series', {}).get(w.get('series', ''), {})
            series_icon = series_info.get('icon', '📄')
            series_color = series_info.get('color', '#888')
            date_str = w.get('date', '')
            excerpt = w.get('excerpt', '')
            cover_class = gradient_css_class(w.get('cover', ''))
            tags_inner = ''.join(f'<span class="tag">{t}</span>' for t in w.get('tags', []))
            cards += f'''
<div class="work-card" data-series="{w.get("series", "")}" data-type="{wtype}">
    <a href="/{wtype}/{w["slug"]}.html" class="card-cover {cover_class}">
        <div class="card-cover-inner">
            <span class="card-type-badge">{wtype_label}</span>
            <h2 class="card-title">{w["title"]}</h2>
        </div>
    </a>
    <div class="card-body">
        <div class="card-meta">
            <span class="card-series" style="color:{series_color}">{series_icon} {w.get("series", "")}</span>
            <span class="card-date">{date_str}</span>
        </div>
        <p class="card-excerpt">{excerpt}</p>
        <div class="card-tags">{tags_inner}</div>
    </div>
</div>'''

        sections_html += f'''
<section class="tag-section" id="tag-{tag}">
    <h2 class="tag-section-title">{tag}<span class="tag-section-count">{count} 篇</span></h2>
    <div class="works-grid">
        {cards}
    </div>
</section>'''

    content = f'''
<section class="listing-hero">
    <h1>标签</h1>
    <p>按标签浏览所有作品</p>
</section>

<section class="works-section">
    <div class="tag-cloud">
        {tags_html}
    </div>
</section>

{sections_html}
'''
    return render_page('标签', content)

# ── Main build ─────────────────────────────────────────────────────────────

def build():
    print("[build] Collecting works...")
    works = collect_works()
    print(f"[build] Found {len(works)} works ({sum(1 for w in works if w['type']=='article')} articles, {sum(1 for w in works if w['type']=='poem')} poems)")

    # Build series data
    series_list = build_series_data(works)

    # Clean public directory
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)

    # Create output directories
    (PUBLIC_DIR / 'article').mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / 'poem').mkdir(parents=True, exist_ok=True)

    # Generate homepage
    print("[build] Generating homepage...")
    homepage_html = render_homepage(works, series_list)
    with open(PUBLIC_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(homepage_html)

    # Generate detail pages
    print("[build] Generating detail pages...")
    for w in works:
        detail_html = render_detail(w)
        out_path = PUBLIC_DIR / w['type'] / f'{w["slug"]}.html'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(detail_html)

    # Generate search index
    print("[build] Generating search index...")
    search_index = build_search_index(works)
    with open(PUBLIC_DIR / 'search-index.json', 'w', encoding='utf-8') as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)

    # Generate series.json
    print("[build] Generating series.json...")
    with open(PUBLIC_DIR / 'series.json', 'w', encoding='utf-8') as f:
        json.dump(series_list, f, ensure_ascii=False, indent=2)

    # Generate listing pages for articles and poems
    for wtype, wtype_label in [('article', '文章'), ('poem', '诗歌')]:
        filtered = [w for w in works if w['type'] == wtype]
        cards_html = ''
        for w in filtered:
            series_info = config.get('series', {}).get(w.get('series', ''), {})
            series_icon = series_info.get('icon', '📄')
            series_color = series_info.get('color', '#888')
            date_str = w.get('date', '')
            excerpt = w.get('excerpt', '')
            cover_class = gradient_css_class(w.get('cover', ''))
            tags_html = ''.join(f'<span class="tag">{t}</span>' for t in w.get('tags', []))

            cards_html += f'''
<div class="work-card" data-series="{w.get("series", "")}" data-type="{wtype}">
    <a href="/{wtype}/{w["slug"]}.html" class="card-cover {cover_class}">
        <div class="card-cover-inner">
            <h2 class="card-title">{w["title"]}</h2>
        </div>
    </a>
    <div class="card-body">
        <div class="card-meta">
            <span class="card-series" style="color:{series_color}">{series_icon} {w.get("series", "")}</span>
            <span class="card-date">{date_str}</span>
        </div>
        <p class="card-excerpt">{excerpt}</p>
        <div class="card-tags">{tags_html}</div>
    </div>
</div>'''

        listing_html = f'''
<section class="listing-hero">
    <h1>{wtype_label}</h1>
    <p>{config["subtitle"]}</p>
</section>
<section class="works-section">
    <div class="works-grid">
        {cards_html}
    </div>
</section>
'''
        page = render_page(wtype_label, listing_html)
        with open(PUBLIC_DIR / wtype / 'index.html', 'w', encoding='utf-8') as f:
            f.write(page)

    # Generate tags page
    print("[build] Generating tags page...")
    tags_html = render_tags_page(works)
    with open(PUBLIC_DIR / 'tags.html', 'w', encoding='utf-8') as f:
        f.write(tags_html)

    # Generate about page
    print("[build] Generating about page...")
    about = config.get('about', {})
    about_html = render_page('关于', f'''
<section class="about-page">
    <div class="about-hero">
        <span class="about-avatar">{about.get("avatar_emoji", "🌙")}</span>
        <h1>{about.get("name", config["author"])}</h1>
        <p class="about-bio">{about.get("bio", "")}</p>
    </div>
    <div class="about-content">
        <div class="about-section">
            <h2>关于我</h2>
            {"".join(f"<p>{p}</p>" for p in about.get("long_bio", "").split("\n\n"))}
        </div>
        <div class="about-section">
            <h2>关注领域</h2>
            <div class="about-tags">
                {"".join(f'<span class="about-tag">{i}</span>' for i in about.get("interests", []))}
            </div>
        </div>
        <div class="about-section">
            <h2>联系我</h2>
            <p class="about-contact">
                📧 <a href="mailto:ybn20060409@163.com">ybn20060409@163.com</a>
            </p>
        </div>
        <a href="/" class="about-back">← 返回首页</a>
    </div>
</section>
''')
    with open(PUBLIC_DIR / 'about.html', 'w', encoding='utf-8') as f:
        f.write(about_html)

    # Copy static assets from static/ directory
    static_dir = ROOT / 'static'
    if static_dir.exists():
        print("[build] Copying static assets...")
        for src_file in static_dir.iterdir():
            if src_file.is_file():
                dst = PUBLIC_DIR / src_file.name
                shutil.copy2(src_file, dst)
                print(f"  - {src_file.name}")

    print("[build] Build complete!")
    print(f"[build] Output: {PUBLIC_DIR}")
    print(f"[build] Files generated:")
    for root, dirs, files in os.walk(PUBLIC_DIR):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), PUBLIC_DIR)
            print(f"  - {rel}")


if __name__ == '__main__':
    build()
