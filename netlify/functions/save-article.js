const { Buffer } = require('buffer');
exports.handler = async (e) => {
  const hd = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST, OPTIONS' };
  if (e.httpMethod === 'OPTIONS') return { statusCode: 200, headers: hd, body: '' };
  try {
    const { action, type, slug, title, date, series, cover, tags, excerpt, content, config } = JSON.parse(e.body || '{}');
    const T = process.env.GITHUB_TOKEN, GH = { Authorization: `token ${T}`, Accept: 'application/vnd.github.v3+json', 'User-Agent': 'bj' };
    const BASE = 'https://api.github.com/repos/ybn20060409-cpu/canyingji';
    const safeSlug = slug ? encodeURIComponent(slug) : '';
    const dir = type ? `content/${type}s` : '';

    if (action === 'get-config') {
      const r = await fetch(`${BASE}/contents/config.json`, { headers: GH });
      return { statusCode: r.ok ? 200 : 404, headers: hd, body: r.ok ? JSON.stringify(JSON.parse(Buffer.from((await r.json()).content, 'base64').toString('utf-8'))) : '{}' };
    }
    if (action === 'save-config' && config) {
      let sha = null; try { const g = await fetch(`${BASE}/contents/config.json`, { headers: GH }); if (g.ok) sha = (await g.json()).sha; } catch(_) {}
      const enc = Buffer.from(JSON.stringify(config, null, 2), 'utf-8').toString('base64');
      const r = await fetch(`${BASE}/contents/config.json`, { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'Update config', content: enc, sha }) });
      return { statusCode: r.ok ? 200 : r.status, headers: hd, body: r.ok ? '{"success":true}' : JSON.stringify({ error: (await r.json()).message }) };
    }
    if (action === 'list') {
      const r = await fetch(`${BASE}/contents/${dir}`, { headers: GH });
      if (!r.ok) return { statusCode: 200, headers: hd, body: '[]' };
      const files = await r.json();
      return { statusCode: 200, headers: hd, body: JSON.stringify(Array.isArray(files) ? files.filter(f => f.name.endsWith('.md') || f.name.endsWith('.html')).map(f => ({ name: f.name })) : []) };
    }
    if (action === 'save') {
      const path = `${dir}/${safeSlug}.md`;
      const fm = ['---', `title: "${title}"`, `date: ${date}`, `series: "${series}"`, `type: "${type}"`, `cover: "${cover}"`, `tags: [${(tags||[]).map(t=>`"${t}"`).join(', ')}]`, `excerpt: "${(excerpt||'').replace(/"/g,'\\"')}"`, '---', '', content||''].join('\n');
      let sha = null; try { const g = await fetch(`${BASE}/contents/${path}`, { headers: GH }); if (g.ok) sha = (await g.json()).sha; } catch(_) {}
      const enc = Buffer.from(fm, 'utf-8').toString('base64');
      const r = await fetch(`${BASE}/contents/${path}`, { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: `${sha?'Update':'Create'} ${title}`, content: enc, sha }) });
      return { statusCode: r.ok ? 200 : r.status, headers: hd, body: r.ok ? '{"success":true,"message":"Saved!"}' : JSON.stringify({ error: (await r.json()).message }) };
    }
    if (action === 'delete') {
      const path = `${dir}/${safeSlug}.md`;
      const g = await fetch(`${BASE}/contents/${path}`, { headers: GH });
      if (!g.ok) return { statusCode: 404, body: '{"error":"Not found"}' };
      const r = await fetch(`${BASE}/contents/${path}`, { method: 'DELETE', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: `Delete ${title||slug}`, sha: (await g.json()).sha }) });
      return { statusCode: r.ok ? 200 : r.status, headers: hd, body: r.ok ? '{"success":true}' : JSON.stringify({ error: (await r.json()).message }) };
    }
    return { statusCode: 400, body: '{"error":"Invalid action"}' };
  } catch(err) { return { statusCode: 500, body: JSON.stringify({ error: err.message }) }; }
};
