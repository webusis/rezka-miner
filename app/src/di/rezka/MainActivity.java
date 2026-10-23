package di.rezka;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.AsyncTask;
import android.os.Bundle;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.util.LruCache;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;

public class MainActivity extends Activity {

    public static final String PREFS = "rezka";
    public static final String KEY_SERVER = "server";
    public static final String DEF_SERVER = "http://127.0.0.1:8080";

    private static final int AC = Color.rgb(255, 140, 0);
    private static final int TX = Color.rgb(242, 242, 242);
    private static final int TX2 = Color.rgb(154, 154, 163);
    private static final int TX3 = Color.rgb(107, 107, 116);
    private static final int ERR = Color.rgb(255, 107, 107);
    private static final int OK = Color.rgb(95, 211, 123);

    private EditText queryEt;
    private TextView status;
    private GridView grid;
    private Button moreBtn;
    private int curPage = 1;
    private String base = "";

    // панель фильтров (выезжает справа)
    private View ovl, panel;
    private boolean panelOpen = false;
    private boolean hasMore = false;
    private boolean loadingPage = false;
    private int panelW;

    private ArrayList<JSONObject> items = new ArrayList<JSONObject>();

    // фильтры главной: как на rezka /new/ (сортировка + отображать)
    private int selF = 0, selG = 0;
    private int[] filterIds = {R.id.fLast, R.id.fPop, R.id.fWatch};
    private int[] genreIds = {R.id.gAll, R.id.gAnime, R.id.gMult, R.id.gSer, R.id.gFilm};
    private String[] filterVals = {"last", "popular", "watching"};
    private String[] genreVals = {"all", "82", "3", "2", "1"};
    private int[] filterNames = {R.string.filter_last, R.string.filter_popular, R.string.filter_watch};
    private int[] genreNames = {R.string.genre_all, R.string.genre_anime, R.string.genre_mult,
            R.string.genre_series, R.string.genre_films};

    // локальные ленты: Недавние / Избранное (кнопки в панели)
    private int selL = -1;
    private int[] localIds = {R.id.localRecent, R.id.localFav};
    private int[] localNames = {R.string.recent_section, R.string.fav_section};

