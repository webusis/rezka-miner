# -*- coding: utf-8 -*-
# rezka_curl.py — клиент к rezka-tv.org без браузера: urllib + ручное решение
# Anubis PoW. Python 2.7 / 3.x совместим (для APK на python2.7).
# API: search / get_title / get_episodes / get_stream / parse_streams / api_get_cdn.
import json
import re
import time
import os
import hashlib
import sys
import gzip
import threading

PY2 = sys.version_info[0] == 2

if PY2:
    from HTMLParser import HTMLParser
    def _unescape(s):
        return HTMLParser().unescape(s)
else:
    from html import unescape as _unescape

if PY2:
    import urllib2 as _urlreq
    import urllib as _urlmod
    from urllib import quote as _quote
    import cookielib as _cookiejar
    from StringIO import StringIO as _BytesIO
    # На Android 4.2 нет системных CA в формате openssl —
    # верификация сертификатов всё равно не работает, отключаем её.
    try:
        import ssl as _sslmod
        _sslmod._create_default_https_context = _sslmod._create_unverified_context
    except Exception:
        pass
else:
    import urllib.request as _urlreq
    import urllib.parse as _urlmod
    from urllib.parse import quote as _quote
    import http.cookiejar as _cookiejar
    from io import BytesIO as _BytesIO

BASE = 'https://rezka-tv.org'
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_APP_DIR, 'data', 'cache')
COOKIE_FILE = os.path.join(_APP_DIR, 'data', 'cookies.txt')
try:
    os.makedirs(CACHE_DIR)
except OSError:
    pass

_LOG_FILE = os.path.join(_APP_DIR, 'server.log')
_LOG_FLAG_FILE = os.path.join(_APP_DIR, 'data', 'log_enabled')
_LOG_MAX_BYTES = 2 * 1024 * 1024      # ротация: файл больше — оставляем только хвост
_LOG_FLUSH_EVERY = 3.0                # сброс в файл не чаще раза в N секунд
_LOG_LOCK = threading.Lock()
_LOG_BUF = []
_LOG_LAST_FLUSH = [0.0]
_LOG_ENABLED_CACHE = [True]   # кэш флага: файл читается один раз при старте
_LOG_FLAG_INITED = [False]


def log_enabled():
    """Флаг логирования из кэша (диск не трогается на каждый вызов)."""
    if not _LOG_FLAG_INITED[0]:
        try:
            with open(_LOG_FLAG_FILE) as f:
                _LOG_ENABLED_CACHE[0] = f.read().strip() != '0'
        except Exception:
            _LOG_ENABLED_CACHE[0] = True
        _LOG_FLAG_INITED[0] = True
    return _LOG_ENABLED_CACHE[0]


def set_log_enabled(v):
    """Переключить логирование: пишем файл и обновляем кэш в памяти."""
    d = os.path.dirname(_LOG_FLAG_FILE)
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        with open(_LOG_FLAG_FILE, 'w') as f:
            f.write('1' if v else '0')
        _LOG_ENABLED_CACHE[0] = bool(v)
        _LOG_FLAG_INITED[0] = True
        return True
    except Exception:
        return False


def clear_logs():
    """Удалить файлы логов рядом с приложением. Вернуть список удалённого."""
    with _LOG_LOCK:
        _flush_log()
        global _LOG_BUF
        _LOG_BUF = []
        _LOG_LAST_FLUSH[0] = time.time()  # сразу после очистки не флашиться
    removed = []
    for name in os.listdir(_APP_DIR):
        if name.endswith('.log'):
            try:
                os.remove(os.path.join(_APP_DIR, name))
                removed.append(name)
            except Exception:
                pass
    return removed


