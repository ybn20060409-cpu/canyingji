const { Buffer } = require('buffer');

function ok(body) { return { statusCode: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; }
function err(msg, code) { return { statusCode: code || 500, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ error: msg }) }; }

function parseMd(raw) {
  const text = Buffer.from(raw, 'base64').toString('utf-8');
  const m = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return { content: text, title: '', date: '', series: '', tags: [], excerpt: '', cover: '', type: '' };
  const fm = {}, body = m[2];
  m[1].split('\n').forEach(line => {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) {
      if (kv[1] === 'tags') { try { fm.tags = JSON.parse(kv[2]); } catch(e) { fm.tags = []; } }
      else fm[kv[1]] = kv[2].replace(/^"(.*)"$/, '$1');
    }
  });
  return { ...fm, content: body.trim(), title: fm.title || '', date: fm.date || '', series: fm.series || '', tags: fm.tags || [], excerpt: fm.excerpt || '', cover: fm.cover || '', type: fm.type || '' };
}

exports.handler = async (e) => {
  if (e.httpMethod === 'OPTIONS') return { statusCode: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST, OPTIONS' }, body: '' };
  if (e.httpMethod !== 'POST') return err('POST only', 405);

  try {
    const b = JSON.parse(e.body || '{}');
    const { action, type, slug, title, date, series, cover, tags, excerpt, content, config } = b;
    const T = process.env.GITHUB_TOKEN;
    if (!T) return err('Server config error: GITHUB_TOKEN not set', 500);
    const GH = { Authorization: 'token '+T, Accept: 'application/vnd.github.v3+json', 'User-Agent': 'beiji-editor' };
    const BASE = 'https://api.github.com/repos/ybn20060409-cpu/canyingji';
    const dir = type ? 'content/'+(type==='article'?'articles':'poems') : '';

    async function getSha(path) { try { const r = await fetch(BASE+'/contents/'+path, { headers: GH }); if (r.ok) return (await r.json()).sha; } catch(_) {} return null; }

    // ── Get full config ──
    if (action === 'get-config') {
      const r = await fetch(BASE+'/contents/config.json', { headers: GH });
      if (!r.ok) return err('Config not found', 404);
      const cfg = JSON.parse(Buffer.from((await r.json()).content, 'base64').toString('utf-8'));
      return ok(cfg);
    }

    // ── Save config ──
    if (action === 'save-config' && config) {
      const sha = await getSha('config.json');
      const enc = Buffer.from(JSON.stringify(config, null, 2), 'utf-8').toString('base64');
      const r = await fetch(BASE+'/contents/config.json', { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'Update config', content: enc, sha: sha || undefined }) });
      if (!r.ok) return err((await r.json()).message, r.status);
      return ok({ success: true });
    }

    // ── List files ──
    if (action === 'list') {
      const r = await fetch(BASE+'/contents/'+dir, { headers: GH });
      if (!r.ok) return ok([]);
      const files = await r.json();
      const items = Array.isArray(files) ? files.filter(f => f.name.endsWith('.md')).map(f => {
        // Try to parse filename to get readable title
        try { return { name: f.name, slug: f.name.replace('.md',''), sha: f.sha }; } catch(_) { return { name: f.name, slug: f.name, sha: f.sha }; }
      }) : [];
      return ok(items);
    }

    // ── Get single file ──
    if (action === 'get' && slug) {
      const safe = encodeURIComponent(slug);
      const r = await fetch(BASE+'/contents/'+dir+'/'+safe+'.md', { headers: GH });
      if (!r.ok) return err('File not found', 404);
      const d = await r.json();
      const parsed = parseMd(d.content);
      return ok({ ...parsed, sha: d.sha, slug: slug });
    }

    // ── Save file ──
    if (action === 'save' && slug && type) {
      const safe = encodeURIComponent(slug);
      const path = dir+'/'+safe+'.md';
      const fm = ['---', 'title: "'+(title||slug)+'"', 'date: '+(date||new Date().toISOString().slice(0,10)), 'series: "'+(series||'')+'"', 'type: "'+type+'"', 'cover: "'+(cover||'gradient-ocean')+'"', 'tags: ['+(tags||[]).map(t=>'"'+t+'"').join(', ')+']', 'excerpt: "'+(excerpt||'').replace(/"/g,'\\"')+'"', '---', '', content||''].join('\n');
      const enc = Buffer.from(fm, 'utf-8').toString('base64');
      const sha = await getSha(path);
      const r = await fetch(BASE+'/contents/'+path, { method: 'PUT', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: (sha?'Update':'Create')+' '+(title||slug), content: enc, sha: sha || undefined }) });
      if (!r.ok) return err((await r.json()).message, r.status);
      return ok({ success: true, slug: slug });
    }

    // ── Delete file ──
    if (action === 'delete' && slug && type) {
      const safe = encodeURIComponent(slug);
      const path = dir+'/'+safe+'.md';
      const sha = await getSha(path);
      if (!sha) return err('File not found', 404);
      const r = await fetch(BASE+'/contents/'+path, { method: 'DELETE', headers: { ...GH, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'Delete '+(title||slug), sha: sha }) });
      if (!r.ok) return err((await r.json()).message, r.status);
      return ok({ success: true });
    }

    return err('Invalid action: '+(action||'none'), 400);
  } catch(ex) { return err(ex.message, 500); }
};
