const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Linux; Android 4.2.2; en-us; Nexus 5 Build/JOP40D) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19',
  });
  const page = await ctx.newPage();

  const base = 'https://rezka-tv.org/series/fiction/64703-follaut-2024-latest/447-le-production.html';
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 60000 });
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(2000);
    if ((await page.content()).includes('initCDNSeriesEvents')) break;
  }

  const out = [];
  for (let season = 1; season <= 2; season++) {
    for (let episode = 1; episode <= 8; episode++) {
      const t = Date.now();
      const res = await page.evaluate(async ({ season, episode, t }) => {
        const body = new URLSearchParams({
          id: '64703',
          translator_id: '447',
          season: String(season),
          episode: String(episode),
          favs: '',
          action: 'get_stream',
        });
        const r = await fetch('/ajax/get_cdn_series/?t=' + t, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
          credentials: 'include',
          body: body.toString(),
        });
        const text = await r.text();
        // ищем streams в ответе
        const m = text.match(/"url":"([^"]+)"/);
        return { status: r.status, len: text.length, url: m ? m[1] : null, sample: text.slice(0, 120) };
      }, { season, episode, t });

      let links = null;
      if (res.url) {
        // разакранируем \/ -> /, формат: [360p]url,[480p]url,...
        const clean = res.url.replace(/\\\//g, '/');
        links = [];
        for (const p of clean.split(',')) {
          const mm = p.match(/^\[([^\]]+)\](https?:\/\/[^\s,]+)/);
          if (mm) links.push({ q: mm[1], url: mm[2] });
        }
      }
      out.push({ season, episode, res, links });
      const qs = links ? links.map(l => l.q).join(',') : '—';
      console.log(`S${season}E${episode}: status=${res.status} len=${res.len} стримы=${qs} ${links && links.length ? links[0].url.slice(0, 70) : ''}`);
    }
  }

  require('fs').writeFileSync('/tmp/opencode/result.json', JSON.stringify(out, null, 2));
  await browser.close();
  console.log('\nСохранил: /tmp/opencode/result.json');
})().catch(e => { console.error('ОШИБКА:', e.message); process.exit(1); });