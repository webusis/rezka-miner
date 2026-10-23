// agent.js — прокси-мост к rezka-tv.org через playwright.
// Держит Anubis-сессию живой, выполняет fetch-запросы в контексте браузера.
// Порт: 9333. Эндпоинты:
//   POST /proxy {url, method?, body?, headers?} -> {status, headers, text}
//   GET  /cookies -> текущие куки
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 9333;
const HOME = 'https://rezka-tv.org';
const COOKIES_FILE = path.join(__dirname, 'data', 'cookies.json');
const SESSION_REFRESH_MS = 15 * 60 * 1000; // обновляем сессию каждые 15 минут

let page = null;
let lastRefresh = 0;

async function refreshSession() {
  // Открываем главную, ждём прохода Anubis (появление контента режки)
  await page.goto(HOME + '/', { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
  let ok = false;
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(2000);
    const cookies = await page.context().cookies(HOME);
    const html = await page.content().catch(() => '');
    if (html.includes('sof.tv') || !html.includes('anubis')) { ok = true; break; }
  }
  if (!ok) throw new Error('Anubis challenge not solved');
  lastRefresh = Date.now();
  const cookies = await page.context().cookies();
  fs.mkdirSync(path.dirname(COOKIES_FILE), { recursive: true });
  fs.writeFileSync(COOKIES_FILE, JSON.stringify(cookies, null, 2));
  console.log(`[agent] сессия обновлена (${cookies.length} кук)`);
}

async function proxyFetch({ url, method = 'GET', body, headers = {} }) {
  const res = await page.evaluate(async ({ url, method, body, headers }) => {
    const r = await fetch(url, {
      method,
      headers: { ...headers },
      credentials: 'include',
      body: body || undefined,
      redirect: 'follow',
    });
    const text = await r.text();
    return { status: r.status, headers: Object.fromEntries(r.headers.entries()), text };
  }, { url, method, body, headers });
  return res;
}

const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks).toString('utf8');

  if (req.method === 'POST' && req.url.startsWith('/proxy')) {
    try {
      const q = JSON.parse(raw);
      const out = await proxyFetch(q);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(out));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  if (req.method === 'GET' && req.url === '/cookies') {
    const cookies = await page.context().cookies();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(cookies));
    return;
  }
  res.writeHead(404); res.end('not found');
});

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Linux; Android 4.2.2; en-us; Nexus 5 Build/JOP40D) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19',
    locale: 'ru-RU',
  });
  page = await ctx.newPage();
  await refreshSession();
  setInterval(() => {
    if (Date.now() - lastRefresh > SESSION_REFRESH_MS) {
      refreshSession().catch(e => console.error('[agent] refresh error:', e.message));
    }
  }, 60 * 1000);
  server.listen(PORT, () => console.log(`[agent] прокси на :${PORT}`));
})().catch(e => { console.error('[agent] FATAL:', e); process.exit(1); });