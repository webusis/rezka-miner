# rezka.py — клиент к rezka-tv.org через node-агент (Anubis-обход).
import json
import re
import time
import urllib.request
import urllib.parse
import os
import hashlib

AGENT = 'http://127.0.0.1:9333/proxy'
BASE = 'https://rezka-tv.org'
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def proxy(url, method='GET', body=None, headers=None, timeout=120):
    payload = json.dumps({
        'url': url,
        'method': method,
        'body': body or None,
        'headers': headers or {},
    }).encode()
    req = urllib.request.Request(AGENT, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)['text']


def cache_get(key, ttl=3600):
    path = os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + '.json')
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < ttl:
            with open(path, encoding='utf-8') as f:
                return json.load(f)

def cache_set(key, data):
    path = os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def api_get_cdn(id, translator_id, action, season=None, episode=None):
    """Дёргает ajax/get_cdn_series."""
    t = int(time.time() * 1000)
    params = {'id': id, 'translator_id': translator_id, 'favs': '', 'action': action}
    if season is not None:
        params['season'] = season
    if episode is not None:
        params['episode'] = episode
    url = f'{BASE}/ajax/get_cdn_series/?t={t}'
    body = urllib.parse.urlencode(params)
    text = proxy(url, 'POST', body, {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'})
    try:
        return json.loads(text)
    except Exception:
        return {'error': 'bad json', 'raw': text[:300]}


def parse_streams(url_str):
    """'[360p]https://x.mp4,[480p]https://y.mp4' -> {'360p': url, ...}
    Премиум-качества (с prem-icon/html-разметкой) отбрасываются."""
    if not url_str:
        return {}
    out = {}
    for p in url_str.split(','):
        m = re.match(r'\[([^\]]+)\](https?://[^\s,]+)', p)
        if not m:
            continue
        q, u = m.group(1), m.group(2)
        # премиум-качества приходят с html-разметкой/иконкой — выкидываем
        if '<' in q or '>' in q or 'pjs-prem' in q or 'prem-icon' in q:
            continue
        out[q] = u
    return out


def search(q, limit=15):
    """Поиск: список карточек."""
    cache_key = f'search:{q}'
    cached = cache_get(cache_key, ttl=600)
    if cached:
        return cached
    url = f'{BASE}/search/?do=search&subaction=search&q={urllib.parse.quote(q)}'
    html = proxy(url)
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
    cache_set(cache_key, items)
    return items


def fetch_html(url):
    """HTML страницы тайтла (с кэшем)."""
    cache_key = f'html:{url}'
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
    for m in re.finditer(r'data-season_id="(\d+)"[^>]*>(?:<span[^>]*>)?([^<]*)', seasons_html):
        seasons.append({'season': int(m.group(1)), 'title': m.group(2).strip()})
    episodes = []
    for m in re.finditer(r'<[^>]+class="[^"]*b-simple_episode__item[^"]*"[^>]*data-season_id="(\d+)"[^>]*data-episode_id="(\d+)"[^>]*>(.*?)</', episodes_html, re.S):
        inner = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        episodes.append({'season': int(m.group(1)), 'episode': int(m.group(2)), 'title': inner})
    return seasons, episodes, resp.get('url')


def get_title(url, with_streams=True):
    """Полная структура тайтла: переводы, сезоны, серии, качества."""
    cache_key = f'title:{url}:streams={with_streams}'
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

    idm = re.search(r'sof\.tv\.initCDN(?:Series|Movies)Events\((\d+)', html)
    post_id = int(idm.group(1)) if idm else None

    dtype = 'series' if 'CDNSeries' in html else ('movie' if 'MoviesEvents' in html else None)

    translators = parse_translators(html, dtype)
    active_tid = active_translator_id(html)
    if active_tid is None or not any(t['id'] == active_tid for t in translators):
        # активный оказался премиум-переводом — берём первого бесплатного
        active_tid = translators[0]['id'] if translators else None

    result = {
        'id': post_id,
        'url': url,
        'title': title.group(1).replace('Смотреть ', '').replace(' онлайн бесплатно в хорошем качестве', '') if title else url,
        'poster': og.group(1) if og else None,
        'description': desc.group(1) if desc else None,
        'type': dtype,
        'meta': meta_text,
        'translators': [],
    }

    # Для каждого переводчика собираем сезоны/серии; ссылки — только у активного
    for tr in translators:
        tr_id = tr['id']
        is_active = tr_id == active_tid
        seasons, episodes, first_url = get_episodes(post_id, tr_id) if dtype == 'series' else ([], [], None)
        if dtype == 'series' and not episodes:
            # fallback: серии прямо из HTML (активный перевод)
            if is_active:
                seasons, episodes = parse_seasons_episodes(html)[:2]
        tr_out = {'id': tr_id, 'name': tr['name'], 'active': is_active, 'seasons': []}

        if dtype == 'series':
            # группируем серии по сезонам
            by_season = {}
            for ep in episodes:
                by_season.setdefault(ep['season'], []).append({'episode': ep['episode'], 'title': ep.get('title', ''), 'qualities': {}})
            for s in seasons:
                tr_out['seasons'].append({'season': s['season'], 'title': s.get('title', ''), 'episodes': by_season.get(s['season'], [])})
            # сезоны без серий в списке
            for snum, eps in by_season.items():
                if snum not in [s['season'] for s in seasons]:
                    tr_out['seasons'].append({'season': snum, 'title': '', 'episodes': eps})
            tr_out['seasons'].sort(key=lambda x: x['season'])
            # ссылки на серии — только для активного перевода
            if with_streams and is_active:
                for s in tr_out['seasons']:
                    for ep in s['episodes']:
                        resp = api_get_cdn(post_id, tr_id, 'get_stream', season=s['season'], episode=ep['episode'])
                        ep['qualities'] = parse_streams(resp.get('url'))
                        time.sleep(0.15)
        else:
            # фильм: одна "серия" с качествами
            resp = api_get_cdn(post_id, tr_id, 'get_movie') if with_streams and is_active else {}
            tr_out['seasons'] = [{'season': 1, 'title': '', 'episodes': [{'episode': 1, 'title': '', 'qualities': parse_streams(resp.get('url')) if with_streams and is_active else {}}]}]

        result['translators'].append(tr_out)

    cache_set(cache_key, result)
    return result