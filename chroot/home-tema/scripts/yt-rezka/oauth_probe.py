#!/usr/bin/env python3
# Диагностика oauth для yt_service: печатает только не-секретное.
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

F = '/home/tema/rezka-yt/oauth.json'
try:
    st = os.stat(F)
    c = json.load(open(F))
except Exception as e:
    print('НЕ ЧИТАЕТСЯ oauth.json:', e); sys.exit(1)

print('oauth.json: mtime=%s uid=%d mode=%o' % (
    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)), st.st_uid, st.st_mode & 0o777))
print('ключи:', sorted(c.keys()))
cid = c.get('client_id') or ''
print('client_id хвост:', c.get('client_secret') and '...' + c['client_id'][-24:] or c.get('client_id'))
print('scopes в файле:', c.get('scopes') or c.get('scope') or '(нет ключа)')
rt = c.get('refresh_token') or ''
print('refresh_token: длина=%d, префикс=%s' % (len(rt), rt[:6]))

d = urllib.parse.urlencode({
    'client_id': c['client_id'],
    'client_secret': c['client_secret'],
    'refresh_token': c['refresh_token'],
    'grant_type': 'refresh_token',
}).encode()

at = None
try:
    with urllib.request.urlopen('https://oauth2.googleapis.com/token', data=d, timeout=25) as r:
        j = json.loads(r.read().decode('utf-8', 'replace'))
    at = j.get('access_token')
    print('REFRESH: OK  scope=%s  expires_in=%s' % (j.get('scope'), j.get('expires_in')))
except urllib.error.HTTPError as e:
    print('REFRESH: HTTP', e.code)
    print('  body:', e.read().decode('utf-8', 'replace')[:500])
except Exception as e:
    print('REFRESH: сетевая ошибка:', repr(e))

if at:
    for name, url in (
        ('subs', 'https://www.googleapis.com/youtube/v3/subscriptions?part=snippet&mine=true&maxResults=1'),
        ('search', 'https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&type=video&maxResults=1'),
    ):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': 'Bearer ' + at}), timeout=25)
            j = json.loads(r.read().decode('utf-8', 'replace'))
            print('API %-6s OK, items=%d' % (name, len(j.get('items', []))))
        except urllib.error.HTTPError as e:
            print('API %-6s HTTP %d: %s' % (name, e.code, e.read().decode('utf-8', 'replace')[:400]))
        except Exception as e:
            print('API %-6s ошибка: %r' % (name, e))
