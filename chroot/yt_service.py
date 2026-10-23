#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точка входа ютуба для Rezka (ветка youtube).
Живёт в Debian-chroot планшета (python3.11), слушает 127.0.0.1:8081.
python2-сервер (RezkaServer.apk) проксирует /api/yt/* на этот порт.

Ленты (поиск/реки/подписки/каналы) — YouTube Data API v3
(oauth.json, scope youtube.readonly).
Стрим — yt-dlp, он же мёржит dash своим ffmpeg в mpegts (склейку
гоняет yt-dlp, это нормально; yt-dlp НЕ для получения ссылок).

Эндпоинты (формат ответов — как у rezka-miner/server.py):
  GET /api/yt/search?q=...          -> {"results": [{title, meta, poster, type, url}]}
  GET /api/yt/recs                  -> то же (темы + популярное)
  GET /api/yt/subs                  -> то же (подписки из аккаунта)
  GET /api/yt/channel?cid=UC...|@...-> то же (последние видео канала)
  GET /api/yt/stream/v.ts?vid=&h=   -> живой mpegts (yt-dlp + ffmpeg-склейка)

Запуск (внутри chroot, из папки rezka-yt):
  nohup python3 /home/tema/rezka-yt/yt_service.py > /home/tema/rezka-yt/yt_service.log 2>&1 &
Все файлы ютуба — в /home/tema/rezka-yt/ (без хлама в /home/tema).
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import concurrent.futures
import re
import xml.etree.ElementTree as ET

HOST = '127.0.0.1'
PORT = 8081
YTDLP = '/usr/local/bin/yt-dlp'  # стрим: mpegts-склейка (не для ссылок)

OAUTH_FILE = '/home/tema/rezka-yt/oauth.json'
# {client_id, client_secret, refresh_token} — от аккаунта с youtube.readonly.
_tok_cache = None  # (access_token, expiry_ts)

COOKIES_FILE = '/home/tema/rezka-yt/cookies.txt'
# Netscape cookies залогиненного аккаунта (Cookie-Editor) — для персонального
# фида рекомендаций /feed/recommended. Протухли? Переэкспортировать сюда.

RECS_TOPICS = [
    'металл rock 80-90',
    'боевик фантастика 90-х',
    'кино обзор',
    'музыка 2026',
    'лучшие клипы 80-х',
]

_recs_lock = threading.Lock()
_recs_state = {'ts': 0.0, 'cards': [], 'busy': False}
_RECS_TTL = 180.0  # фид обновляется постоянно — перетаскиваем каждые 3 мин в фоне

# --- Главная из каналов: свежие видео по RSS (без API-квоты) ---
HOME_CHANNELS = [
    'kuplinovplay', 'dmitri.potapov', 'bes',
    'kingstonmyles', 'Нарратор', 'amway921wot',
    'podval4ikshow', 'overwatchru', 'funmode',
    'danyakraster', 'radiotapok', 'artem_3bepbko',
    'lollydragon1882', 'alinarin', 'ЗовитеПронину',
    'valerian89', 'minynaranja', 'takostro',
    'oleg_kimm', 'thejoves', 'alliam',
    'masterskayanastroeny', 'mityayset', 'studioctv',
    'kinohub_films_and_series', 'saturdaynightlive', 'rimpac',
    'sergoff_m', 'maxmaximov86', 'perpetuumworld',
    'sledovatelgs', 'metalscorpua', 'shimoroshow',
    'mrmarmok', 'pushnoyru', 'johan59',
    'amitesh', 'cursedlinuxuser', 'oblomoffood',
    'ozvu4enomedoedom', 'kvn', 'ladyleo',
    'stopgameru', 'zhizn_anonima', 'pozivnayakomedia',
    'maxim.shelkov', 'eisbrecherofficial', 'obsidiantime',
    'мусорщик-виктор', 'zakatoon', 'yakovlevmisha',
    'vsiserii', 'ovsyankaai', 'furrydev2007',
    'valeraghosther', 'remont-noutbukov', 'dinara_kurbanova',
    'oldovoetv', 'paranoidfantom', 'margaret_wolf',
    'zombiechezz', 'vomgle', 'deeem_v',
    'valentrye', 'johnny_half', 'konduktor72',
    'alemorf', 'alineinwonderland', 'dominickrow',
    'feliks-ks-ks', 'ptmovies-official', 'dobryak',
    'yashnikova', 'yuritheprofessional', 'lankarra_s',
    'codewizer', 'doctordiy', 't1000-k',
    'ШОСПк', 'vasyanasene', 'solid-show',
    'olegyafizov', 'epic.fighting', 'oblomoffstuff',
    'ktkv', 'englishantischool', 'kvashenaya',
    'alexburkan', 'alcobard', 'shoptitans',
    'rapanacondaz', 'zavozin', 'aliseonoc',
    'buldjat', 'russmosh', 'filmsterru',
    'spoontamer', 'alisa_supernova', 'image_game',
    'kinamaniachannel', 'АУКЦИОНконтейнеров', 'morgensternlive',
    'pinkbutterflyman', 'marmoklive', 'golosvasi',
    'ТатьянаКамазистка', 'rusm9snik', 'ЦУЕФА-н4к',
    'ВЫНОСмозга', 'obeziana', 'АлександрЛи-я5ъ',
    'howdyhonet', 'vanzai', 'toplesofficial',
    'webgirlkristina', 'plamenev', '-roadtofilm.1351',
    'dfishers', 'overbafer1', 'kitayg1',
    'clustermeerkat', 'prosunduk', 'kuplinov',
    'dubrovskiy-syndicate', 'mishayakovl', 'alinagingertail',
    'academeg2ndch', 'academegdailystream', 'yafantom',
    'optimisster', 'insanespacemuffin', 'enjoykin',
    'colinfurze', 'mrellgin', 'unclemcelroy',
    'roomfactoryy', 'cloudiam', 'academeg',
    'daifivetop', 'saspens', 'eugenesagaz',
    'kisimiak', 'igromaniavideo', 'drrojashow',
    'mobofilka', 'letsplayporusski', 'opencode',
]

_CHAN_IDS_FILE = '/home/tema/rezka-yt/channel_ids.json'
_CHAN_TTL = 1800.0    # лента каналов обновляется раз в 30 минут
_CHAN_PER = 3         # не больше 3 свежих видео с канала — чтобы один не забивал ленту
_CHAN_UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120 Safari/537.36')
_chan_lock = threading.Lock()
_chan_state = {'ts': 0.0, 'cards': [], 'busy': False}


def _http_get(url, timeout=25, tries=3):
    """GET с ретраями: у планшета DNS отваливается при пачке параллельных запросов."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': _CHAN_UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


def _load_chan_ids():
    try:
        with open(_CHAN_IDS_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_chan_ids(d):
    try:
        with open(_CHAN_IDS_FILE, 'w') as f:
            json.dump(d, f, ensure_ascii=False, indent=0)
    except Exception as e:
        sys.stderr.write('chan ids save: %s\n' % e)


def _resolve_one(handle):
    """@handle -> UCxxxxxx (со страницы канала, без Data API и кук)."""
    try:
        url = 'https://www.youtube.com/@' + urllib.parse.quote(handle)
        html = _http_get(url).decode('utf-8', 'replace')
    except Exception as e:
        sys.stderr.write('chan resolve %s: %s\n' % (handle, e))
        return None
    m = (re.search(r'channel_id=(UC[A-Za-z0-9_-]{22})', html)
         or re.search(r'"channelId":"(UC[A-Za-z0-9_-]{22})"', html))
    return m.group(1) if m else None


def _resolve_channels():
    """handle -> channel_id, кэш в файле: резолвим один раз, дальше только RSS."""
    ids = _load_chan_ids()
    missing = [h for h in HOME_CHANNELS if not ids.get(h)]
    if missing:
        sys.stderr.write('chan resolve: %d каналов...\n' % len(missing))
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            for h, cid in zip(missing, ex.map(_resolve_one, missing)):
                if cid:
                    ids[h] = cid
        _save_chan_ids(ids)
    got = [ids[h] for h in HOME_CHANNELS if ids.get(h)]
    sys.stderr.write('chan resolve: %d/%d ок\n' % (len(got), len(HOME_CHANNELS)))
    return got


def _feed_cards(cid):
    """Свежие видео канала из Atom-RSS."""
    try:
        xml = _http_get('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid)
        root = ET.fromstring(xml)
    except Exception as e:
        sys.stderr.write('rss %s: %s\n' % (cid, e))
        return []
    ns = {'a': 'http://www.w3.org/2005/Atom',
          'yt': 'http://www.youtube.com/xml/schemas/2015'}
    ch = root.findtext('a:title', default='', namespaces=ns) or ''
    out = []
    for e in root.findall('a:entry', ns)[:_CHAN_PER]:
        vid = e.findtext('yt:videoId', default='', namespaces=ns) or ''
        if len(vid) != 11:
            continue
        pub = e.findtext('a:published', default='', namespaces=ns) or ''
        out.append((pub, {
            'title': e.findtext('a:title', default='', namespaces=ns) or '',
            'meta': ch,
            'poster': _thumb(vid),
            'type': 'YT',
            'url': 'yt:' + vid,
        }))
    return out


def recs_from_channels():
    """Лента главной: свежие видео со всех HOME_CHANNELS, отсортированные по дате."""
    ids = _resolve_channels()
    if not ids:
        return []
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for part in ex.map(_feed_cards, ids):
            rows.extend(part)
    rows.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in rows]


def _chan_worker():
    try:
        cards = recs_from_channels()
        with _chan_lock:
            _chan_state['cards'] = cards
            _chan_state['ts'] = time.time()
            _chan_state['busy'] = False
        sys.stderr.write('chan feed: %d карточек\n' % len(cards))
    except Exception as e:
        sys.stderr.write('chan feed: %s\n' % e)
        with _chan_lock:
            _chan_state['busy'] = False


def recs():
    """Главная: лента из HOME_CHANNELS. Пока не готова — отдаём старый путь
    (персональный фид/темы), а свежую собираем в фоне."""
    with _chan_lock:
        cards = list(_chan_state['cards'])
        ts, busy = _chan_state['ts'], _chan_state['busy']
    if cards:
        if not busy and time.time() - ts > _CHAN_TTL:
            with _chan_lock:
                _chan_state['busy'] = True
            threading.Thread(target=_chan_worker, daemon=True).start()
        return cards
    if not busy:
        with _chan_lock:
            _chan_state['busy'] = True
        threading.Thread(target=_chan_worker, daemon=True).start()
    return _recs_legacy()


def _thumb(entry_id):
    return 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % entry_id


def _api(path):
    """GET к YouTube Data API v3 с bearer-токеном. None на любой ошибке."""
    tok = _access_token()
    if not tok:
        return None
    url = 'https://www.googleapis.com/youtube/v3/' + path
    try:
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        sys.stderr.write('youtube api %s: %s\n' % (path[:50], e))
        return None


def _thumb_from_sn(sn):
    th = sn.get('thumbnails') or {}
    pic = th.get('medium') or th.get('high') or th.get('default') or {}
    return pic.get('url', '')


def _cards_from_v3(items):
    """items YouTube API (search/playlistItems/videos) -> карточки резки."""
    out = []
    for it in items or []:
        sn = it.get('snippet') or {}
        # playlistItems: настоящий videoId живёт в snippet.resourceId,
        # а в id — base64 'плейлист.видео' (мусор для нас).
        rid = sn.get('resourceId') or {}
        vid = rid.get('videoId') or rid.get('playlistId')
        if not vid:
            iid = it.get('id')
            if isinstance(iid, dict):
                vid = iid.get('videoId') or iid.get('playlistId')
            elif isinstance(iid, str):
                vid = iid
        if not vid or not isinstance(vid, str):
            continue
        out.append({
            'title': sn.get('title', ''),
            'meta': sn.get('channelTitle', ''),
            'poster': _thumb_from_sn(sn),
            'type': 'YT',
            'url': 'yt:' + vid,
        })
    return out


def search(q):
    q = urllib.parse.quote((q or '').strip())
    if not q:
        return []
    d = _api('search?part=snippet&type=video&maxResults=25&q=' + q)
    if d is None:
        return [{'title': 'yt: API недоступен', 'meta': '', 'poster': '',
                 'type': 'YT', 'url': ''}]
    return _cards_from_v3(d.get('items'))


def recs_from_api():
    """Фолбэк: темы + топ региона через официальный API."""
    out = []
    seen = set()
    for t in RECS_TOPICS:
        d = _api('search?part=snippet&type=video&maxResults=8&q=' +
                 urllib.parse.quote(t))
        for c in _cards_from_v3(d.get('items') if d else []):
            if c['url'] and c['url'] not in seen:
                seen.add(c['url'])
                out.append(c)
    d = _api('videos?part=snippet&chart=mostPopular&maxResults=8&regionCode=BY')
    for c in _cards_from_v3(d.get('items') if d else []):
        if c['url'] and c['url'] not in seen:
            seen.add(c['url'])
            out.append(c)
    return out


def yt_cookies_file():
    """Путь к КОПИИ кук для вызовов yt-dlp (--cookies).
    yt-dlp при --cookies перезаписывает файл куками своей сессии — мастер
    с экспортированными куками через копию, чтобы не рассинхронизировать.
    Одна копия на процесс, обновляется из мастера при каждом вызове."""
    ck = '/tmp/yt_cookies_%d.txt' % os.getpid()
    try:
        with open(COOKIES_FILE, 'rb') as f:
            data = f.read()
        with open(ck, 'wb') as f:
            f.write(data)
        os.chmod(ck, 0o600)
        return ck
    except Exception as e:
        sys.stderr.write('куки: копия не удалась, мастер как фолбэк: %s\n' % e)
        return COOKIES_FILE


def recs_from_feed():
    """Персональные рекомендации: главная аккаунта через yt-dlp + cookies.
    --flat-playlist: берём карточки из фида, не резолвя каждое видео.
    ВАЖНО: yt-dlp при --cookies ПЕРЕЗАПИСЫВАЕТ файл куками своей сессии —
    мастер-файл с экспортированными куками отдаём через КОПИЮ, иначе
    после пары обновлений (TTL-фон) набор рассинхронизируется и YouTube
    перестаёт его принимать (рекомендации слетают в фолбэк по темам)."""
    ck = yt_cookies_file()
    cmd = [YTDLP, '--no-warnings', '--flat-playlist', '--playlist-end', '25',
           '--cookies', ck, '-J',
           'https://www.youtube.com/feed/recommended']
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=110)
    except Exception as e:
        sys.stderr.write('recs feed: %s\n' % e)
        return []
    if p.returncode != 0:
        sys.stderr.write('recs feed rc!=0: %s\n' %
                         (p.stderr or b'').decode('utf-8', 'replace')[-200:])
        return []
    try:
        d = json.loads(p.stdout.decode('utf-8', 'replace'))
    except Exception:
        return []
    out = []
    for e in d.get('entries') or []:
        if not e:
            continue
        vid = e.get('id') or ''
        if len(vid) != 11 or not vid.isalnum():
            continue
        out.append({
            'title': e.get('title', ''),
            'meta': e.get('channel') or '',
            'poster': _thumb(vid),
            'type': 'YT',
            'url': 'yt:' + vid,
        })
    if not out:
        sys.stderr.write('recs feed: пустой фид (куки не приняты?) — фолбэк на темы\n')
    return out


def _recs_load():
    """Тянет свежие карточки (фид → фолбэк API) и сохраняет. Фон/первый раз."""
    global _recs_state
    cards = recs_from_feed()
    if not cards:
        cards = recs_from_api()
    with _recs_lock:
        _recs_state['cards'] = cards
        _recs_state['ts'] = time.time()
        _recs_state['busy'] = False


def _recs_legacy():
    """Главная: отдаём последний фид мгновенно, обновление — в фоне.
    Первый раз после старта грузим синхронно (главная не пустая)."""
    global _recs_state
    with _recs_lock:
        cards = list(_recs_state['cards'])
        ts, busy = _recs_state['ts'], _recs_state['busy']
    if not cards and not busy:
        with _recs_lock:
            _recs_state['busy'] = True
        _recs_load()
        with _recs_lock:
            return _recs_state['cards']
    if not busy and time.time() - ts > _RECS_TTL:
        with _recs_lock:
            _recs_state['busy'] = True
        threading.Thread(target=_recs_load, daemon=True).start()
    return cards


def _access_token():
    """Свежий access_token (refresh по oauth.json), кэш в памяти."""
    global _tok_cache
    t = _tok_cache
    if t and t[1] > time.time() + 300:
        return t[0]
    if not os.path.exists(OAUTH_FILE):
        return None
    try:
        with open(OAUTH_FILE) as f:
            c = json.load(f)
        data = urllib.parse.urlencode({
            'client_id': c['client_id'],
            'client_secret': c['client_secret'],
            'refresh_token': c['refresh_token'],
            'grant_type': 'refresh_token',
        }).encode('utf-8')
        req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        sys.stderr.write('oauth refresh failed: %s\n' % e)
        return None
    tok = d.get('access_token')
    if not tok:
        return None
    exp = int(d.get('expires_in', 3600))
    _tok_cache = (tok, time.time() + exp)
    return tok


def subs_from_api():
    """Реальные подписки аккаунта через YouTube Data API v3."""
    tok = _access_token()
    if not tok:
        return None
    url = ('https://www.googleapis.com/youtube/v3/subscriptions'
           '?part=snippet&mine=true&maxResults=50')
    try:
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:
        sys.stderr.write('subs api failed: %s\n' % e)
        return None
    out = []
    for it in d.get('items') or []:
        sn = it.get('snippet') or {}
        rid = sn.get('resourceId') or {}
        cid = rid.get('channelId')
        if not cid:
            continue
        th = sn.get('thumbnails') or {}
        pic = th.get('medium') or th.get('default') or {}
        out.append({
            'title': sn.get('title', ''),
            'meta': 'подписка',
            'poster': pic.get('url', ''),
            'type': 'канал',
            'url': 'chan:' + cid,
        })
    return out


def load_subs():
    """Подписки — только из аккаунта через API (файла-фолбэка нет)."""
    cards = subs_from_api()
    if cards is None:
        return [{'title': 'yt: API недоступен', 'meta': '', 'poster': '',
                 'type': 'канал', 'url': ''}]
    return cards


def channel_videos(cid):
    """Канал: последние видео через uploads-плейлист (UU + id без UC)."""
    cid = (cid or '').strip()
    if cid.startswith('@'):
        # handle -> канал
        d = _api('channels?part=snippet&forHandle=' + urllib.parse.quote(cid[1:]))
        if not d or not d.get('items'):
            return [{'title': 'yt: канал не найден', 'meta': '', 'poster': '',
                     'type': 'YT', 'url': ''}]
        cid = d['items'][0]['id']
    if cid.startswith('UC'):
        pid = 'UU' + cid[2:]
    elif cid.startswith('UU'):
        pid = cid
    else:
        return [{'title': 'yt: неверный id канала', 'meta': '', 'poster': '',
                 'type': 'YT', 'url': ''}]
    d = _api('playlistItems?part=snippet&maxResults=25&playlistId=' + pid)
    if d is None:
        return [{'title': 'yt: API недоступен', 'meta': '', 'poster': '',
                 'type': 'YT', 'url': ''}]
    return _cards_from_v3(d.get('items'))


# ---------------------------------------------------------------------------
# Стрим: python качает dash (135 video + 140 audio) по Range, кормит ffmpeg
# через два fifo, ffmpeg mux'ит в mpegts. Перемотка: по Range-запросу плеера
# стартуем с моофа на нужной секунде (видео — офсеты из sidx + поиск маркера
# 'moof', аудио — пропорция размера по времени), PTS идут с нужной секунды.
# ffmpeg-сеть в chroot сломана — поэтому только локальные входы (fifo).
# Проверено на планшете: init + середина (мооф#600) через два fifo -> mpegts.
# ---------------------------------------------------------------------------

META_CACHE = {}          # vid -> (ts, meta)
_META_TTL = 600.0        # 10 мин: срок жизни прямой googlevideo-ссылки ~6 ч
FFMPEG = 'ffmpeg'


def _rget(url, rng=None, timeout=120):
    """GET с необязательным Range. Возвращает открытый response (читай/закрой)."""
    hdrs = {'User-Agent': 'Mozilla/5.0'}
    if rng:
        hdrs['Range'] = rng
    return urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=timeout)


def _sel(height):
    if height > 720:
        height = 720
    if height >= 720:
        return 'bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]/b[height<=720]'
    return ('bv*[vcodec^=avc1][height=480]+ba[ext=m4a]'
            '/bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]'
            '/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]'
            '/b[height<=720]')


def _boxes(data):
    """[(off, typ, size)] — плоский список боксов в data (до первого обрыва)."""
    out = []
    off = 0
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off + 4], 'big')
        typ = data[off + 4:off + 8]
        if size == 1:
            size = int.from_bytes(data[off + 8:off + 16], 'big')
            hdr = 16
        else:
            hdr = 8
        if size < hdr or off + size > len(data):
            break
        out.append((off, typ, size))
        off += size
    return out


def _sidx_end(data):
    """Индекс конца бокса sidx (или None). init без sidx не бывает у ютуба."""
    for off, typ, size in _boxes(data):
        if typ == b'sidx':
            return off + size
    return None


def _sidx_refs(data):
    """[(pts_sec, off)] из sidx. Офсеты могут быть со сдвигом ±init — в проде
    реальный старт уточняется поиском маркера 'moof' в буфере (_moof_off)."""
    for off, typ, size in _boxes(data):
        if typ != b'sidx':
            continue
        b = data[off + 8:off + size]
        if len(b) < 24:
            return []
        ver = b[0]
        timescale = int.from_bytes(b[8:12], 'big') or 1
        if ver == 0:
            earliest = int.from_bytes(b[12:16], 'big')
            first_off = int.from_bytes(b[16:20], 'big')
            refs = int.from_bytes(b[22:24], 'big')
            p = 24
        else:
            earliest = int.from_bytes(b[12:20], 'big')
            first_off = int.from_bytes(b[20:28], 'big')
            refs = int.from_bytes(b[30:32], 'big')
            p = 32
        base = off + size + first_off
        pts = earliest
        subs = []
        for _ in range(refs):
            if p + 12 > len(b):
                break
            rsz = int.from_bytes(b[p + 1:p + 4], 'big')
            d = int.from_bytes(b[p + 4:p + 8], 'big')
            subs.append((pts / timescale, base))
            pts += d
            base += rsz
            p += 12
        return subs
    return []


def _pick_ref(refs, t):
    """Последний реф с pts <= t (+2с допуск)."""
    best = refs[0]
    for r in refs:
        if r[0] <= t + 2:
            best = r
        else:
            break
    return best


def _moof_off(url, probe):
    """Точный байт начала моофа в потоке url вблизи probe.
    Качаем 128КБ от (probe-64К), ищем маркер 'moof', берём позицию-4."""
    if probe <= 0:
        return None
    start = max(0, probe - 65536)
    try:
        r = _rget(url, 'bytes=%d-%d' % (start, start + 131071), timeout=90)
        data = r.read()
        r.close()
    except Exception:
        return probe
    i = data.find(b'moof')
    if i < 4:
        return probe
    return max(0, start + i - 4)


def _sel_single(height):
    """Строго один поток: mp4 с видеорядом И звуком в одном файле
    (itag 22/18/59...). YouTube почти не отдаёт такие — когда есть,
    стримим файл напрямую, ffmpeg не участвует."""
    if height > 720:
        height = 720
    return ('b[height<=%d][ext=mp4][vcodec^=avc1][acodec]'
            '/b[height<=%d][ext=mp4][vcodec]'
            '/b[height<=%d][ext=mp4]'
            '/b[height<=%d]') % (height, height, height, height)


def _yt_meta(vid, height):
    """Мета для стрима строго одним потоком: прогрессивный mp4 (видео+аудио
    в одном файле). Прямая ссылка googlevideo, размер, длительность. Кэш 10 мин.
    None — однопоточного формата нет (никаких склеек и ffmpeg)."""
    now = time.time()
    c = META_CACHE.get(vid)
    if c and now - c[0] < _META_TTL:
        return c[1]
    url = 'https://www.youtube.com/watch?v=' + (vid or '')
    try:
        p = subprocess.run([YTDLP, '--no-warnings', '-J', '-f', _sel_single(height), url],
                           capture_output=True, timeout=120)
        if p.returncode != 0:
            return None
        d = json.loads(p.stdout.decode('utf-8', 'replace'))
    except Exception:
        return None
    if d.get('requested_formats'):
        return None  # dash-раздельные (видео + аудио по отдельности) — не наше
    ac = (d.get('acodec') or 'none').lower()
    vc = (d.get('vcodec') or 'none').lower()
    if ac == 'none' or vc == 'none':
        return None
    if (d.get('ext') or '') != 'mp4':
        return None
    vurl = d.get('url')
    if not vurl:
        return None
    size = d.get('filesize') or d.get('filesize_approx') or 0
    dur = float(d.get('duration') or 0)
    if not size or dur <= 0:
        return None
    m = {'prog': True, 'vurl': vurl, 'total': int(size), 'dur': dur,
         'itag': d.get('format_id'), 'res': d.get('resolution')}
    META_CACHE[vid] = (now, m)
    return m


# ===== DASH-MPD для ExoPlayer (схема SmartTube: SegmentBase + indexRangeExact) =====

J_CACHE = {}  # vid -> (ts, info-json от yt-dlp -J)
_MPD_NS = 'urn:mpeg:dash:schema:mpd:2011'
_MPD_PROFILE = 'urn:mpeg:dash:profile:isoff-on-demand:2011'
# По-хорошему — isinstance, но import только здесь чтоб не трогать шапку
import xml.sax.saxutils as _xesc


def _yt_info(vid):
    """Сырой yt-dlp -J по видео (все форматы). Кэш по vid, TTL как у меты."""
    now = time.time()
    c = J_CACHE.get(vid)
    if c and now - c[0] < _META_TTL:
        return c[1]
    url = 'https://www.youtube.com/watch?v=' + (vid or '')
    d = None
    # Сначала штатные клиенты; android — только фолбэк (детский/ограниченный контент,
    # где обычно падает visionos). В комбинации 'default,android' дефолт теряется,
    # поэтому пробуем по очереди.
    for extra in ([], ['--extractor-args', 'youtube:player_client=android']):
        try:
            p = subprocess.run([YTDLP, '--no-warnings'] + extra + ['-J', url],
                               capture_output=True, timeout=120)
            if p.returncode != 0:
                continue
            d = json.loads(p.stdout.decode('utf-8', 'replace'))
            break
        except Exception:
            continue
    if d is None:
        return None
    J_CACHE[vid] = (now, d)
    return d


def _rng(v):
    """indexRange/initRange: '1000-1309' | [1000, 1309] | None -> 'a-b' или ''."""
    if not v:
        return ''
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return '%d-%d' % (v[0], v[1])
    s = str(v)
    return s if '-' in s else ''


_SIDX_CACHE = {}  # url -> (ts, 'start-end')

def _sidx_range(url):
    """indexRange бокса sidx в dash-файле: качаем голову (64КБ), ищем бокс.
    yt-dlp свежий index_range не отдаёт — берём из файла, как в склейке."""
    now = time.time()
    c = _SIDX_CACHE.get(url)
    if c and now - c[0] < _META_TTL:
        return c[1]
    try:
        r = _rget(url, 'bytes=0-65535', timeout=60)
        data = r.read()
        r.close()
    except Exception:
        return None
    pos = 0
    n = len(data)
    off = size = None
    while pos + 8 <= n:
        sz = int.from_bytes(data[pos:pos + 4], 'big')
        typ = data[pos + 4:pos + 8]
        if typ == b'sidx':
            off, size = pos, sz
            break
        if sz < 8:
            break
        pos += sz
    if off is None:
        return None
    rng = '%d-%d' % (off, off + size - 1)
    _SIDX_CACHE[url] = (now, rng)
    return rng


def _aber(f):
    """bandwidth: битрейт в бит/с (fallback 1 Мбит)."""
    tbr = f.get('tbr') or 0
    abr = f.get('abr') or 0
    vbr = f.get('vbr') or 0
    bw = tbr or max(abr, vbr) or 1000
    return int(bw * 1000)


def _audio_rank(f):
    """Приоритет аудиодорожки: оригинал (format_note «default») > русская > abr."""
    note = (f.get('format_note') or '').lower()
    lang = (f.get('language') or '').lower()
    return (1 if 'default' in note else 0,
            1 if lang.startswith('ru') else 0,
            f.get('abr') or 0)


def _yt_qualities(d):
    """Доступные качества. Если есть раздельные потоки (video-only + audio-only) —
    отдаём их как DASH; иначе — прогрессивные (muxed) mp4 как fallback.
    -> [{'h','fps','itag','label','kind'}] от лучшей к худшей."""
    vidh = {}
    prog = {}
    has_aud = False
    for f in d.get('formats') or []:
        vc = (f.get('vcodec') or 'none').lower()
        ac = (f.get('acodec') or 'none').lower()
        ext = (f.get('ext') or '').lower()
        u = f.get('url') or ''
        if not u or 'manifest' in u or 'hls' in u:
            continue
        hgt = f.get('height') or 0
        if vc.startswith('avc1') and ac == 'none' and ext == 'mp4' and hgt > 0:
            cur = vidh.get(hgt)
            if cur is None or (f.get('vbr') or 0) > (cur.get('vbr') or 0):
                vidh[hgt] = f
        elif ac.startswith('mp4a') and vc == 'none' and ext in ('m4a', 'mp4'):
            has_aud = True
        elif vc.startswith('avc1') and ac.startswith('mp4a') and ext == 'mp4' and hgt > 0:
            cur = prog.get(hgt)
            if cur is None or (f.get('tbr') or 0) > (cur.get('tbr') or 0):
                prog[hgt] = f
    dash = bool(vidh and has_aud)
    src = vidh if dash else prog
    kind = 'dash' if dash else 'prog'
    out = []
    for hgt in sorted(src, reverse=True):
        f = src[hgt]
        fps = int(f.get('fps') or 30)
        w = f.get('width') or 0
        # Портретные ролики (шортсы) меряем по меньшей стороне, как YouTube:
        # иначе 1080x1920 подписывается как «1920p».
        short = min(w, hgt) if w else hgt
        label = '%dp' % short
        if fps >= 50:
            label += '%d' % fps
        out.append({'h': hgt, 'fps': fps, 'itag': str(f.get('format_id') or ''),
                    'label': label, 'kind': kind})
    return out


def _yt_prog(vid, height):
    """Прогрессивный (muxed avc1+aac) mp4 — для роликов без раздельных потоков."""
    d = _yt_info(vid)
    if not d:
        return None, 'yt-dlp не отдал инфо'
    best = None
    for f in d.get('formats') or []:
        vc = (f.get('vcodec') or 'none').lower()
        ac = (f.get('acodec') or 'none').lower()
        if not vc.startswith('avc1') or not ac.startswith('mp4a'):
            continue
        if (f.get('ext') or '') != 'mp4':
            continue
        u = f.get('url') or ''
        if not u or 'manifest' in u or 'hls' in u:
            continue
        hgt = f.get('height') or 0
        if hgt <= 0 or hgt > height:
            continue
        if best is None or hgt > (best.get('height') or 0):
            best = f
    if best is None:
        return None, 'нет прогрессивного mp4'
    return {'url': best['url'], 'itag': str(best.get('format_id') or ''),
            'height': best.get('height') or 0,
            'label': '%dp' % (best.get('height') or 0)}, None


def _yt_mpd(vid, height):
    """DASH-манифест видео+аудио (как у SmartTube): плеер сам мёржит дорожки,
    ffmpeg не участвует. Возвращает (mpd_str, None) или (None, err)."""
    d = _yt_info(vid)
    if not d:
        return None, 'yt-dlp не отдал инфо'
    dur = float(d.get('duration') or 0)
    fmt = d.get('formats') or []

    # видео: mp4 + avc1 (h264), высота <= запрошенной, не выше 720у
    vids = {}
    for f in fmt:
        vc = (f.get('vcodec') or 'none').lower()
        if vc == 'none' or not vc.startswith('avc1'):
            continue
        if (f.get('acodec') or 'none').lower() != 'none':
            continue  # muxed (напр. itag 18) не годится: нужен фрагментированный видеопоток
        if (f.get('ext') or '') != 'mp4':
            continue
        hgt = f.get('height') or 0
        if hgt <= 0 or hgt > height:
            continue
        u = f.get('url') or ''
        if not u:
            continue
        if 'manifest' in u or 'hls' in u:
            # новый sabr/HLS-контейнер (269/229/311...) — нам нужен
            # прямой fMP4 (160/133/134/298...), иначе sidx не достать
            continue
        # лучшее на каждую высоту (по vbr)
        cur = vids.get(hgt)
        if cur is None or (f.get('vbr') or 0) > (cur.get('vbr') or 0):
            vids[hgt] = f

    # аудио: mp4/m4a + aac (mp4a.*) — ExoPlayer без ffmpeg-декодера тянет aac;
    # opus/vorbis в webm не берём (нет нативного декодера на старом планшете).
    # ВАЖНО: у мультиязычных роликов YouTube отдаёт НЕСКОЛЬКО aac-дорожек
    # одного кодека (напр. 140-0 en-US и 140-1 ru). Раньше брали первую —
    # и на «Куплинове» играл английский автодубляж. Теперь берём оригинал:
    # в format_note он помечен «(default)», иначе — русскую, иначе по abr.
    aud_best = None
    for f in fmt:
        ac = (f.get('acodec') or 'none').lower()
        if ac == 'none' or not ac.startswith('mp4a'):
            continue
        if (f.get('vcodec') or 'none').lower() != 'none':
            continue  # только audio-only (muxed mp4 не берём)
        if (f.get('ext') or '') not in ('m4a', 'mp4'):
            continue
        if not f.get('url'):
            continue
        if aud_best is None or _audio_rank(f) > _audio_rank(aud_best):
            aud_best = f
    auds = {}
    if aud_best is not None:
        auds[(aud_best.get('acodec') or 'mp4a.40.2').lower()] = aud_best

    if not vids:
        return None, 'dash-видео (mp4/avc1) не найдено'
    if not auds:
        return None, 'dash-аудио (aac/m4a) не найдено'

    esc = _xesc.escape
    x = ['<?xml version="1.0" encoding="UTF-8"?>']
    x.append('<MPD xmlns="%s" profiles="%s" type="static" '
             'mediaPresentationDuration="PT%.2fS" minBufferTime="PT1.5S">'
             % (_MPD_NS, _MPD_PROFILE, dur))

    # видео-адаптации: от лучшей высоты к худшей (720 -> 360)
    # ВАЖНО: AdaptationSet@id по DASH — unsignedInt, ExoPlayer парсит его как int.
    x.append('  <Period>')
    sid = 0
    for hgt in sorted(vids, reverse=True):
        f = vids[hgt]
        ir = _sidx_range(f['url'])
        if not ir:
            continue  # sidx не нашли — без indexRange dash не отдаём
        sid += 1
        vc = f.get('vcodec') or 'avc1'
        fps = f.get('fps') or 30
        x.append('    <AdaptationSet id="%d" mimeType="video/mp4" codecs="%s" '
                 'width="%d" height="%d" frameRate="%d" segmentAlignment="true" '
                 'startWithSAP="1">' % (sid, esc(vc), f.get('width') or 0, hgt, fps))
        x.append('      <Representation id="%s" bandwidth="%d">'
                 % (esc(f.get('format_id') or 'v%d' % hgt), _aber(f)))
        x.append('        <BaseURL>%s</BaseURL>' % esc(f['url']))
        x.append('        <SegmentBase indexRange="%s" indexRangeExact="true">'
                 % ir)
        x.append('          <Initialization range="0-%d"/>'
                 % (int(ir.split('-', 1)[0]) - 1))
        x.append('        </SegmentBase>')
        x.append('      </Representation>')
        x.append('    </AdaptationSet>')

    # аудио-адаптации (по одному на кодек)
    for ac in sorted(auds):
        f = auds[ac]
        ir = _sidx_range(f['url'])
        if not ir:
            continue
        sid += 1
        sr = f.get('asr') or 44100
        lang = f.get('language') or f.get('language_code') or 'und'
        x.append('    <AdaptationSet id="%d" mimeType="audio/mp4" codecs="%s" '
                 'audioSamplingRate="%d" lang="%s" segmentAlignment="true">'
                 % (sid, esc(ac), sr, esc(lang)))
        x.append('      <Representation id="%s" bandwidth="%d">'
                 % (esc(f.get('format_id') or 'a%d' % sid), _aber(f)))
        x.append('        <BaseURL>%s</BaseURL>' % esc(f['url']))
        x.append('        <SegmentBase indexRange="%s" indexRangeExact="true">'
                 % ir)
        x.append('          <Initialization range="0-%d"/>'
                 % (int(ir.split('-', 1)[0]) - 1))
        x.append('        </SegmentBase>')
        x.append('      </Representation>')
        x.append('    </AdaptationSet>')

    x.append('  </Period>')
    x.append('</MPD>')
    return '\n'.join(x), None


def _feed(url, init, start, fpath, stop):
    """Пишет в fifo: init (если есть) + данные с байта start (или с начала).
    stop — threading.Event: тихая остановка при убийстве ffmpeg."""
    try:
        fd = os.open(fpath, os.O_WRONLY)
        if init:
            os.write(fd, init)
        if start is not None:
            r = _rget(url, 'bytes=%d-' % start)
        else:
            r = _rget(url)
        try:
            while not stop.is_set():
                b = r.read(65536)
                if not b:
                    break
                os.write(fd, b)
        finally:
            r.close()
    except Exception:
        pass
    finally:
        try:
            os.close(fd)
        except Exception:
            pass


def yt_stream_prog(meta, start_byte):
    """Стрим строго одним потоком: прогрессивный mp4 (видео+аудио в файле).
    Проксируем googlevideo напрямую, ffmpeg не участвует.
    Перемотка: MX сам считает байт по moov-таблице — отдаём РОВНО с его байта.
    Ленивый: первый next() открывает качалку (и падает с ошибкой, если нет доступа)."""
    if start_byte < 0:
        start_byte = 0
    try:
        if start_byte > 0:
            r = _rget(meta['vurl'], 'bytes=%d-' % start_byte, timeout=90)
        else:
            r = _rget(meta['vurl'], timeout=90)
    except Exception as e:
        raise StopIteration('yt: %s' % e)
    if not r:
        raise StopIteration('yt: нет доступа к потоку')
    try:
        while True:
            b = r.read(65536)
            if not b:
                break
            yield b
    except Exception:
        pass
    finally:
        try:
            r.close()
        except Exception:
            pass


def yt_stream_new(meta, start_sec):
    """Генератор mpegts: python качает 135+140 -> два fifo -> ffmpeg.
    start_sec > 0: старт с моофа на этой секунде (перемотка).
    Ленивый: первый next() поднимает ffmpeg и готовит фиды."""
    stop = threading.Event()
    ident = threading.get_ident()
    fifo_v = '/tmp/yt_v_%d.fifo' % ident
    fifo_a = '/tmp/yt_a_%d.fifo' % ident
    for f in (fifo_v, fifo_a):
        try:
            os.unlink(f)
        except OSError:
            pass
        try:
            os.mkfifo(f)
        except OSError:
            pass
    v_start = a_start = None
    v_init = a_init = None
    if start_sec > 0:
        ref = _pick_ref(meta['vrefs'], start_sec)
        v_start = _moof_off(meta['vurl'], ref[1])
        a_probe = int(meta['asize'] * start_sec / meta['dur'])
        a_start = _moof_off(meta['aurl'], a_probe)
        v_init = meta['init_v']   # ftyp+moov+sidx: оба входа стартуют с init
        a_init = meta['init_a']
    tv = threading.Thread(target=_feed,
                          args=(meta['vurl'], v_init, v_start, fifo_v, stop), daemon=True)
    ta = threading.Thread(target=_feed,
                          args=(meta['aurl'], a_init, a_start, fifo_a, stop), daemon=True)
    tv.start()
    ta.start()
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'warning',
           '-thread_queue_size', '2048',
           '-i', fifo_v, '-i', fifo_a, '-c', 'copy', '-f', 'mpegts', '-']
    try:
        dl = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as e:
        stop.set()
        return 'ffmpeg: %s' % e
    yield b''
    import select
    idle = 0
    try:
        while True:
            rd, _, _ = select.select([dl.stdout], [], [], 10.0)
            if rd:
                chunk = dl.stdout.read(65536)
                if not chunk:
                    break
                idle = 0
                yield chunk
            else:
                idle += 10
                if idle >= 60:
                    # ffmpeg молчит >60с: качалки встали или клиент ушёл до
                    # первых данных (get читает stdout блокирующе и не увидит
                    # обрыв клиента, пока нет данных) — добиваем, иначе
                    # каждый такой запрос оставляет ffmpeg висеть навсегда
                    break
    except Exception:
        pass
    finally:
        stop.set()
        try:
            dl.kill()
        except Exception:
            pass
        for f in (fifo_v, fifo_a):
            try:
                os.unlink(f)
            except OSError:
                pass


def _yt_stream_old(vid, height):
    """Фолбэк: старый путь, yt-dlp сам мёржит dash в mpegts (без перемотки)."""
    url = 'https://www.youtube.com/watch?v=' + (vid or '')
    cmd = [YTDLP, '--no-warnings',
           '-f', _sel(height), '-o', '-', url]
    try:
        dl = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as e:
        return 'yt-dlp: %s' % e
    yield b''
    import select
    idle = 0
    try:
        while True:
            rd, _, _ = select.select([dl.stdout], [], [], 10.0)
            if rd:
                chunk = dl.stdout.read(65536)
                if not chunk:
                    break
                idle = 0
                yield chunk
            else:
                idle += 10
                if idle >= 60:
                    break  # yt-dlp молчит — добиваем (см. yt_stream_new)
    except Exception:
        pass
    finally:
        try:
            dl.kill()
        except Exception:
            pass


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == '/api/yt/search':
                self._json({'query': (q.get('q') or [''])[0], 'results': search((q.get('q') or [''])[0])})
            elif u.path == '/api/yt/recs':
                self._json({'results': recs()})
            elif u.path == '/api/yt/subs':
                self._json({'results': load_subs()})
            elif u.path == '/api/yt/channel':
                cid = (q.get('cid') or [''])[0]
                if not cid:
                    self._json({'error': 'нет cid'}, 400)
                else:
                    self._json({'channel': cid, 'results': channel_videos(cid)})
            elif u.path == '/api/yt/qualities':
                vid = (q.get('vid') or [''])[0].strip()
                if not vid:
                    self._json({'error': 'нет vid'}, 400)
                    return
                d = _yt_info(vid)
                if not d:
                    self._json({'error': 'yt-dlp не отдал инфо'}, 500)
                    return
                self._json({'vid': vid, 'qualities': _yt_qualities(d)})
            elif u.path == '/api/yt/prog':
                vid = (q.get('vid') or [''])[0].strip()
                try:
                    h = int((q.get('h') or ['360'])[0])
                except ValueError:
                    h = 360
                if not vid:
                    self._json({'error': 'нет vid'}, 400)
                    return
                pr, err = _yt_prog(vid, h)
                if pr is None:
                    self._json({'error': err or 'нет прогрессивного формата'}, 500)
                    return
                pr['vid'] = vid
                self._json(pr)
            elif u.path == '/api/yt/mpd':
                vid = (q.get('vid') or [''])[0].strip()
                try:
                    h = int((q.get('h') or ['720'])[0])
                except ValueError:
                    h = 720
                if not vid:
                    self._json({'error': 'нет vid'}, 400)
                    return
                mpd, err = _yt_mpd(vid, h)
                if mpd is None:
                    self._json({'error': err or 'нет dash-форматов'}, 500)
                    return
                data = mpd.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/dash+xml')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            elif u.path.startswith('/api/yt/stream'):
                vid = (q.get('vid') or [''])[0].strip()
                try:
                    h = int((q.get('h') or ['480'])[0])
                except ValueError:
                    h = 480
                if not vid:
                    self._json({'error': 'нет vid'}, 400)
                    return
                meta = _yt_meta(vid, h)
                if not meta:
                    self._json({'error': 'однопоточного формата нет: у ролика только dash (видео и аудио раздельно). Склейку делаем? (h=480)'}, 500)
                    return
                # Range от плеера: bytes=NNN- -> перемотка на NNN-й байт
                rng = self.headers.get('Range') or ''
                start_byte = -1
                if rng.startswith('bytes='):
                    try:
                        start_byte = int(rng[6:].split(',')[0].split('-')[0])
                    except ValueError:
                        start_byte = -1
                try:
                    gen = yt_stream_prog(meta, start_byte)
                    next(gen)  # прогрев: открываем качалку
                except StopIteration as e:
                    msg = e.value if isinstance(e.value, str) else 'yt: ошибка запуска'
                    self._json({'error': msg}, 500)
                    return
                # заголовки до первого чанка — ВАЖНО: send_response() ПЕРВЫМ,
                # иначе curl/плеер видят HTTP/0.9 (заголовок без статусной строки)
                total = meta['total']
                if total > 0 and start_byte >= 0:
                    s = min(max(start_byte, 0), total - 1)
                    self.send_response(206)
                    self.send_header('Content-Range', 'bytes %d-%d/%d' % (s, total - 1, total))
                    self.send_header('Content-Length', str(total - s))
                else:
                    self.send_response(200)
                    self.send_header('Content-Length', str(total))
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                # Таймаут на сокет: если клиент (прокси/МХ) замер и не читает,
                # write заблокируется на полном буфере -> через 30с TimeoutError
                # -> добиваем генератор. Без этого зависший читатель оставлял
                # ffmpeg жить вечно (write блокировался, BrokenPipe не наступал).
                try:
                    self.connection.settimeout(30)
                except Exception:
                    pass
                try:
                    for chunk in gen:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    # клиент ушёл (MX перезапросил/закрыл) или завис — ОБЯЗАТЕЛЬНО
                    # добить генератор, иначе ffmpeg + качалки живут вечно
                    # (планшет лагает от накопленных процессов: каждый запрос
                    # плодил по ffmpeg навсегда)
                    try:
                        gen.close()  # GeneratorExit в yield -> finally -> kill()
                    except Exception:
                        pass
            else:
                self._json({'error': 'not found'}, 404)
        except Exception as e:
            try:
                self._json({'error': str(e)}, 500)
            except Exception:
                pass
        try:
            self.close_connection = True
        except Exception:
            pass


if __name__ == '__main__':
    srv = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write('yt_service: listening on %s:%d (pid %d)\n' % (HOST, PORT, os.getpid()))
    with _chan_lock:
        _chan_state['busy'] = True
    threading.Thread(target=_chan_worker, daemon=True).start()  # прогрев ленты главной
    srv.serve_forever()