    // youtube: переключатель REZKA/YT и ленты
    private int mode = 0;                 // 0 = резка, 1 = ютуб
    private int[] tabIds = {R.id.tabRezka, R.id.tabYt};
    private int selY = -1;                // выбранный yt-чип: 0..3, -1 = рекомендации по умолчанию
    private String chanId = null;         // открыт канал из подписок (для back)
    private int[] ytIds = {R.id.ytRecs, R.id.ytSubs, R.id.ytRecent, R.id.ytFav};
    private int[] ytNameIds = {R.string.yt_recs, R.string.yt_subs, R.string.yt_recent, R.string.yt_fav};

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        // ловушка крашей: стек падения пишем в /sdcard/rezka_crash.txt
        Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
            @Override
            public void uncaughtException(Thread thread, Throwable e) {
                try {
                    StringBuilder sb = new StringBuilder();
                    sb.append(e.toString()).append('\n');
                    for (StackTraceElement el : e.getStackTrace())
                        sb.append("  at ").append(el).append('\n');
                    java.io.FileWriter w = new java.io.FileWriter(
                        new java.io.File(android.os.Environment.getExternalStorageDirectory(),
                                         "rezka_crash.txt"));
                    w.write(sb.toString());
                    w.close();
                } catch (Exception ignored) { }
                android.os.Process.killProcess(android.os.Process.myPid());
                System.exit(10);
            }
        });

        setContentView(R.layout.activity_main);
        queryEt = (EditText) findViewById(R.id.query);
        status = (TextView) findViewById(R.id.status);
        grid = (GridView) findViewById(R.id.grid);
        moreBtn = (Button) findViewById(R.id.more);
        moreBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { loadMore(); }
        });

        // панель фильтров: изначально за правым краем экрана
        ovl = findViewById(R.id.ovl);
        panel = findViewById(R.id.panel);
        panelW = (int) (290 * getResources().getDisplayMetrics().density);
        panel.setTranslationX(panelW);

        // гамбургер: открыть панель
        View menuBtn = findViewById(R.id.menuBtn);
        menuBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { openPanel(); }
        });
        // затемнение: тап = закрыть
        ovl.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { closePanel(); }
        });
        // тап в поле поиска — панель уезжает
        queryEt.setOnFocusChangeListener(new View.OnFocusChangeListener() {
            @Override public void onFocusChange(View v, boolean hasFocus) {
                if (hasFocus && panelOpen) closePanel();
            }
        });
        // скролл сетки — панель уезжает; «ещё» показываем только у конца ленты
        grid.setOnScrollListener(new android.widget.AbsListView.OnScrollListener() {
            @Override public void onScrollStateChanged(android.widget.AbsListView v, int state) {
                if (state != android.widget.AbsListView.OnScrollListener.SCROLL_STATE_IDLE && panelOpen)
                    closePanel();
            }
            @Override public void onScroll(android.widget.AbsListView v, int first, int visible, int total) {
                boolean end = total > 0 && first + visible >= total - 2;
                moreBtn.setVisibility(end && hasMore && !loadingPage ? View.VISIBLE : View.GONE);
            }
        });

        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        base = sp.getString(KEY_SERVER, DEF_SERVER);

        // логотип: круглая обрезка, клик — смена сервера
        ImageView logo = (ImageView) findViewById(R.id.logo);
        logo.setImageBitmap(round(decode(R.drawable.logo)));
        logo.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { editServer(); }
        });

        SpannableString ss = new SpannableString("REZKA//MINER");
        ss.setSpan(new ForegroundColorSpan(AC), 5, 12, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        TextView logoText = (TextView) findViewById(R.id.logotext);
        logoText.setText(ss);
        logoText.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        // тап по надписи — сброс на главную (Последние поступления · Все)
        logoText.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { resetHome(); }
        });

        grid.setAdapter(new Adapter());
        grid.setOnItemClickListener(new android.widget.AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(android.widget.AdapterView<?> parent, View v, int pos, long id) {
                if (pos < 0 || pos >= items.size()) return;
                JSONObject c = items.get(pos);
                String url = c.optString("url");
                if (url.startsWith("yt:")) watchYt(c);
                else if (url.startsWith("chan:")) {
                    chanId = url.substring(5);
                    if (mode != 1) switchMode(1);
                    selY = 1;
                    paintChips();
                    loadYtChannel(chanId);
                } else if (url.length() > 0) openDetail(url);
            }
        });

        // чипы фильтров: сортировка
        for (int i = 0; i < filterIds.length; i++) {
            final int idx = i;
            findViewById(filterIds[i]).setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (mode == 0 && selF == idx) return;
                    if (mode != 0) { mode = 0; queryEt.setText(""); selY = -1; chanId = null; }
                    selF = idx;
                    selL = -1;
                    paintTabs();
                    paintChips();
                    loadNew();
                    closePanel();
                }
            });
        }
        // чипы фильтров: отображать
        for (int i = 0; i < genreIds.length; i++) {
            final int idx = i;
            findViewById(genreIds[i]).setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (mode == 0 && selG == idx) return;
                    if (mode != 0) { mode = 0; queryEt.setText(""); selY = -1; chanId = null; }
                    selG = idx;
                    selL = -1;
                    paintTabs();
                    paintChips();
                    loadNew();
                    closePanel();
                }
            });
        }
        // локальные ленты: Недавние / Избранное (клик — лента с постерами)
        for (int i = 0; i < localIds.length; i++) {
            final int idx = i;
            findViewById(localIds[i]).setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (mode == 0 && selL == idx) { loadNew(); return; }   // повторный тап — назад к ленте
                    if (mode != 0) { mode = 0; queryEt.setText(""); selY = -1; chanId = null; paintTabs(); }
                    selL = idx;
                    paintChips();
                    loadLocal(idx);
                    closePanel();
                }
            });
        }
        // переключатель источника: REZKA / YT
        for (int i = 0; i < tabIds.length; i++) {
            final int idx = i;
            findViewById(tabIds[i]).setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (mode == idx) return;
                    switchMode(idx);
                }
            });
        }
        // yt-чипы: Рекомендации / Подписки / Недавние / Избранное
        for (int i = 0; i < ytIds.length; i++) {
            final int idx = i;
            findViewById(ytIds[i]).setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (mode != 1) switchMode(1);
                    if (selY == idx) { loadYt(0); return; }   // повторный тап — назад к рекомендациям
                    selY = idx;
                    chanId = null;
                    paintChips();
                    loadYt(idx);
                    closePanel();
                }
            });
        }
        paintTabs();
        paintChips();
        loadNew();

        // ввод с клавиатуры = поиск
        queryEt.setOnEditorActionListener(new android.widget.TextView.OnEditorActionListener() {
            @Override public boolean onEditorAction(android.widget.TextView v, int actionId, android.view.KeyEvent ev) {
                if (actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH
                        || (ev != null && ev.getKeyCode() == android.view.KeyEvent.KEYCODE_ENTER)) {
                    onSearch(null);
                    return true;
                }
                return false;
            }
        });
    }

    private void editServer() {
        final EditText et = new EditText(this);
        et.setText(base);
        et.setSingleLine(true);
        et.setHint(R.string.server_dialog_hint);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        et.setPadding(pad, pad, pad, pad);

        // управление логами сервера (пишутся в папку приложения)
        final CheckBox logCb = new CheckBox(this);
        logCb.setText(R.string.server_logging);
        logCb.setPadding(pad, 0, pad, 0);
        logCb.setEnabled(false); // активируем после ответа сервера

        final TextView clearBtn = new TextView(this);
        clearBtn.setText(R.string.clear_logs);
        clearBtn.setPadding(pad, pad, pad, pad);
        clearBtn.setTextSize(15);
        clearBtn.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        clearBtn.setTextColor(0xFF999999);
        clearBtn.setClickable(false);

        LinearLayout ll = new LinearLayout(this);
        ll.setOrientation(LinearLayout.VERTICAL);
        ll.addView(et);
        ll.addView(logCb);
        ll.addView(clearBtn);

        new AlertDialog.Builder(this)
            .setTitle(R.string.server_dialog_title)
            .setView(ll)
            .setPositiveButton("OK", new android.content.DialogInterface.OnClickListener() {
                @Override public void onClick(android.content.DialogInterface d, int w) {
                    String s = et.getText().toString().trim();
                    while (s.length() > 0 && s.endsWith("/")) s = s.substring(0, s.length() - 1);
                    if (s.length() == 0) return;
                    base = s;
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                        .putString(KEY_SERVER, base).commit();
                }
            })
            .setNegativeButton(R.string.cancel, null)
            .show();

        logCb.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override public void onCheckedChanged(CompoundButton b, boolean isChecked) {
                // пока чекбокс неактивен (статус ещё не получен) — не шлём
                if (!logCb.isEnabled() || base.length() == 0) return;
                final String u = base + "/api/log/settings?enabled=" + (isChecked ? "1" : "0");
                new Thread(new Runnable() {
                    @Override public void run() {
                        try { Api.get(u, 8000); } catch (Exception ignored) { }
                    }
                }).start();
            }
        });

        clearBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (base.length() == 0) return;
                new Thread(new Runnable() {
                    @Override public void run() {
                        String msg;
                        try {
                            Api.get(base + "/api/log/clear", 8000);
                            msg = getString(R.string.logs_cleared);
                        } catch (Exception e) {
                            msg = getString(R.string.err, e.getMessage());
                        }
                        final String m = msg;
                        runOnUiThread(new Runnable() {
                            @Override public void run() {
                                Toast.makeText(MainActivity.this, m, Toast.LENGTH_SHORT).show();
                            }
                        });
                    }
                }).start();
            }
        });

        // узнать текущее состояние логирования у сервера
        if (base.length() == 0) return;
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    String j = Api.get(base + "/api/log/settings", 8000);
                    final boolean en = new JSONObject(j).optBoolean("enabled", true);
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            logCb.setChecked(en);   // слушатель не сработает: чекбокс ещё неактивен
                            logCb.setEnabled(true);
                            clearBtn.setTextColor(AC);
                            clearBtn.setClickable(true);
                        }
                    });
                } catch (Exception e) {
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            logCb.setText(R.string.server_no_logs);
                        }
                    });
                }
            }
        }).start();
    }

    public void onSearch(View v) {
        if (base.length() == 0) { editServer(); return; }
        hideKeyboard();
        selL = -1;
        selY = -1;
        chanId = null;
        paintChips();
        final String q = queryEt.getText().toString().trim();
        if (q.length() == 0) { resetHome(); return; }
        status.setText(getString(R.string.finding, q));
        status.setTextColor(TX3);
        grid.setAdapter(null);
        final boolean yt = mode == 1;
        new AsyncTask<Void, Void, String>() {
            String err;
            @Override
            protected String doInBackground(Void... a) {
                try {
                    return Api.get(base + (yt ? "/api/yt/search" : "/api/search")
                            + "?q=" + Uri.encode(q));
                } catch (Exception e) {
                    err = e.getMessage();
                    return null;
                }
            }
            @Override
            protected void onPostExecute(String json) {
                if (json == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                try {
                    JSONArray arr = new JSONObject(json).getJSONArray("results");
                    items.clear();
                    for (int i = 0; i < arr.length(); i++) items.add(arr.getJSONObject(i));
                    grid.setAdapter(new Adapter());
                    if (items.size() == 0) {
                        status.setText(R.string.no_results);
                        status.setTextColor(TX3);
                    } else {
                        status.setText(getString(R.string.found, items.size()));
                        status.setTextColor(TX3);
                    }
                } catch (Exception e) {
                    status.setText(getString(R.string.err, e.getMessage()));
                    status.setTextColor(ERR);
                }
                hasMore = false;
                moreBtn.setVisibility(View.GONE);
            }
        }.execute();
    }

    private void hideKeyboard() {
        try {
            InputMethodManager im = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            im.hideSoftInputFromWindow(queryEt.getWindowToken(), 0);
        } catch (Exception ignored) { }
    }

    // ---------- панель фильтров ----------
    private void openPanel() {
        if (panelOpen) return;
        panelOpen = true;
        hideKeyboard();
        ovl.setVisibility(View.VISIBLE);
        ovl.setAlpha(0f);
        ovl.animate().alpha(1f).setDuration(220).start();
        panel.setTranslationX(panelW);
        panel.animate().translationX(0f).setDuration(220).start();
    }

    private void closePanel() {
        if (!panelOpen) return;
        panelOpen = false;
        ovl.animate().alpha(0f).setDuration(200).withEndAction(new Runnable() {
            @Override public void run() { ovl.setVisibility(View.GONE); }
        }).start();
        panel.animate().translationX(panelW).setDuration(200).start();
    }

    // ---------- секции «Недавние» и «Избранное» в панели ----------
    private void loadLocal(final int which) {
        if (base.length() == 0) return;
        hideKeyboard();
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        JSONArray arr = cards(sp, which == 0 ? KEY_RECENT : KEY_FAVS);
        items.clear();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject c = arr.optJSONObject(i);
            if (c != null) items.add(c);
        }
        grid.setAdapter(new Adapter());
        hasMore = false;
        moreBtn.setVisibility(View.GONE);
        if (items.size() == 0) {
            status.setText(which == 0 ? R.string.recent_empty : R.string.fav_empty);
        } else {
            status.setText(getString(R.string.local_status,
                    getString(localNames[which]), items.size()));
        }
        status.setTextColor(TX3);
    }

    // сброс на главную: «Последние поступления · Все» / «ютуб · Рекомендации»
    private void resetHome() {
        queryEt.setText("");
        selF = 0; selG = 0; selL = -1;
        selY = -1; chanId = null;
        paintTabs();
        paintChips();
        if (mode == 0) loadNew();
        else loadYt(0);
    }

    @Override
    public void onBackPressed() {
        if (panelOpen) { closePanel(); return; }
        boolean searched = queryEt.getText().toString().trim().length() > 0;
        if (mode == 1) {
            // из поиска / ленты / канала — назад к рекомендациям, выход — только оттуда
            if (searched || selY != -1 || chanId != null) { resetHome(); return; }
            super.onBackPressed();
            return;
        }
        if (selL != -1 || searched || selF != 0 || selG != 0) {
            resetHome();   // сначала домой, выход из приложения — только с главной
            return;
        }
        super.onBackPressed();
    }

    // ---------- фильтры главной ----------
    private void paintTabs() {
        for (int i = 0; i < tabIds.length; i++) {
            TextView v = (TextView) findViewById(tabIds[i]);
            v.setBackgroundResource(i == mode ? R.drawable.chip_on : R.drawable.chip_bg);
            v.setTextColor(i == mode
                    ? getResources().getColor(R.color.dark_on_ac)
                    : getResources().getColor(R.color.tx2));
        }
    }

    private void switchMode(int m) {
        mode = m;
        queryEt.setText("");
        selL = -1; selY = -1; chanId = null;
        paintTabs();
        paintChips();
        if (mode == 0) loadNew();
        else loadYt(0);
    }

    private void paintChips() {
        for (int i = 0; i < filterIds.length; i++) {
            TextView v = (TextView) findViewById(filterIds[i]);
            boolean on = mode == 0 && i == selF;
            v.setBackgroundResource(on ? R.drawable.chip_on : R.drawable.chip_bg);
            v.setTextColor(on
                    ? getResources().getColor(R.color.dark_on_ac)
                    : getResources().getColor(R.color.tx2));
        }
        for (int i = 0; i < genreIds.length; i++) {
            TextView v = (TextView) findViewById(genreIds[i]);
            boolean on = mode == 0 && i == selG;
            v.setBackgroundResource(on ? R.drawable.chip_on : R.drawable.chip_bg);
            v.setTextColor(on
                    ? getResources().getColor(R.color.dark_on_ac)
                    : getResources().getColor(R.color.tx2));
        }
        for (int i = 0; i < localIds.length; i++) {
            TextView v = (TextView) findViewById(localIds[i]);
            boolean on = mode == 0 && i == selL;
            v.setBackgroundResource(on ? R.drawable.chip_on : R.drawable.chip_bg);
            v.setTextColor(on
                    ? getResources().getColor(R.color.dark_on_ac)
                    : getResources().getColor(R.color.tx2));
        }
        for (int i = 0; i < ytIds.length; i++) {
            TextView v = (TextView) findViewById(ytIds[i]);
            boolean on = mode == 1 && i == selY;
            v.setBackgroundResource(on ? R.drawable.chip_on : R.drawable.chip_bg);
            v.setTextColor(on
                    ? getResources().getColor(R.color.dark_on_ac)
                    : getResources().getColor(R.color.tx2));
        }
    }

    private void loadNew() {
        if (base.length() == 0) return;
        hideKeyboard();
        loadingPage = true;
        final int fIdx = selF, gIdx = selG;
        status.setText(R.string.loading);
        status.setTextColor(TX3);
        grid.setAdapter(null);
        new AsyncTask<Void, Void, String>() {
            String err;
            @Override
            protected String doInBackground(Void... a) {
                try {
                    String url = base + "/api/new?filter=" + filterVals[fIdx]
                            + ("all".equals(genreVals[gIdx]) ? "" : "&genre=" + genreVals[gIdx]);
                    return Api.get(url);
                } catch (Exception e) {
                    err = e.getMessage();
                    return null;
                }
            }
            @Override
            protected void onPostExecute(String json) {
                loadingPage = false;
                if (json == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                try {
                    JSONArray arr = new JSONObject(json).getJSONArray("results");
                    items.clear();
                    curPage = 1;
                    for (int i = 0; i < arr.length(); i++) items.add(arr.getJSONObject(i));
                    grid.setAdapter(new Adapter());
                    hasMore = arr.length() >= 36;
                    moreBtn.setVisibility(View.GONE);
                    status.setText(getString(R.string.new_status,
                            getString(filterNames[fIdx]), getString(genreNames[gIdx]), items.size()));
                    status.setTextColor(TX3);
                } catch (Exception e) {
                    status.setText(getString(R.string.err, e.getMessage()));
                    status.setTextColor(ERR);
                }
            }
        }.execute();
    }

    // догрузка следующей страницы ленты (пагинация /new/page/N/)
    private void loadMore() {
        if (base.length() == 0 || loadingPage || !hasMore) return;
        loadingPage = true;
        final int fIdx = selF, gIdx = selG;
        final int page = curPage + 1;
        moreBtn.setVisibility(View.GONE);
        status.setText(R.string.loading);
        status.setTextColor(TX3);
        new AsyncTask<Void, Void, String>() {
            String err;
            @Override
            protected String doInBackground(Void... a) {
                try {
                    String url = base + "/api/new?filter=" + filterVals[fIdx]
                            + ("all".equals(genreVals[gIdx]) ? "" : "&genre=" + genreVals[gIdx])
                            + "&page=" + page;
                    return Api.get(url);
                } catch (Exception e) {
                    err = e.getMessage();
                    return null;
                }
            }
            @Override
            protected void onPostExecute(String json) {
                loadingPage = false;
                if (json == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    moreBtn.setVisibility(View.VISIBLE);
                    return;
                }
                try {
                    JSONArray arr = new JSONObject(json).getJSONArray("results");
                    for (int i = 0; i < arr.length(); i++) items.add(arr.getJSONObject(i));
                    curPage = page;
                    BaseAdapter a = (BaseAdapter) grid.getAdapter();
                    if (a != null) a.notifyDataSetChanged();
                    else grid.setAdapter(new Adapter());
                    hasMore = arr.length() >= 36;
                    // кнопка — только когда стоим у конца ленты
                    int first = grid.getFirstVisiblePosition();
                    int vis = grid.getChildCount();
                    boolean end = items.size() > 0 && first + vis >= items.size() - 2;
                    moreBtn.setVisibility(end && hasMore ? View.VISIBLE : View.GONE);
                    status.setText(getString(R.string.new_status,
                            getString(filterNames[fIdx]), getString(genreNames[gIdx]), items.size()));
                    status.setTextColor(TX3);
                } catch (Exception e) {
                    status.setText(getString(R.string.err, e.getMessage()));
                    status.setTextColor(ERR);
                    moreBtn.setVisibility(View.VISIBLE);
                }
            }
        }.execute();
    }

    // ---------- youtube: ленты и просмотр ----------
    private void loadYt(final int which) {
        if (base.length() == 0) return;
        hideKeyboard();
        if (which >= 2) { loadYtLocal(which); return; }   // Недавние/Избранное — локально
        final String[] ep = {"/api/yt/recs", "/api/yt/subs"};
        status.setText(R.string.yt_loading);
        status.setTextColor(TX3);
        grid.setAdapter(null);
        new AsyncTask<Void, Void, String>() {
            String err;
            @Override
            protected String doInBackground(Void... a) {
                try {
                    return Api.get(base + ep[which]);
                } catch (Exception e) {
                    err = e.getMessage();
                    return null;
                }
            }
            @Override
            protected void onPostExecute(String json) {
                if (json == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                try {
                    JSONArray arr = new JSONObject(json).getJSONArray("results");
                    items.clear();
                    for (int i = 0; i < arr.length(); i++) items.add(arr.getJSONObject(i));
                    grid.setAdapter(new Adapter());
                    hasMore = false;
                    moreBtn.setVisibility(View.GONE);
                    if (items.size() == 0) status.setText(R.string.yt_empty);
                    else status.setText(getString(R.string.yt_status,
                            getString(ytNameIds[which]), items.size()));
                    status.setTextColor(TX3);
                } catch (Exception e) {
                    status.setText(getString(R.string.err, e.getMessage()));
                    status.setTextColor(ERR);
                }
            }
        }.execute();
    }

    private void loadYtLocal(int which) {
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        JSONArray arr = cards(sp, which == 2 ? KEY_RECENT_YT : KEY_FAVS_YT);
        items.clear();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject c = arr.optJSONObject(i);
            if (c != null) items.add(c);
        }
        grid.setAdapter(new Adapter());
        hasMore = false;
        moreBtn.setVisibility(View.GONE);
        if (items.size() == 0) status.setText(R.string.yt_empty);
        else status.setText(getString(R.string.yt_status,
                getString(ytNameIds[which]), items.size()));
        status.setTextColor(TX3);
    }

    private void loadYtChannel(final String cid) {
        if (base.length() == 0) return;
        hideKeyboard();
        status.setText(R.string.yt_loading);
        status.setTextColor(TX3);
        grid.setAdapter(null);
        new AsyncTask<Void, Void, String>() {
            String err;
            @Override
            protected String doInBackground(Void... a) {
                try {
                    return Api.get(base + "/api/yt/channel?cid=" + Uri.encode(cid));
                } catch (Exception e) {
                    err = e.getMessage();
                    return null;
                }
            }
            @Override
            protected void onPostExecute(String json) {
                if (json == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                try {
                    JSONArray arr = new JSONObject(json).getJSONArray("results");
                    items.clear();
                    for (int i = 0; i < arr.length(); i++) items.add(arr.getJSONObject(i));
                    grid.setAdapter(new Adapter());
                    hasMore = false;
                    moreBtn.setVisibility(View.GONE);
                    if (items.size() == 0) status.setText(R.string.yt_empty);
                    else status.setText(getString(R.string.yt_status, "канал", items.size()));
                    status.setTextColor(TX3);
                } catch (Exception e) {
                    status.setText(getString(R.string.err, e.getMessage()));
                    status.setTextColor(ERR);
                }
            }
        }.execute();
    }

    // Ютуб: сперва список реально доступных качеств (с сервиса), потом свой плеер
    private void watchYt(JSONObject card) {
        addRecent(this, card, KEY_RECENT_YT);
        final String url = card.optString("url");
        if (!url.startsWith("yt:")) return;
        final String vid = url.substring(3);

        final LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(10), dp(16), dp(2));
        // Качеств бывает 6+ (особенно у вертикальных роликов) — пакуем в скролл.
        final ScrollView sc = new ScrollView(this);
        sc.addView(box, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        final TextView wait = new TextView(this);
        wait.setText(R.string.loading);
        wait.setTextColor(getResources().getColor(R.color.tx2));
        wait.setTextSize(15);
        wait.setPadding(dp(16), dp(13), dp(16), dp(13));
        box.addView(wait);

        final AlertDialog dlg = new AlertDialog.Builder(this)
            .setTitle(R.string.yt_quality_title)
            .setView(sc)
            .setNegativeButton(R.string.cancel, null)
            .show();

        new Thread(new Runnable() {
            @Override public void run() {
                final java.util.ArrayList<Integer> hs = new java.util.ArrayList<Integer>();
                final java.util.ArrayList<String> labels = new java.util.ArrayList<String>();
                final java.util.ArrayList<String> kinds = new java.util.ArrayList<String>();
                try {
                    String j = Api.get(base + "/api/yt/qualities?vid=" + Uri.encode(vid), 150000);
                    JSONArray arr = new JSONObject(j).optJSONArray("qualities");
                    if (arr != null) {
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject o = arr.getJSONObject(i);
                            int h = o.optInt("h");
                            if (h > 0) {
                                hs.add(h);
                                labels.add(o.optString("label", h + "p"));
                                kinds.add(o.optString("kind", "dash"));
                            }
                        }
                    }
                } catch (Exception ignored) { }
                if (hs.isEmpty()) {
                    // сервис молчит — фолбэк на 720/360
                    hs.add(720); labels.add("720p"); kinds.add("dash");
                    hs.add(360); labels.add("360p"); kinds.add("dash");
                }
                runOnUiThread(new Runnable() {
                    @Override public void run() {
                        box.removeAllViews();
                        for (int i = 0; i < labels.size(); i++) {
                            final int h = hs.get(i);
                            final String kind = kinds.get(i);
                            TextView row = new TextView(MainActivity.this);
                            row.setText(labels.get(i));
                            row.setTextSize(15);
                            row.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
                            row.setGravity(Gravity.CENTER_VERTICAL);
                            row.setBackgroundResource(i == 0
                                    ? R.drawable.chip_on : R.drawable.chip_bg);
                            row.setTextColor(getResources().getColor(i == 0
                                    ? R.color.dark_on_ac : R.color.tx2));
                            row.setPadding(dp(16), 0, dp(16), 0);
                            // фиксированная высота: строки не разъезжаются и не режутся
                            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                                    ViewGroup.LayoutParams.MATCH_PARENT, dp(38));
                            lp.bottomMargin = dp(4);
                            row.setOnClickListener(new View.OnClickListener() {
                                @Override public void onClick(View v) {
                                    dlg.dismiss();
                                    openYtStream(vid, h, kind);
                                }
                            });
                            box.addView(row, lp);
                        }
                        // если список длинный — ограничиваем высоту и даём скроллиться
                        box.post(new Runnable() {
                            @Override public void run() {
                                int maxH = (int) (getResources()
                                        .getDisplayMetrics().heightPixels * 0.62f);
                                if (box.getHeight() > maxH) {
                                    ViewGroup.LayoutParams lp = sc.getLayoutParams();
                                    lp.height = maxH;
                                    sc.setLayoutParams(lp);
                                }
                            }
                        });
                    }
                });
            }
        }).start();
    }

    private void openYtStream(final String vid, final int h, final String kind) {
        if ("prog".equals(kind)) {
            // Прогрессивный mp4: сперва вытянем прямую ссылку, потом в плеер
            new Thread(new Runnable() {
                @Override public void run() {
                    String direct = null;
                    String err = "нет ссылки";
                    try {
                        String j = Api.get(base + "/api/yt/prog?vid="
                                + Uri.encode(vid) + "&h=" + h, 150000);
                        direct = new JSONObject(j).optString("url");
                    } catch (Exception e) {
                        err = e.getMessage();
                    }
                    final String durl = direct;
                    final String derr = err;
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            if (durl == null || durl.length() == 0) {
                                Toast.makeText(MainActivity.this,
                                        getString(R.string.err, derr),
                                        Toast.LENGTH_LONG).show();
                                return;
                            }
                            startPlayer(durl, true);
                        }
                    });
                }
            }).start();
            return;
        }
        startPlayer(base + "/api/yt/mpd?vid=" + Uri.encode(vid) + "&h=" + h, false);
    }

    private void startPlayer(String u, boolean prog) {
        Intent i = new Intent(this, PlayerActivity.class);
        i.setData(Uri.parse(u));
        i.putExtra("prog", prog);
        try {
            startActivity(i);
        } catch (android.content.ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_player, Toast.LENGTH_SHORT).show();
        }
    }

    private String findMx() {
        String[] cand = {DetailActivity.MX, "com.mxtech.videoplayer.ad"};
        android.content.pm.PackageManager pm = getPackageManager();
        for (String c : cand) {
            try {
                if (pm.getLaunchIntentForPackage(c) != null) return c;
            } catch (Exception ignored) { }
        }
        return null;
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }

    // ---------- карточки-сетка ----------
    class Adapter extends BaseAdapter {
        @Override public int getCount() { return items.size(); }
        @Override public Object getItem(int i) { return items.get(i); }
        @Override public long getItemId(int i) { return i; }

        @Override
        public View getView(int i, View cv, ViewGroup p) {
            if (cv == null) cv = getLayoutInflater().inflate(R.layout.item_result, p, false);
            try {
                JSONObject o = items.get(i);
                ((TextView) cv.findViewById(R.id.title)).setText(o.optString("title"));
                ((TextView) cv.findViewById(R.id.meta)).setText(o.optString("meta"));
                TextView tag = (TextView) cv.findViewById(R.id.tag);
                String t = o.optString("type");
                if (t.length() > 0) { tag.setVisibility(View.VISIBLE); tag.setText(t); }
                else tag.setVisibility(View.GONE);
                final ImageView iv = (ImageView) cv.findViewById(R.id.poster);
                String poster = o.optString("poster");
                String u = poster.length() == 0 ? "" : base + "/api/stream_proxy/img.jpg?url="
                        + Uri.encode(poster);
                Poster.load(u, iv);
            } catch (Exception ignored) { }
            return cv;
        }
    }

    // ---------- загрузка постеров (через наш прокси, чтобы старый планшет не давился https) ----------
    static class Poster {
        static LruCache<String, Bitmap> cache = new LruCache<String, Bitmap>(12 * 1024 * 1024) {
            @Override protected int sizeOf(String k, Bitmap b) { return b.getRowBytes() * b.getHeight(); }
        };

        static void load(final String url, final ImageView iv) {
            if (url.length() == 0) return;
            Bitmap b = cache.get(url);
            if (b != null) { iv.setImageBitmap(b); return; }
            iv.setTag(url);
            new Thread(new Runnable() {
                @Override public void run() {
                    try {
                        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                        c.setConnectTimeout(10000);
                        c.setReadTimeout(25000);
                        InputStream in = c.getInputStream();
                        final Bitmap bp = BitmapFactory.decodeStream(in);
                        in.close();
                        c.disconnect();
                        if (bp != null) cache.put(url, bp);
                        iv.post(new Runnable() {
                            @Override public void run() {
                                if (url.equals(iv.getTag())) iv.setImageBitmap(bp);
                            }
                        });
                    } catch (Exception ignored) { }
                }
            }).start();
        }
    }

    private Bitmap decode(int res) {
        return BitmapFactory.decodeResource(getResources(), res);
    }

    // круглая обрезка (лого как в морде — аватар в круге)
    static Bitmap round(Bitmap src) {
        if (src == null) return null;
        int s = Math.min(src.getWidth(), src.getHeight());
        Bitmap out = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(out);
        Paint p = new Paint();
        p.setAntiAlias(true);
        p.setColor(Color.WHITE);
        c.drawCircle(s / 2f, s / 2f, s / 2f, p);
        p.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.SRC_IN));
        Rect r = new Rect(0, 0, s, s);
        c.drawBitmap(src, r, r, p);
        return out;
    }

    // ---------- избранное / недавние: локально, JSON-массивы карточек ----------
    private static final String KEY_FAVS = "favs";
    private static final String KEY_RECENT = "recent";
    private static final String KEY_FAVS_YT = "favy";
    private static final String KEY_RECENT_YT = "recenty";
    private static final int RECENT_MAX = 15;

    private static JSONArray cards(SharedPreferences sp, String key) {
        try {
            String s = sp.getString(key, "[]");
            JSONArray a = new JSONArray(s);
            return a != null ? a : new JSONArray();
        } catch (Exception e) { return new JSONArray(); }
    }

    static boolean isFav(Activity a, String url) { return isFav(a, url, KEY_FAVS); }

    static boolean isFav(Activity a, String url, String key) {
        JSONArray arr = cards(a.getSharedPreferences(PREFS, MODE_PRIVATE), key);
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o != null && url.equals(o.optString("url"))) return true;
        }
        return false;
    }

    // API 17: в org.json нет remove(int)/put(int,..) — собираем вручную
    private static JSONArray rebuild(JSONArray src, int skipIdx, JSONObject prepend) {
        JSONArray r = new JSONArray();
        try {
            if (prepend != null) r.put(prepend);
            for (int i = 0; i < src.length(); i++) {
                if (i == skipIdx) continue;
                r.put(src.get(i));
            }
        } catch (Exception ignored) { }
        return r;
    }

    static boolean toggleFav(Activity a, JSONObject card) { return toggleFav(a, card, KEY_FAVS); }

    static boolean toggleFav(Activity a, JSONObject card, String key) {
        SharedPreferences sp = a.getSharedPreferences(PREFS, MODE_PRIVATE);
        JSONArray arr = cards(sp, key);
        String url = card.optString("url");
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o != null && url.equals(o.optString("url"))) {
                arr = rebuild(arr, i, null);
                sp.edit().putString(key, arr.toString()).commit();
                return false;
            }
        }
        arr = rebuild(arr, -1, card);
        sp.edit().putString(key, arr.toString()).commit();
        return true;
    }

    static void addRecent(Activity a, JSONObject card) { addRecent(a, card, KEY_RECENT); }

    static void addRecent(Activity a, JSONObject card, String key) {
        if (card == null || card.optString("url").length() == 0) return;
        SharedPreferences sp = a.getSharedPreferences(PREFS, MODE_PRIVATE);
        JSONArray arr = cards(sp, key);
        String url = card.optString("url");
        int skip = -1;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o != null && url.equals(o.optString("url"))) { skip = i; break; }
        }
        arr = rebuild(arr, skip, card);
        while (arr.length() > RECENT_MAX) arr = rebuild(arr, arr.length() - 1, null);
        sp.edit().putString(key, arr.toString()).commit();
    }

    void openDetail(String url) {
        JSONObject card = null;
        for (int i = 0; i < items.size(); i++) {
            JSONObject o = items.get(i);
            if (url.equals(o.optString("url"))) { card = o; break; }
        }
        if (card == null) {
            card = new JSONObject();
            try { card.put("url", url); } catch (Exception ignored) { }
        }
        addRecent(this, card);
        Intent i = new Intent(this, DetailActivity.class);
        i.putExtra("url", url);
        startActivity(i);
    }
}