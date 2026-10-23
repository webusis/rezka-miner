const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = [];
  page.on('console', m => logs.push('[console] ' + m.type() + ': ' + m.text()));
  page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
  page.on('requestfailed', r => logs.push('[reqfail] ' + r.url().slice(0, 120) + ' :: ' + (r.failure() || {}).errorText));

  const url = 'https://3fbc8ff9a20976.lhr.life/rezka.html?api=https://2b3df12df47801.lhr.life';
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  console.log('Hls loaded:', await page.evaluate(() => typeof window.Hls));

  // поиск фильма
  await page.fill('#q', 'Матрица');
  await page.click('#go');
  await page.waitForSelector('.card', { timeout: 60000 });
  await page.click('.card');
  await page.waitForSelector('.detail', { timeout: 90000 });
  await page.waitForTimeout(1500);

  const info = await page.evaluate(() => {
    const d = document.querySelector('.detail');
    return {
      h1: (d.querySelector('h1') || {}).textContent,
      qsel: Array.from(d.querySelectorAll('.qsel option')).map(o => o.textContent),
      eps: Array.from(d.querySelectorAll('.ep')).map(e => e.textContent.trim()),
      chips: Array.from(d.querySelectorAll('.qchip')).map(c => c.textContent.trim()),
      status: (document.getElementById('status') || {}).textContent,
    };
  });
  console.log('=== ФИЛЬМ ===');
  console.log(JSON.stringify(info, null, 1));

  // клик «Смотреть фильм», проверяем плеер
  await page.click('.ep');
  await page.waitForTimeout(6000);
  const pl = await page.evaluate(() => ({
    playerShow: document.getElementById('player').classList.contains('show'),
    hlsActive: !!window.__hls_test || undefined,
    videoSrc: (document.getElementById('video') || {}).src ? 'set' : 'empty',
    ptitle: (document.getElementById('ptitle') || {}).textContent,
    status: (document.getElementById('status') || {}).textContent,
  }));
  console.log('=== ПЛЕЕР ===');
  console.log(JSON.stringify(pl, null, 1));

  console.log('=== ЛОГИ (последние 12) ===');
  console.log(logs.slice(-12).join('\n'));
  await browser.close();
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });