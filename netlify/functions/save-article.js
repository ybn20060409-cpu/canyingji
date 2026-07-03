const { Buffer } = require('buffer');

exports.handler = async (event) => {
  const h = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST, OPTIONS' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: h, body: '' };

  try {
    const { action, type, slug, title, date, series, cover, tags, excerpt, content, config } = JSON.parse(event.body || '{}');
    const T = process.env.GITHUB_TOKEN;
    const GH = { Authorization: `token ${T}`, Accept: 'application/vnd.github.v3+json', 'User-Agent': 'bj' };
    const BASE = 'https://api.github.com/repos/ybn20060409-cpu/canyingji';

    // Get config
    if (action === 'get-config') {
      const r = await fetch(`${BASE}/contents/config.json`, { headers: GH });
      if (!r.ok) return { statusCode: 404, body: '{}' };
      const d = await r.json();
      const cfg = JSON.parse(Buffer.from(d.content, 'base64').toString('utf-8'));
      return { statusCode: 200, headers: h, body: JSON.stringify(cfg) };
    }

    // Save config (series / about)
    if (action === 'save-config') {
      let sha = null;
      try { const gr = await fetch(`${BASE}/contents/config.json`, { headers: GH }); if (gr.ok) sha = (await gr.json()).sha; } catch(e) {}
      const enc = Buffer.from(JSON.stringify(config, null, 2), 'utf-8').toString('base64');
      const r = await fetch(`${BASE}/contents/config.json`, { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'Update config', content: enc, sha }) });
      if (!r.ok) return { statusCode: r.status, body: JSON.stringify({ error: (await r.json()).message }) };
      return { statusCode: 200, headers: h, body: JSON.stringify({ success: true }) };
    }

    // List
    if (action === 'list') {
      const dir = type === 'article' ? 'articles' : 'poems';
      let r = await fetch(`${BASE}/contents/content/${dir}`, { headers: GH });
      if (!r.ok) r = await fetch(`${BASE}/contents/${type}`, { headers: GH });
      if (!r.ok) return { statusCode: 200, headers: h, body: '[]' };
      const files = await r.json();
      const items = Array.isArray(files) ? files.filter(f => f.name.endsWith('.md') || f.name.endsWith('.html')) : [];
      return { statusCode: 200, headers: h, body: JSON.stringify(items.map(f => ({ name: f.name }))) };
    }

    // Save article/poem
    if (action === 'save') {
      const dir = `content/${type}s`;
      const mdPath = `${dir}/${slug}.md`;
      const fm = ['---', `title: "${title}"`, `date: ${date}`, `series: "${series}"`, `type: "${type}"`, `cover: "${cover}"`, `tags: [${(tags||[]).map(t=>`"${t}"`).join(', ')}]`, `excerpt: "${(excerpt||'').replace(/"/g,'\\"')}"`, '---', '', content||''].join('\n');
      let sha = null;
      try { const gr = await fetch(`${BASE}/contents/${mdPath}`, { headers: GH }); if (gr.ok) sha = (await gr.json()).sha; } catch(e) {}
      const enc = Buffer.from(fm, 'utf-8').toString('base64');
      const r = await fetch(`${BASE}/contents/${mdPath}`, { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: `${sha?'Update':'Create'} ${title}`, content: enc, sha }) });
      if (!r.ok) return { statusCode: r.status, body: JSON.stringify({ error: (await r.json()).message }) };
      return { statusCode: 200, headers: h, body: JSON.stringify({ success: true, message: 'Saved!' }) };
    }

    // Delete
    if (action === 'delete') {
      const dir = `content/${type}s`;
      const mdPath = `${dir}/${slug}.md`;
      const gr = await fetch(`${BASE}/contents/${mdPath}`, { headers: GH });
      if (!gr.ok) return { statusCode: 404, body: JSON.stringify({ error: 'Not found' }) };
      const r = await fetch(`${BASE}/contents/${mdPath}`, { method: 'DELETE', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: `Delete ${title||slug}`, sha: (await gr.json()).sha }) });
      if (!r.ok) return { statusCode: r.status, body: JSON.stringify({ error: (await r.json()).message }) };
      return { statusCode: 200, headers: h, body: JSON.stringify({ success: true }) };
    }

    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid action' }) };
  } catch(e) { return { statusCode: 500, body: JSON.stringify({ error: e.message }) }; }
};
