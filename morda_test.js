const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = [];
  page.on('console', m => logs.push('[console] ' + m.type() + ': ' + m.text()));
  page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
  page.on('requestfailed', r => logs.push('[reqfail] ' + r.url().slice(0, 100) + ' :: ' + (r.failure() || {}).errorText));

  const url = 'https://68504358d54d57.lhr.life/rezka.html?api=https://3eb2372711a99e.lhr.life';
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2000);

  // поиск
  await page.fill('#q', 'Матрица');
  await page.click('#go');
  await page.waitForSelector('.card', { timeout: 60000 });
  const cards = await page.$$eval('.card .t', els => els.map(e => e.textContent));
  console.log('НАЙДЕНО карточек:', cards.length, '|', cards.slice(0, 3).join(' / '));

  // клик по первой карточке
  await page.click('.card');
  await page.waitForSelector('.detail', { timeout: 90000 });
  await page.waitForTimeout(1500);

  const info = await page.evaluate(() => {
    const d = document.querySelector('.detail');
    return {
      h1: (d.querySelector('h1') || {}).textContent,
      eps: Array.from(d.querySelectorAll('.ep')).map(e => e.textContent.trim()),
      status: (document.getElementById('status') || {}).textContent,
      selOpts: Array.from(d.querySelectorAll('.sel option')).map(o => o.textContent),
    };
  });
  console.log('=== ДЕТАЛЬ (фильм) ===');
  console.log(JSON.stringify(info, null, 1));
  console.log('=== ЛОГИ ===');
  console.log(logs.slice(-15).join('\n'));

  await browser.close();
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });