#!/usr/bin/env python3
"""editor.py - Local web-based CMS for 北南集

Run with: python editor.py
Opens at: http://localhost:5000
"""

import sys
import io
import json
import os
import re
import shutil
import subprocess
import traceback
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Windows UTF-8 stdout ──────────────────────────────────────────────────
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ── Paths ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / 'content'
ARTICLES_DIR = CONTENT_DIR / 'articles'
POEMS_DIR = CONTENT_DIR / 'poems'
CONFIG_PATH = ROOT / 'config.json'
EDITOR_HTML = ROOT / 'editor.html'

# Ensure content directories exist
ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
POEMS_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────

def load_config():
    """Load config.json."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(data):
    """Save config.json."""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(title):
    """Generate a slug from a title. Preserves Chinese/Unicode characters,
    replaces spaces with hyphens, removes problematic characters."""
    slug = re.sub(r'[\s_]+', '-', title.strip())
    # Remove chars that are problematic in filenames (keep Unicode letters and CJK)
    slug = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff-]', '', slug, flags=re.UNICODE)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-').lower()


def parse_frontmatter(filepath):
    """Parse YAML-like frontmatter and markdown body from a .md file.

    Since we only use stdlib (no PyYAML), we parse a simple YAML subset
    that supports the fields we need: title, date, series, tags, cover, excerpt.
    Tags can be a list or comma-separated string.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}, content

    fm_text = match.group(1)
    body = content[match.end():]
    meta = parse_simple_yaml(fm_text)

    # Derive slug from filename
    meta['slug'] = filepath.stem

    # Normalize date
    if 'date' in meta:
        meta['date'] = str(meta['date'])

    # Normalize tags
    if 'tags' in meta and isinstance(meta['tags'], list):
        meta['tags'] = [str(t) for t in meta['tags']]

    return meta, body


def parse_simple_yaml(text):
    """Parse a simple flat YAML subset. Supports:
    - key: value
    - key: "quoted value"
    - key: 'quoted value'
    - key:
        - item1
        - item2
    Multiline values via | not supported.
    """
    result = {}
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith('#'):
            i += 1
            continue

        # Check for list item
        if line.strip().startswith('- '):
            # Find the preceding key
            key = _last_key
            val = line.strip()[2:].strip()
            val = val.strip('"').strip("'")
            if key not in result or not isinstance(result[key], list):
                result[key] = []
            result[key].append(val)
            i += 1
            continue

        # Key: Value
        m = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val == '':
                # Might be start of a list
                _last_key = key
                result[key] = []
            else:
                val = val.strip('"').strip("'")
                result[key] = val
                _last_key = key
        i += 1

    return result


def to_yaml_frontmatter(meta):
    """Generate YAML frontmatter string from metadata dict."""
    lines = ['---']
    # Always put title first
    if 'title' in meta:
        lines.append(f'title: "{meta["title"]}"')
    for key, val in meta.items():
        if key == 'title':
            continue
        if key == 'slug':
            continue
        if isinstance(val, list):
            lines.append(f'{key}:')
            for item in val:
                lines.append(f'  - {item}')
        elif isinstance(val, str):
            # Escape quotes in string values
            escaped = val.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f'{key}: {val}')
    lines.append('---')
    return '\n'.join(lines) + '\n'


def list_markdown_files(directory):
    """List all .md files in a directory, return metadata list."""
    items = []
    if directory.exists():
        for md_file in sorted(directory.glob('*.md'), key=lambda f: f.name):
            meta, body = parse_frontmatter(md_file)
            items.append({
                'title': meta.get('title', md_file.stem),
                'slug': meta.get('slug', md_file.stem),
                'date': meta.get('date', ''),
                'series': meta.get('series', ''),
                'excerpt': meta.get('excerpt', ''),
                'tags': meta.get('tags', []),
                'cover': meta.get('cover', ''),
            })
    # Sort by date descending
    items.sort(key=lambda x: x.get('date', ''), reverse=True)
    return items


# ── HTTP Handler ──────────────────────────────────────────────────────────

class EditorHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the CMS editor."""

    def log_message(self, format, *args):
        """Suppress default logging to stderr."""
        pass

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cors_headers()
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_str, status=200):
        """Send an HTML response."""
        body = html_str.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._cors_headers()
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        """Set CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _read_body(self):
        """Read the request body."""
        length = int(self.headers.get('Content-Length', 0))
        if length > 0:
            return self.rfile.read(length).decode('utf-8')
        return ''

    def _parse_path(self):
        """Parse the URL path and return parts."""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path.rstrip('/') or '/')
        return path, parsed.query

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        path, query = self._parse_path()

        try:
            if path == '/':
                self._serve_editor()
            elif path == '/api/articles':
                self._list_articles()
            elif path.startswith('/api/articles/'):
                slug = path[len('/api/articles/'):]
                self._get_article(slug)
            elif path == '/api/poems':
                self._list_poems()
            elif path.startswith('/api/poems/'):
                slug = path[len('/api/poems/'):]
                self._get_poem(slug)
            elif path == '/api/config':
                self._get_config()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

    def do_POST(self):
        """Handle POST requests."""
        path, _ = self._parse_path()

        try:
            if path == '/api/articles':
                self._create_article()
            elif path == '/api/poems':
                self._create_poem()
            elif path == '/api/deploy':
                self._deploy()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

    def do_PUT(self):
        """Handle PUT requests."""
        path, _ = self._parse_path()

        try:
            if path.startswith('/api/articles/'):
                slug = path[len('/api/articles/'):]
                self._update_article(slug)
            elif path.startswith('/api/poems/'):
                slug = path[len('/api/poems/'):]
                self._update_poem(slug)
            elif path == '/api/config':
                self._update_config()
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

    def do_DELETE(self):
        """Handle DELETE requests."""
        path, _ = self._parse_path()

        try:
            if path.startswith('/api/articles/'):
                slug = path[len('/api/articles/'):]
                self._delete_article(slug)
            elif path.startswith('/api/poems/'):
                slug = path[len('/api/poems/'):]
                self._delete_poem(slug)
            else:
                self._send_json({'error': 'Not found'}, 404)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

    # ── Editor HTML ───────────────────────────────────────────────────────

    def _serve_editor(self):
        """Serve the editor.html file."""
        if EDITOR_HTML.exists():
            html = EDITOR_HTML.read_text(encoding='utf-8')
            self._send_html(html)
        else:
            self._send_json({'error': 'editor.html not found'}, 404)

    # ── Articles CRUD ─────────────────────────────────────────────────────

    def _list_articles(self):
        """GET /api/articles"""
        items = list_markdown_files(ARTICLES_DIR)
        self._send_json(items)

    def _get_article(self, slug):
        """GET /api/articles/<slug>"""
        filepath = ARTICLES_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Article not found'}, 404)
            return
        meta, body = parse_frontmatter(filepath)
        meta['content'] = body.strip()
        self._send_json(meta)

    def _create_article(self):
        """POST /api/articles"""
        data = json.loads(self._read_body())
        title = data.get('title', '').strip()
        if not title:
            self._send_json({'error': 'Title is required'}, 400)
            return

        slug = slugify(title)
        if not slug:
            self._send_json({'error': 'Could not generate slug from title'}, 400)
            return

        filepath = ARTICLES_DIR / f'{slug}.md'
        if filepath.exists():
            self._send_json({'error': f'Article with slug "{slug}" already exists'}, 409)
            return

        content = data.get('content', '')
        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        meta = {
            'title': title,
            'date': data.get('date', ''),
            'series': data.get('series', ''),
            'tags': tags,
            'cover': data.get('cover', ''),
            'excerpt': data.get('excerpt', ''),
        }

        frontmatter = to_yaml_frontmatter(meta)
        full_content = frontmatter + '\n' + content.strip() + '\n'

        filepath.write_text(full_content, encoding='utf-8')
        self._send_json({'success': True, 'slug': slug}, 201)

    def _update_article(self, slug):
        """PUT /api/articles/<slug>"""
        filepath = ARTICLES_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Article not found'}, 404)
            return

        data = json.loads(self._read_body())

        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        meta = {
            'title': data.get('title', ''),
            'date': data.get('date', ''),
            'series': data.get('series', ''),
            'tags': tags,
            'cover': data.get('cover', ''),
            'excerpt': data.get('excerpt', ''),
        }

        frontmatter = to_yaml_frontmatter(meta)
        content = data.get('content', '')
        full_content = frontmatter + '\n' + content.strip() + '\n'

        filepath.write_text(full_content, encoding='utf-8')
        self._send_json({'success': True, 'slug': slug})

    def _delete_article(self, slug):
        """DELETE /api/articles/<slug>"""
        filepath = ARTICLES_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Article not found'}, 404)
            return

        filepath.unlink()
        self._send_json({'success': True})

    # ── Poems CRUD ────────────────────────────────────────────────────────

    def _list_poems(self):
        """GET /api/poems"""
        items = list_markdown_files(POEMS_DIR)
        self._send_json(items)

    def _get_poem(self, slug):
        """GET /api/poems/<slug>"""
        filepath = POEMS_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Poem not found'}, 404)
            return
        meta, body = parse_frontmatter(filepath)
        meta['content'] = body.strip()
        self._send_json(meta)

    def _create_poem(self):
        """POST /api/poems"""
        data = json.loads(self._read_body())
        title = data.get('title', '').strip()
        if not title:
            self._send_json({'error': 'Title is required'}, 400)
            return

        slug = slugify(title)
        if not slug:
            self._send_json({'error': 'Could not generate slug from title'}, 400)
            return

        filepath = POEMS_DIR / f'{slug}.md'
        if filepath.exists():
            self._send_json({'error': f'Poem with slug "{slug}" already exists'}, 409)
            return

        content = data.get('content', '')
        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        meta = {
            'title': title,
            'date': data.get('date', ''),
            'series': data.get('series', ''),
            'tags': tags,
            'cover': data.get('cover', ''),
            'excerpt': data.get('excerpt', ''),
        }

        frontmatter = to_yaml_frontmatter(meta)
        full_content = frontmatter + '\n' + content.strip() + '\n'

        filepath.write_text(full_content, encoding='utf-8')
        self._send_json({'success': True, 'slug': slug}, 201)

    def _update_poem(self, slug):
        """PUT /api/poems/<slug>"""
        filepath = POEMS_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Poem not found'}, 404)
            return

        data = json.loads(self._read_body())

        tags = data.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        meta = {
            'title': data.get('title', ''),
            'date': data.get('date', ''),
            'series': data.get('series', ''),
            'tags': tags,
            'cover': data.get('cover', ''),
            'excerpt': data.get('excerpt', ''),
        }

        frontmatter = to_yaml_frontmatter(meta)
        content = data.get('content', '')
        full_content = frontmatter + '\n' + content.strip() + '\n'

        filepath.write_text(full_content, encoding='utf-8')
        self._send_json({'success': True, 'slug': slug})

    def _delete_poem(self, slug):
        """DELETE /api/poems/<slug>"""
        filepath = POEMS_DIR / f'{slug}.md'
        if not filepath.exists():
            self._send_json({'error': 'Poem not found'}, 404)
            return

        filepath.unlink()
        self._send_json({'success': True})

    # ── Config ────────────────────────────────────────────────────────────

    def _get_config(self):
        """GET /api/config"""
        try:
            config = load_config()
            self._send_json(config)
        except Exception as e:
            self._send_json({'error': f'Failed to load config: {e}'}, 500)

    def _update_config(self):
        """PUT /api/config

        Accepts partial updates. Merges top-level keys into existing config.
        Special handling for series: if series is provided, it replaces the
        entire series dict.
        """
        try:
            data = json.loads(self._read_body())
            config = load_config()

            # Merge top-level keys
            for key in ['site_name', 'subtitle', 'author', 'description',
                         'avatar_text']:
                if key in data:
                    config[key] = data[key]

            # Merge about
            if 'about' in data:
                config['about'] = data['about']

            # Merge series
            if 'series' in data:
                config['series'] = data['series']

            # Merge colors
            if 'colors' in data:
                config['colors'] = data['colors']

            save_config(config)
            self._send_json({'success': True})
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

    # ── Deploy ────────────────────────────────────────────────────────────

    def _deploy(self):
        """POST /api/deploy

        Runs build.py first, then netlify deploy --prod.
        Uses Server-Sent Events style: returns JSON with progress info.
        For simplicity, runs synchronously and returns the result.
        """
        try:
            # Step 1: Build
            build_script = ROOT / 'build.py'
            if not build_script.exists():
                self._send_json({'error': 'build.py not found'}, 500)
                return

            print('[deploy] Running build.py...')
            result = subprocess.run(
                [sys.executable, str(build_script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            build_ok = result.returncode == 0
            build_output = (result.stdout or '') + '\n' + (result.stderr or '')

            if not build_ok:
                self._send_json({
                    'success': False,
                    'stage': 'build',
                    'output': build_output,
                    'error': 'Build failed'
                }, 500)
                return

            # Step 2: Deploy
            print('[deploy] Running netlify deploy...')
            result = subprocess.run(
                'npx netlify deploy --prod --dir=public',
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=300,
                shell=True,
            )
            deploy_ok = result.returncode == 0
            deploy_output = (result.stdout or '') + '\n' + (result.stderr or '')

            # Try to extract the URL from deploy output
            url_match = re.search(r'(https?://[^\s]+\.netlify\.app[^\s]*)', deploy_output)
            deploy_url = url_match.group(1) if url_match else None

            if deploy_ok:
                self._send_json({
                    'success': True,
                    'stage': 'deploy',
                    'output': build_output + '\n' + deploy_output,
                    'url': deploy_url or 'https://canyingji.netlify.app',
                })
            else:
                self._send_json({
                    'success': False,
                    'stage': 'deploy',
                    'output': build_output + '\n' + deploy_output,
                    'error': 'Deploy failed',
                }, 500)

        except subprocess.TimeoutExpired:
            self._send_json({'error': 'Deploy timed out'}, 500)
        except Exception as e:
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)


# ── Main ──────────────────────────────────────────────────────────────────

def find_free_port(start=5000, max_attempts=10):
    """Find a free port starting from `start`."""
    for port in range(start, start + max_attempts):
        try:
            server = HTTPServer(('', port), EditorHandler)
            server.server_close()
            return port
        except OSError:
            continue
    return start  # fallback


def main():
    port = find_free_port(5000)
    server = HTTPServer(('', port), EditorHandler)
    url = f'http://localhost:{port}'
    print(f'编辑器已启动: {url}')
    print(f'按 Ctrl+C 停止服务器')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()


if __name__ == '__main__':
    main()
