# -*- coding: utf-8 -*-
# Точка входа APK (bootstrap service_only): поднимаем HTTP-сервер.
# Диагностическая версия: шаги и traceback пишем в /sdcard/rezka.log
import sys
import os
import time

_LOGGED = set()


def _logfile(msg):
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')
    first, _sep, rest = msg.partition('\n')
    msg = '[%s] %s%s' % (stamp, first, ('\n' + rest) if rest else '')
    try:
        for p in ('/sdcard/rezka.log', '/mnt/sdcard/rezka.log', 'rezka.log'):
            try:
                with open(p, 'a') as f:
                    f.write(msg + '\n')
                _LOGGED.add(p)
            except Exception:
                pass
    except Exception:
        pass


def _excepthook(tp, val, tb):
    import traceback
    try:
        _logfile('--- UNCAUGHT EXCEPTION ---\n' + ''.join(traceback.format_exception(tp, val, tb)))
    except Exception:
        pass


sys.excepthook = _excepthook

_logfile('=== rezka-server start ===')
_logfile('step1: python %s' % sys.version)
try:
    os.environ['REZKA_CURL'] = '1'  # внутри APK нет node-агента — только rezka_curl
    _logfile('step2: import server...')
    import server
    _logfile('step3: server imported, calling run()')
    server.run()
except Exception:
    import traceback
    tb = traceback.format_exc()
    _logfile('EXCEPTION:\n' + tb)
    raise