def _flush_log():
    """Один fopen/fwrite/fclose на весь накопленный блок + ротация по размеру."""
    global _LOG_BUF
    if not _LOG_BUF:
        return
    chunk = ''.join(_LOG_BUF)
    _LOG_BUF = []
    try:
        with open(_LOG_FILE, 'a') as f:
            f.write(chunk)
    except Exception:
        return
    # ротация: файл разросся — оставляем только хвост (не больше половины лимита)
    try:
        if os.path.getsize(_LOG_FILE) > _LOG_MAX_BYTES:
            with open(_LOG_FILE, 'rb') as f:
                data = f.read()
            tail = data[-_LOG_MAX_BYTES // 2:]
            nl = tail.find(b'\n')
            if nl != -1:
                tail = tail[nl + 1:]
            with open(_LOG_FILE, 'wb') as f:
                f.write(tail)
    except Exception:
        pass


def _log(msg, prefix='[curl]'):
    """Буферизованная запись в server.log (сброс раз в ~3 сек, а не на каждый вызов).
    prefix=None — msg уже готовая строка (server.py)."""
    if not log_enabled():
        return
    if prefix:
        line = '%s %s %s\n' % (prefix, time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    else:
        line = msg if msg.endswith('\n') else msg + '\n'
    with _LOG_LOCK:
        _LOG_BUF.append(line)
        now = time.time()
        if now - _LOG_LAST_FLUSH[0] >= _LOG_FLUSH_EVERY:
            _LOG_LAST_FLUSH[0] = now
            _flush_log()

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

_jar = None
_opener = None


def _urlencode(params):
    """urlencode с utf-8-кодированием значений (для py2)."""
    out = {}
    for k, v in (params or {}).items():
        if PY2 and isinstance(v, unicode):
            v = v.encode('utf-8')
        out[k] = v
    return _urlmod.urlencode(out)


def _open_url(url, timeout=90):
    global _jar, _opener
    if _opener is None:
        _jar = _cookiejar.LWPCookieJar()
        try:
            _jar.load(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
        _opener = _urlreq.build_opener(_urlreq.HTTPCookieProcessor(_jar))
    req = _urlreq.Request(url)
    req.add_header('User-Agent', UA)
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.9,en;q=0.5')
    req.add_header('Accept-Encoding', 'gzip, deflate')
    req.add_header('Referer', BASE + '/')
    try:
        resp = _opener.open(req, timeout=timeout)
    finally:
        try:
            _jar.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
    data = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        if PY2:
            data = gzip.GzipFile(fileobj=_BytesIO(data)).read()
        else:
            data = gzip.decompress(data)
    return data.decode('utf-8', 'replace')


def _fetch(url, method='GET', body=None, headers=None, timeout=90):
    """GET/POST через urllib. URL уже должен быть percent-encoded."""
    data = None
    if method == 'POST' and body is not None:
        data = body.encode('utf-8') if isinstance(body, unicode if PY2 else str) else body
    req = _urlreq.Request(url, data=data)
    req.add_header('User-Agent', UA)
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.9,en;q=0.5')
    req.add_header('Accept-Encoding', 'gzip, deflate')
    req.add_header('Referer', BASE + '/')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    global _jar, _opener
    if _opener is None:
        _open_url(BASE + '/', timeout=max(timeout, 30))
    try:
        resp = _opener.open(req, timeout=timeout)
    finally:
        try:
            _jar.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
    data = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        if PY2:
            data = gzip.GzipFile(fileobj=_BytesIO(data)).read()
        else:
            data = gzip.decompress(data)
    return data.decode('utf-8', 'replace')


def _anubis_pass(html, target_url, timeout=90):
    """Решает Anubis PoW-челлендж (1.25): sha256(randomData+nonce), ведущие
    floor(difficulty/2) нулевых байт; GET pass-challenge ставит куку anubis-auth
    и редиректит на target_url."""
    m = re.search(r'<script id="anubis_challenge" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return html
    data = json.loads(m.group(1))
    ch = data['challenge']
    diff = data['rules']['difficulty']
    p = diff // 2
    odd = diff % 2 != 0
    rd = ch['randomData']
    if PY2:
        rd = rd.encode('utf-8') if isinstance(rd, unicode) else rd
    else:
        rd = rd.encode('utf-8') if isinstance(rd, str) else rd
    target = b'\x00' * p
    _log('anubis: diff=%s p=%s odd=%s url=%s' % (diff, p, odd, target_url[:90]))
    t0 = time.time()
    nonce = 0
    while True:
        n = str(nonce)
        if PY2:
            h = hashlib.sha256(rd + n).digest()
        else:
            h = hashlib.sha256(rd + n.encode('ascii')).digest()
        if h[:p] == target and (not odd or h[p] >> 4 == 0):
            break
        nonce += 1
    _log('anubis: solved nonce=%d t=%.2fs' % (nonce, time.time() - t0))
    if PY2:
        response = h.encode('hex')
    else:
        response = h.hex()
    q = _urlencode({'id': ch['id'], 'response': response, 'nonce': nonce,
                    'redir': target_url, 'elapsedTime': '1'})
    return _fetch(BASE + '/.within.website/x/cmd/anubis/api/pass-challenge?' + q, timeout=timeout)


def proxy(url, method='GET', body=None, headers=None, timeout=120):
    """Дёрнуть URL; при Anubis-челлендже решаем PoW и повторяем (до 3 раз)."""
    _log('proxy: %s %s' % (method, url[:110]))
    t0 = time.time()
    text = _fetch(url, method, body, headers, timeout=timeout)
    rounds = 0
    for _ in range(3):
        if '<script id="anubis_challenge"' not in text:
            break
        text = _anubis_pass(text, url if method == 'GET' else url.split('?')[0], timeout)
        rounds += 1
    _log('proxy: done rounds=%d t=%.1fs len=%d' % (rounds, time.time() - t0, len(text) if text else -1))
    return text


def _cache_digest(key):
    """md5-хэш ключа кэша, устойчивый к юникоду в py2/py3."""
    key = _u2b(key)
    if PY2:
        return hashlib.md5(key).hexdigest()
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def cache_get(key, ttl=3600):
    path = os.path.join(CACHE_DIR, _cache_digest(key) + '.json')
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < ttl:
            try:
                with open(path, 'rb') as f:
                    return json.loads(f.read().decode('utf-8'))
            except Exception:
                return None
    return None


def _json_bytes(data):
    """json.dumps → utf-8 байты, устойчиво к юникоду/байтам в py2."""
    s = json.dumps(data, ensure_ascii=False)
    if PY2 and not isinstance(s, unicode):
        s = s.decode('utf-8')
    return s.encode('utf-8')


def cache_set(key, data):
    path = os.path.join(CACHE_DIR, _cache_digest(key) + '.json')
    try:
        with open(path, 'wb') as f:
            f.write(_json_bytes(data))
    except Exception:
        pass


def api_get_cdn(id, translator_id, action, season=None, episode=None):
    """Дёргает ajax/get_cdn_series."""
    t = int(time.time() * 1000)
    params = {'id': id, 'translator_id': translator_id, 'favs': '', 'action': action}
    if season is not None:
        params['season'] = season
    if episode is not None:
        params['episode'] = episode
    url = '%s/ajax/get_cdn_series/?t=%d' % (BASE, t)
    body = _urlencode(params)
    text = proxy(url, 'POST', body, {'Content-Type': 'application/x-www-form-urlencoded',
                                     'X-Requested-With': 'XMLHttpRequest'})
    try:
        return json.loads(text)
    except Exception:
        return {'error': 'bad json', 'raw': text[:300]}


def parse_streams(url_str):
    """'[360p]https://x.mp4,...' -> {'360p': url}. Премиум-качества отбрасываются."""
    if not url_str:
        return {}
    out = {}
    for p in url_str.split(','):
        m = re.match(r'\[([^\]]+)\](https?://[^\s,]+)', p)
        if not m:
            continue
        q, u = m.group(1), m.group(2)
        if '<' in q or '>' in q or 'pjs-prem' in q or 'prem-icon' in q:
            continue
        out[q] = u
    return out


def _q(s):
    """percent-encode строки для query (utf-8)."""
    if PY2:
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        return _quote(s)
    return _quote(s)


def _u2b(s):
    """py2: юникод → utf-8 байты (для %s-форматирования и quote)."""
    if PY2 and isinstance(s, unicode):
        return s.encode('utf-8')
    return s


def parse_cards(html, limit=40):
    """Карточки из разметки b-content__inline_item (поиск, /new/, категории)."""
    items = []
    for m in re.finditer(r'<div class="b-content__inline_item" data-id="(\d+)" data-url="([^"]+)">(.*?)</div></div>', html, re.S):
        did, durl, inner = m.groups()
        title = re.search(r'<a href="[^"]*">([^<]*)</a>', inner)
        img = re.search(r'<img src="([^"]+)"[^>]*alt="[^"]*"', inner)
        entity = re.search(r'<i class="entity">([^<]*)</i>', inner)
        info = re.search(r'<span class="info">([^<]*)</span>', inner)
        meta = re.search(r'<div>([^<]*)</div>', inner)
        items.append({
            'id': int(did),
            'url': durl,
            'title': title.group(1) if title else durl,
            'poster': img.group(1) if img else None,
            'type': (entity.group(1) if entity else '').strip(),
            'info': info.group(1) if info else '',
            'meta': meta.group(1) if meta else '',
        })
        if len(items) >= limit:
            break
    return items


def search(q, limit=15):
    """Поиск: список карточек."""
    q = _u2b(q)
    cache_key = 'search:%s' % q
    cached = cache_get(cache_key, ttl=600)
    if cached:
        return cached
    url = '%s/search/?do=search&subaction=search&q=%s' % (BASE, _q(q))
    html = proxy(url)
    items = parse_cards(html, limit)
    cache_set(cache_key, items)
    return items


NEW_FILTERS = ('last', 'popular', 'recommendation', 'watching')


def new_items(filter_key='last', genre=None, page=1, limit=40):
    """Главная: /new/ с сортировкой (поступления/популярные/смотрят), жанром
    и пагинацией (/new/page/N/). genre: '1' фильмы, '2' сериалы,
    '3' мультфильмы, '4' тв-шоу, '82' аниме."""
    f = filter_key if filter_key in NEW_FILTERS else 'last'
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    cache_key = 'new:%s:%s:p%s:%s' % (f, genre, page, limit)
    cached = cache_get(cache_key, ttl=600)
    if cached:
        return cached
    q = 'filter=%s' % f
    if genre:
        q += '&genre=%s' % genre
    if page > 1:
        url = '%s/new/page/%d/?%s' % (BASE, page, q)
    else:
        url = '%s/new/?%s' % (BASE, q)
    html = proxy(url)
    items = parse_cards(html, limit)
    cache_set(cache_key, items)
    return items


def fetch_html(url):
    """HTML страницы тайтла (с кэшем)."""
    url = _u2b(url)
    cache_key = 'html:%s' % url
    cached = cache_get(cache_key, ttl=600)
    if cached:
        return cached
    html = proxy(url)
    cache_set(cache_key, html)
    return html


def parse_translators(html, dtype, skip_premium=True):
    """Список переводов со страницы (дедуп по id, premium отсекаются)."""
    trs = {}
    for m in re.finditer(r'<a[^>]*b-translator__items[^>]*>', html):
        tag = m.group(0)
        cm = re.search(r'class="([^"]*)"', tag)
        tm = re.search(r'title="([^"]*)"', tag)
        dm = re.search(r'data-translator_id="(\d+)"', tag)
        if not dm:
            continue
        tid = dm.group(1)
        premium = bool(cm and 'b-prem_translator' in cm.group(1))
        name = tm.group(1) if tm else ''
        if tid in trs:
            trs[tid]['premium'] = trs[tid]['premium'] or premium
        else:
            trs[tid] = {'id': int(tid), 'name': name, 'premium': premium}
    if not trs:
        for m in re.finditer(r'data-translator_id="(\d+)"[^>]*>([^<]+)<', html):
            tid = m.group(1)
            if tid not in trs:
                trs[tid] = {'id': int(tid), 'name': m.group(2).strip(), 'premium': False}
    atid = active_translator_id(html)
    for t in trs.values():
        t['active'] = t['id'] == atid
    out = [t for t in trs.values() if not (skip_premium and t['premium'])]
    if skip_premium and not out:
        out = list(trs.values())
    if not out:
        # переводов в разметке нет — у тайтла единственный перевод:
        # берём tid из initCDN и создаём виртуальный перевод
        m = re.search(r'initCDN(?:Series|Movies)Events\(\d+,\s*(\d+)', html)
        if m:
            out = [{'id': int(m.group(1)), 'name': u'Оригинал', 'premium': False, 'active': True}]
    return out


def active_translator_id(html):
    m = re.search(r'b-translator__item[^"]*active[^"]*"[^>]*data-translator_id="(\d+)"', html)
    return int(m.group(1)) if m else None


def parse_seasons_episodes(html):
    """Сезоны и серии активного перевода из HTML страницы."""
    seasons = []
    for m in re.finditer(r'<div class="b-simple_season__item[^"]*"[^>]*data-season_id="(\d+)"[^>]*>(?:<span[^>]*>)?([^<]*)', html):
        seasons.append({'season': int(m.group(1)), 'title': m.group(2).strip()})
    episodes = []
    for m in re.finditer(r'<a class="b-simple_episode__item[^"]*"[^>]*data-season_id="(\d+)"[^>]*data-episode_id="(\d+)"[^>]*>(?:<span[^>]*>)?([^<]*)', html):
        episodes.append({'season': int(m.group(1)), 'episode': int(m.group(2)), 'title': m.group(3).strip()})
    return seasons, episodes


def get_episodes(id, translator_id):
    """Серии переводчика через API get_episodes."""
    resp = api_get_cdn(id, translator_id, 'get_episodes')
    seasons_html = resp.get('seasons') or ''
    episodes_html = resp.get('episodes') or ''
    seasons = []
    for m in re.finditer(r'data-(?:season|tab)_id="(\d+)"[^>]*>(?:<span[^>]*>)?([^<]*)', seasons_html):
        seasons.append({'season': int(m.group(1)), 'title': m.group(2).strip()})
    episodes = []
    for m in re.finditer(r'<[^>]+class="[^"]*b-simple_episode__item[^"]*"[^>]*data-season_id="(\d+)"[^>]*data-episode_id="(\d+)"[^>]*>(.*?)</', episodes_html, re.S):
        inner = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        episodes.append({'season': int(m.group(1)), 'episode': int(m.group(2)), 'title': inner})
    return seasons, episodes, resp.get('url')


def _fetch_qualities_pool(tr_out, post_id, tr_id):
    """Параллельно тянем потоки всех серий (py2/py3, без concurrent.futures).
    Для тяжёлых сериалов (100+ серий) синхронный цикл вешал клиент на таймаут."""
    try:
        import Queue as _Q
    except ImportError:
        import queue as _Q
    from threading import Thread
    tasks = []
    for s in tr_out['seasons']:
        for ep in s['episodes']:
            tasks.append((s['season'], ep['episode'], ep))
    q = _Q.Queue()
    for t in tasks:
        q.put(t)

    def worker():
        while True:
            try:
                season, ep_num, ep = q.get_nowait()
            except Exception:
                return
            try:
                resp = api_get_cdn(post_id, tr_id, 'get_stream', season=season, episode=ep_num)
                ep['qualities'] = parse_streams(resp.get('url'))
            except Exception:
                ep['qualities'] = {}
            try:
                time.sleep(0.05)
            except Exception:
                pass

    n = min(8, len(tasks)) if tasks else 1
    ths = [Thread(target=worker) for _ in range(n)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()


def get_title(url, with_streams=True):
    """Полная структура тайтла: переводы, сезоны, серии, качества."""
    url = _u2b(url)
    cache_key = 'title2:%s:streams=%s' % (url, with_streams)
    cached = cache_get(cache_key, ttl=3600)
    if cached:
        return cached

    html = fetch_html(url)
    title = re.search(r'<title>([^<]*)</title>', html)
    og = re.search(r'property="og:image" content="([^"]+)"', html)
    desc = re.search(r'property="og:description" content="([^"]+)"', html)
    meta = re.search(r'<div class="b-post__info"[^>]*>(.*?)</div>', html, re.S)
    meta_text = re.sub(r'<[^>]+>', ' ', meta.group(1)) if meta else ''
    meta_text = re.sub(r'\s+', ' ', meta_text).strip()

    # инфо-таблица: пары «поле: значение» текстом, без ссылок
    facts = []
    for m in re.finditer(r'<td class="l"><h2>([^<]*)</h2>\s*:</td>\s*<td[^>]*>(.*?)</td>', html, re.S):
        k = m.group(1).strip()
        v = re.sub(r'<[^>]+>', ' ', m.group(2))
        v = re.sub(r'\s+', ' ', v).strip()
        v = v.replace(' , ', ', ').replace(' ,', ',').strip()
        v = _unescape(v)
        if k and v:
            facts.append([k, v])

    # рейтинги: IMDb / Кинопоиск
    rating = {}
    for m in re.finditer(r'class="b-post__info_rates\s+([a-z]+)"[^>]*>.*?</a>:\s*<span class="bold">([\d.,]+)</span>', html, re.S):
        rating[m.group(1)] = m.group(2)

    # полное описание: b-post__description_text, fallback на og:description
    dm = re.search(r'class="b-post__description_text"[^>]*>(.*?)</div>', html, re.S)
    if dm:
        dtx = re.sub(r'<br\s*/?>', '\n', dm.group(1))
        dtx = re.sub(r'<[^>]+>', '', dtx)
        dtx = re.sub(r'[ \t]+', ' ', dtx).strip()
        dtx = _unescape(dtx)
        description = dtx
    else:
        description = desc.group(1) if desc else None

    # мета-строка под названием: год/страна/жанр из таблицы (новая разметка)
    if not meta_text and facts:
        meta_parts = []
        for k, v in facts:
            if k in (u'Дата выхода', u'Год выпуска', u'Страна', u'Жанр'):
                meta_parts.append(v)
        meta_text = ', '.join(meta_parts)
        meta_text = re.sub(r'\s*,\s*', ', ', meta_text).strip()

    idm = re.search(r'sof\.tv\.initCDN(?:Series|Movies)Events\((\d+)', html)
    post_id = int(idm.group(1)) if idm else None

    dtype = 'series' if 'CDNSeries' in html else ('movie' if 'MoviesEvents' in html else None)

    translators = parse_translators(html, dtype)
    active_tid = active_translator_id(html)
    if active_tid is None or not any(t['id'] == active_tid for t in translators):
        active_tid = translators[0]['id'] if translators else None

    result = {
        'id': post_id,
        'url': url,
        'title': re.sub(r'^(фильм|сериал|мультфильм|тв-шоу|аниме)\s+', '',
                    title.group(1).replace(u'Смотреть ', '').replace(u' онлайн бесплатно в хорошем качестве', '')) if title else url,
        'poster': og.group(1) if og else None,
        'description': description,
        'type': dtype,
        'meta': meta_text,
        'rating': rating,
        'facts': facts,
        'translators': [],
    }

    for tr in translators:
        tr_id = tr['id']
        is_active = tr_id == active_tid
        seasons, episodes, first_url = get_episodes(post_id, tr_id) if dtype == 'series' else ([], [], None)
        if dtype == 'series' and not episodes:
            if is_active:
                seasons, episodes = parse_seasons_episodes(html)[:2]
        tr_out = {'id': tr_id, 'name': tr['name'], 'active': is_active, 'seasons': []}

        if dtype == 'series':
            by_season = {}
            for ep in episodes:
                by_season.setdefault(ep['season'], []).append({'episode': ep['episode'], 'title': ep.get('title', ''), 'qualities': {}})
            for s in seasons:
                tr_out['seasons'].append({'season': s['season'], 'title': s.get('title', ''), 'episodes': by_season.get(s['season'], [])})
            for snum, eps in by_season.items():
                if snum not in [s['season'] for s in seasons]:
                    tr_out['seasons'].append({'season': snum, 'title': '', 'episodes': eps})
            tr_out['seasons'].sort(key=lambda x: x['season'])
            if with_streams and is_active:
                _fetch_qualities_pool(tr_out, post_id, tr_id)
        else:
            resp = api_get_cdn(post_id, tr_id, 'get_movie') if with_streams and is_active else {}
            tr_out['seasons'] = [{'season': 1, 'title': '', 'episodes': [{'episode': 1, 'title': '', 'qualities': parse_streams(resp.get('url')) if with_streams and is_active else {}}]}]

        result['translators'].append(tr_out)

    cache_set(cache_key, result)
    return result


# ---------- потоки сезона для любого перевода ----------
_SEASON_CACHE = {}


def get_season_qualities(url, post_id, tr_id, season):
    """Потоки всех серий одного сезона для ЛЮБОГО перевода (не только активного:
    в get_title качества фетчатся только активному, а сезон целиком нужен
    и для остальных). Кэш 1 час. Возвращает список
    [{'episode': N, 'qualities': {...}}, ...] или None."""
    key = (post_id, tr_id, season)
    now = time.time()
    c = _SEASON_CACHE.get(key)
    if c and now - c[0] < 3600:
        return c[1]
    t = get_title(url, with_streams=False)  # структура (кэш), потоки не нужны
    tr = next((x for x in t.get('translators', []) if x['id'] == tr_id), None)
    if tr is None:
        return None
    s = next((x for x in tr.get('seasons', []) if x['season'] == season), None)
    if s is None:
        return None
    view = {'seasons': [{'season': season, 'episodes': [
        {'episode': e['episode'], 'title': e.get('title', ''), 'qualities': {}} for e in s['episodes']]}]}
    if view['seasons'][0]['episodes']:
        _fetch_qualities_pool(view, post_id, tr_id)
    out = [{'episode': e['episode'], 'qualities': e['qualities']}
           for e in view['seasons'][0]['episodes']]
    _SEASON_CACHE[key] = (now, out)
    return out