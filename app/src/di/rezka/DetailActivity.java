package di.rezka;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.AsyncTask;
import android.os.Bundle;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Locale;

public class DetailActivity extends Activity {

    public static final String MX = "com.mxtech.videoplayer.pro";
    static final String[] QORDER = { "1080p", "720p", "480p", "360p" };

    private static final int AC = Color.rgb(255, 140, 0);
    private static final int AC2 = Color.rgb(255, 176, 77);
    private static final int TX = Color.rgb(242, 242, 242);
    private static final int TX2 = Color.rgb(154, 154, 163);
    private static final int TX3 = Color.rgb(107, 107, 116);
    private static final int ERR = Color.rgb(255, 107, 107);
    private static final int DARK = Color.rgb(26, 16, 0);
    private static final int BG2C = Color.rgb(16, 16, 20);
    private static final int CARD = Color.rgb(21, 21, 26);
    private static final int LINE = Color.rgb(42, 42, 49);

    private TextView status;
    private LinearLayout root;
    private String base;
    private String titleUrl;

    private JSONObject data;            // полный ответ /api/title
    private JSONObject curTr;           // выбранный перевод
    private int selSeason = 1;
    private String curQ = "480p";
    private ArrayList<String> allQs = new ArrayList<String>();

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_detail);
        status = (TextView) findViewById(R.id.status);
        root = (LinearLayout) findViewById(R.id.root);

        base = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
                .getString(MainActivity.KEY_SERVER, MainActivity.DEF_SERVER);
        titleUrl = getIntent().getStringExtra("url");

        findViewById(R.id.back).setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { finish(); }
        });

        load();
    }

    // ---------- загрузка структуры ----------
    private void load() {
        status.setText(R.string.structure_loading);
        new AsyncTask<Void, Void, JSONObject>() {
            String err;
            @Override protected JSONObject doInBackground(Void... a) {
                try {
                    String j = Api.get(base + "/api/title?url=" + Uri.encode(titleUrl) + "&streams=1", 150000);
                    return new JSONObject(j);
                } catch (Exception e) { err = e.getMessage(); return null; }
            }
            @Override protected void onPostExecute(JSONObject o) {
                if (o == null) {
                    String msg = (err != null && err.length() > 0) ? err : getString(R.string.err_timeout);
                    status.setText(getString(R.string.err, msg));
                    status.setTextColor(ERR);
                    return;
                }
                data = o;
                status.setText("");
                render();
            }
        }.execute();
    }

    // ---------- рендер всей страницы ----------
    private void render() {
        if (data == null) return;
        root.removeAllViews();
        try {
            JSONArray trs = data.optJSONArray("translators");
            if (trs == null || trs.length() == 0) {
                status.setText(R.string.no_translators);
                status.setTextColor(ERR);
                return;
            }
            // перевод выбирается кликом; здесь — только если ещё не выбран
            if (curTr == null) {
                for (int i = 0; i < trs.length(); i++)
                    if (trs.getJSONObject(i).optBoolean("active", false)) { curTr = trs.getJSONObject(i); break; }
                if (curTr == null) curTr = trs.getJSONObject(0);
            }

            allQs.clear();
            collectQs(curTr);

            boolean isMovie = "movie".equals(data.optString("type"));
            buildHeader();
            buildTranslators(trs);
            if (allQs.size() > 0) buildQuality();
            if (isMovie) {
                buildMovie();
            } else {
                buildSeasons();
                buildEpisodes();
            }
        } catch (Exception e) {
            status.setText(getString(R.string.err, e.getMessage()));
            status.setTextColor(ERR);
        }
    }

    private void collectQs(JSONObject tr) {
        try {
            JSONArray ss = tr.optJSONArray("seasons");
            if (ss == null) return;
            for (int i = 0; i < ss.length(); i++) {
                JSONArray eps = ss.getJSONObject(i).optJSONArray("episodes");
                if (eps == null) continue;
                for (int j = 0; j < eps.length(); j++) {
                    JSONObject qs = eps.getJSONObject(j).optJSONObject("qualities");
                    if (qs == null) continue;
                    JSONArray names = qs.names();
                    if (names == null) continue;
                    for (int k = 0; k < names.length(); k++) {
                        String q = names.optString(k);
                        if (!allQs.contains(q)) allQs.add(q);
                    }
                }
            }
        } catch (Exception ignored) { }
    }

    // ---------- шапка: постер + название + инфо ----------
    private void buildHeader() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setBackgroundDrawable(roundBg(CARD, LINE, 14, 1));
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.bottomMargin = dp(18);
        root.addView(card, lp);

        ImageViewWrap poster = new ImageViewWrap(this);
        poster.setLayoutParams(new LinearLayout.LayoutParams(dp(150), dp(225)));
        poster.setScaleType(ImageViewWrap.ScaleType.CENTER_CROP);
        poster.setBackgroundColor(CARD);
        String p = data.optString("poster");
        if (p.length() > 0) {
            MainActivity.Poster.load(base + "/api/stream_proxy/img.jpg?url=" + Uri.encode(p), poster);
        }
        card.addView(poster);

        LinearLayout info = new LinearLayout(this);
        info.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        ilp.leftMargin = dp(14);
        card.addView(info, ilp);

        TextView t = tv(TX, 22, true);
        t.setText(data.optString("title"));
        info.addView(t);

        String kv = data.optString("meta");
        if ("series".equals(data.optString("type")) && data.has("meta")) { }
        if (kv.length() > 0) {
            TextView kvv = tv(TX2, 13, false);
            kvv.setText(kv);
            kvv.setPadding(0, dp(4), 0, 0);
            info.addView(kvv);
        }

        // рейтинги IMDb / Кинопоиск
        JSONObject rating = data.optJSONObject("rating");
        if (rating != null && rating.length() > 0) {
            StringBuilder rb = new StringBuilder();
            if (rating.has("imdb")) rb.append("IMDb ").append(rating.optString("imdb"));
            if (rating.has("kp")) {
                if (rb.length() > 0) rb.append("   ·   ");
                rb.append("Кинопоиск ").append(rating.optString("kp"));
            }
            if (rb.length() > 0) {
                TextView rv = tv(AC, 14, true);
                rv.setText(rb.toString());
                rv.setPadding(0, dp(6), 0, 0);
                info.addView(rv);
            }
        }

        // инфо-таблица: пары «поле: значение» (текстом, без ссылок)
        JSONArray facts = data.optJSONArray("facts");
        if (facts != null) {
            for (int fi = 0; fi < facts.length(); fi++) {
                JSONArray f = facts.optJSONArray(fi);
                if (f == null || f.length() < 2) continue;
                String k = f.optString(0);
                String v = f.optString(1);
                if (k.length() == 0 || v.length() == 0) continue;
                if ("Рейтинги".equals(k)) continue;   // дублирует rating-строку выше
                TextView fv = tv(TX2, 13, false);
                SpannableString fs = new SpannableString(k + ": " + v);
                fs.setSpan(new ForegroundColorSpan(TX3), 0, k.length() + 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                fv.setText(fs);
                fv.setMaxLines(3);
                fv.setEllipsize(android.text.TextUtils.TruncateAt.END);
                fv.setPadding(0, dp(3), 0, 0);
                info.addView(fv);
            }
        }

        // полное описание
        String desc = data.optString("description");
        if (desc.length() > 0) {
            TextView d = tv(TX2, 13, false);
            d.setText(desc);
            d.setPadding(0, dp(8), 0, 0);
            info.addView(d);
        }

        // избранное: карточка сохраняется локально, в панели появится список
        final JSONObject favCard = new JSONObject();
        try {
            favCard.put("url", titleUrl);
            favCard.put("title", data.optString("title"));
            favCard.put("poster", data.optString("poster"));
            favCard.put("type", data.optString("type"));
        } catch (Exception ignored) { }
        final boolean inFav = MainActivity.isFav(this, titleUrl);
        final TextView fav = tv(DARK, 14, true);
        fav.setText(inFav ? R.string.fav_del : R.string.fav_add);
        fav.setPadding(dp(14), dp(9), dp(14), dp(9));
        fav.setGravity(1);
        fav.setBackgroundDrawable(roundBg(inFav ? AC2 : AC, inFav ? AC2 : AC, 10, 0));
        LinearLayout.LayoutParams flp = lpWrap();
        flp.topMargin = dp(12);
        fav.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                boolean now = MainActivity.toggleFav(DetailActivity.this, favCard);
                fav.setText(now ? R.string.fav_del : R.string.fav_add);
                fav.setBackgroundDrawable(roundBg(now ? AC2 : AC, now ? AC2 : AC, 10, 0));
                Toast.makeText(DetailActivity.this,
                        now ? R.string.fav_added : R.string.fav_removed, Toast.LENGTH_SHORT).show();
            }
        });
        info.addView(fav, flp);
    }

    // ---------- переводы: табы ----------
    private void buildTranslators(JSONArray trs) {
        sec("ПЕРЕВОДЫ");
        HorizontalScrollView hsv = new HorizontalScrollView(this);
        hsv.setHorizontalScrollBarEnabled(false);
        hsv.setFillViewport(true);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        hsv.addView(row, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        final int selId = curTr.optInt("id", 0);
        for (int i = 0; i < trs.length(); i++) {
            final JSONObject tr;
            try { tr = trs.getJSONObject(i); } catch (Exception e) { continue; }
            int id = tr.optInt("id", 0);
            boolean on = id == selId;
            TextView tab = tv(on ? DARK : TX2, 13, on);
            tab.setText(tr.optString("name"));
            tab.setPadding(dp(14), dp(7), dp(14), dp(7));
            tab.setSingleLine(true);
            tab.setBackgroundDrawable(roundBg(on ? AC : BG2C, on ? AC : LINE, 8, 1));
            LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            tlp.rightMargin = dp(8);
            tab.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (tr.optInt("id", 0) != curTr.optInt("id", 0)) {
                        curTr = tr;
                        // сезон сохраняем, если он есть у нового перевода;
                        // иначе — первый сезон новой озвучки
                        if (!seasonExists(tr, selSeason)) selSeason = firstSeason(tr);
                        render();
                        seedSeasonQs();   // дотягиваем потоки выбранного перевода
                    }
                }
            });
            row.addView(tab, tlp);
        }
        root.addView(hsv, lpWrap());
    }

    // ---------- качество: чипсы ----------
    private void buildQuality() {
        sec("КАЧЕСТВО");
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < allQs.size(); i++) {
            final String q = allQs.get(i);
            boolean on = q.equals(curQ);
            TextView chip = tv(on ? DARK : TX2, 13, on);
            chip.setText(q);
            chip.setPadding(dp(14), dp(6), dp(14), dp(6));
            chip.setBackgroundDrawable(roundBg(on ? AC : BG2C, on ? AC : LINE, 7, 1));
            LinearLayout.LayoutParams clp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            clp.rightMargin = dp(8);
            chip.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    curQ = q;
                    render();
                }
            });
            row.addView(chip, clp);
        }
        root.addView(row, lpWrap());
    }

    // ---------- фильм: кнопка смотреть ----------
    private void buildMovie() {
        final JSONObject qs = movieQualities(curTr);
        final boolean empty = qs == null;
        TextView btn = tv(DARK, 17, true);
        btn.setText(getString(R.string.watch_movie) + (empty ? "" : " · " + pickQ(qs, curQ)));
        btn.setPadding(dp(18), dp(15), dp(18), dp(15));
        btn.setGravity(1);
        btn.setBackgroundDrawable(roundBg(AC, AC, 12, 0));
        LinearLayout.LayoutParams blp = lpWrap();
        blp.topMargin = dp(14);
        root.addView(btn, blp);
        btn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (empty) {
                    fetchStream(0, 0, true);
                } else {
                    play(qs, "stream.mp4");
                }
            }
        });
        if (empty) {
            TextView hint = tv(TX3, 12, false);
            hint.setText(R.string.no_links);
            hint.setPadding(0, dp(8), 0, 0);
            root.addView(hint, lpWrap());
        }
    }

    // качества фильма: первый непустой qualities среди всех сезонов перевода
    // (сервер кладёт фильм в «сезон 1, серия 1»)
    private JSONObject movieQualities(JSONObject tr) {
        try {
            JSONArray ss = tr.optJSONArray("seasons");
            if (ss == null) return null;
            for (int i = 0; i < ss.length(); i++) {
                JSONArray eps = ss.getJSONObject(i).optJSONArray("episodes");
                if (eps == null) continue;
                for (int j = 0; j < eps.length(); j++) {
                    JSONObject qo = eps.getJSONObject(j).optJSONObject("qualities");
                    if (qo != null && qo.length() > 0) return qo;
                }
            }
        } catch (Exception ignored) { }
        return null;
    }

    // ---------- сериал: сезоны (спиннер) ----------
    private void buildSeasons() {
        sec("СЕЗОНЫ");
        JSONArray ss = curTr.optJSONArray("seasons");
        if (ss == null || ss.length() == 0) {
            TextView none = tv(TX3, 13, false);
            none.setText(R.string.no_seasons);
            root.addView(none, lpWrap());
            return;
        }
        final int[] nums = new int[ss.length()];
        final String[] titles = new String[ss.length()];
        for (int i = 0; i < ss.length(); i++) {
            JSONObject s = ss.optJSONObject(i);
            nums[i] = s.optInt("season", i + 1);
            String st = s.optString("title");
            titles[i] = st.length() > 0 ? nums[i] + " · " + st : "Сезон " + nums[i];
        }
        Spinner sp = new Spinner(this);
        ArrayAdapter<String> ad = new ArrayAdapter<String>(this,
                android.R.layout.simple_spinner_item, titles);
        ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        sp.setAdapter(ad);
        int cur = 0;
        for (int i = 0; i < nums.length; i++) if (nums[i] == selSeason) { cur = i; break; }
        sp.setSelection(cur);
        sp.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                if (nums[pos] != selSeason) {
                    selSeason = nums[pos];
                    render();
                }
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });
        root.addView(sp, lpWrap());
    }

    // ---------- сериал: серии ----------
    private void buildEpisodes() {
        sec("СЕРИИ");
        JSONArray ss = curTr.optJSONArray("seasons");
        if (ss == null) return;
        JSONObject season = null;
        for (int i = 0; i < ss.length(); i++) {
            if (ss.optJSONObject(i).optInt("season", 0) == selSeason) { season = ss.optJSONObject(i); break; }
        }
        if (season == null) {
            TextView none = tv(TX3, 13, false);
            none.setText(R.string.no_episodes);
            root.addView(none, lpWrap());
            return;
        }
        JSONArray eps = season.optJSONArray("episodes");
        if (eps == null || eps.length() == 0) {
            TextView none = tv(TX3, 13, false);
            none.setText(R.string.no_episodes);
            root.addView(none, lpWrap());
            return;
        }
        for (int i = 0; i < eps.length(); i++) {
            final JSONObject ep = eps.optJSONObject(i);
            final int epNum = ep.optInt("episode", i + 1);
            JSONObject qs = ep.optJSONObject("qualities");
            final boolean empty = qs == null || qs.length() == 0;
            String chosen = empty ? null : pickQ(qs, curQ);

            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.HORIZONTAL);
            card.setGravity(1);
            card.setBackgroundDrawable(roundBg(CARD, LINE, 10, 1));
            card.setPadding(dp(12), dp(11), dp(12), dp(11));
            LinearLayout.LayoutParams clp = lpWrap();
            clp.bottomMargin = dp(8);
            card.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    if (empty) fetchStream(selSeason, epNum, false);
                    else play(ep.optJSONObject("qualities"),
                            String.format(Locale.US, "s%02de%02d.mp4", selSeason, epNum));
                }
            });

            TextView num = tv(AC, 15, true);
            num.setText(String.format(Locale.US, "x%02d", epNum));
            card.addView(num);

            TextView name = tv(TX2, 13, false);
            String et = ep.optString("title");
            name.setText(et);
            name.setPadding(dp(12), 0, 0, 0);
            name.setSingleLine(true);
            name.setEllipsize(android.text.TextUtils.TruncateAt.END);
            LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            card.addView(name, nlp);

            if (chosen != null) {
                TextView q = tv(AC2, 12, true);
                q.setText(chosen);
                q.setPadding(dp(8), 0, 0, 0);
                card.addView(q);
            } else if (empty) {
                TextView q = tv(TX3, 12, false);
                q.setText("···");
                q.setPadding(dp(8), 0, 0, 0);
                card.addView(q);
            }
            root.addView(card, clp);
        }

        // кнопка: сезон целиком в MX
        TextView mx = tv(DARK, 15, true);
        mx.setText(R.string.season_mx);
        mx.setPadding(dp(18), dp(14), dp(18), dp(14));
        mx.setGravity(1);
        mx.setBackgroundDrawable(roundBg(AC, AC, 12, 0));
        LinearLayout.LayoutParams mlp = lpWrap();
        mlp.topMargin = dp(10);
        mx.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { chooseSeasonQuality(); }
        });
        root.addView(mx, mlp);
    }

    // ---------- ленивый фетч потоков ----------
    private void fetchStream(int season, int episode, final boolean isMovie) {
        status.setText(R.string.stream_loading);
        final int sn = season, ep = episode;
        new AsyncTask<Void, Void, JSONObject>() {
            String err;
            @Override protected JSONObject doInBackground(Void... a) {
                try {
                    String u = base + "/api/stream?id=" + data.optString("id")
                            + "&tid=" + curTr.optInt("id", 0)
                            + "&season=" + sn + "&episode=" + ep
                            + "&url=" + Uri.encode(titleUrl);
                    return new JSONObject(Api.get(u));
                } catch (Exception e) { err = e.getMessage(); return null; }
            }
            @Override protected void onPostExecute(JSONObject o) {
                status.setText("");
                if (o == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                JSONObject qs = o.optJSONObject("qualities");
                if (qs == null || qs.length() == 0) {
                    status.setText(R.string.no_links);
                    status.setTextColor(ERR);
                    return;
                }
                // кладём качества в структуру, чтобы не фетчить повторно
                try {
                    if (isMovie) {
                        JSONArray ss = curTr.optJSONArray("seasons");
                        JSONObject target = null;
                        if (ss != null) {
                            for (int i = 0; i < ss.length() && target == null; i++) {
                                JSONArray epl = ss.getJSONObject(i).optJSONArray("episodes");
                                if (epl != null && epl.length() > 0) target = epl.getJSONObject(0);
                            }
                        }
                        if (target == null) {
                            JSONObject ep1 = new JSONObject();
                            ep1.put("episode", 1);
                            ep1.put("title", "");
                            JSONArray epl = new JSONArray();
                            epl.put(ep1);
                            JSONObject s1 = new JSONObject();
                            s1.put("season", 1);
                            s1.put("title", "");
                            s1.put("episodes", epl);
                            JSONArray ssl = curTr.optJSONArray("seasons");
                            if (ssl == null) { ssl = new JSONArray(); curTr.put("seasons", ssl); }
                            ssl.put(s1);
                            target = ep1;
                        }
                        target.put("qualities", qs);
                    } else {
                        JSONArray ss = curTr.optJSONArray("seasons");
                        for (int i = 0; i < ss.length(); i++) {
                            JSONObject s = ss.getJSONObject(i);
                            if (s.optInt("season", 0) == sn) {
                                JSONArray epl = s.optJSONArray("episodes");
                                for (int j = 0; j < epl.length(); j++) {
                                    JSONObject e = epl.getJSONObject(j);
                                    if (e.optInt("episode", 0) == ep) e.put("qualities", qs);
                                }
                            }
                        }
                    }
                } catch (Exception ignored) { }
                render();
                if (isMovie) play(qs, "stream.mp4");
                else play(qs, String.format(Locale.US, "s%02de%02d.mp4", sn, ep));
            }
        }.execute();
    }

    // ---------- выбор качества ----------
    static String pickQ(JSONObject qs, String want) {
        if (qs == null || qs.length() == 0) return null;
        if (want != null && qs.has(want)) return want;
        for (String q : QORDER) if (qs.has(q)) return q;   // ближайшее доступное лучшее
        JSONArray names = qs.names();
        return (names != null && names.length() > 0) ? names.optString(0) : null;
    }

    // ---------- играть одну серию/фильм в MX ----------
    private void play(JSONObject qs, String label) {
        String q = pickQ(qs, curQ);
        if (q == null) {
            status.setText(R.string.no_links);
            status.setTextColor(ERR);
            return;
        }
        String u;
        try { u = qs.getString(q); } catch (Exception e) { return; }
        String prox = base + "/api/stream_proxy/" + label + "?url=" + Uri.encode(u);
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(Uri.parse(prox), "video/*");
        String mx = findMx();
        if (mx != null) i.setPackage(mx);
        try {
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_player, Toast.LENGTH_SHORT).show();
        }
    }

    // ---------- выбор качества перед «сезон целиком» ----------
    private void chooseSeasonQuality() {
        JSONArray ss = curTr.optJSONArray("seasons");
        if (ss == null) { status.setText(""); return; }
        JSONObject s = null;
        for (int i = 0; i < ss.length(); i++) {
            if (ss.optJSONObject(i).optInt("season", 0) == selSeason) { s = ss.optJSONObject(i); break; }
        }
        if (s == null) { status.setText(""); return; }
        // собираем качества, реально доступные в этом сезоне
        final ArrayList<String> qs = new ArrayList<String>();
        JSONArray eps = s.optJSONArray("episodes");
        if (eps == null) { status.setText(""); return; }
        for (int i = 0; i < eps.length(); i++) {
            JSONObject qo = eps.optJSONObject(i).optJSONObject("qualities");
            if (qo == null) continue;
            JSONArray names = qo.names();
            if (names == null) continue;
            for (int j = 0; j < names.length(); j++) {
                String q = names.optString(j);
                if (!qs.contains(q)) qs.add(q);
            }
        }
        if (qs.size() == 0) {
            // структура без потоков (неактивный перевод или сезон ещё не
            // дотянут): просим сервер и повторно открываем выбор качества
            fetchSeason(selSeason, new Runnable() {
                @Override public void run() { chooseSeasonQuality(); }
            });
            return;
        }
        if (qs.size() == 1) { openSeasonMx(selSeason, qs.get(0)); return; }
        // сортируем по QORDER (лучшие первыми)
        java.util.Collections.sort(qs, new java.util.Comparator<String>() {
            @Override public int compare(String a, String b) {
                return idx(b) - idx(a);
            }
            int idx(String q) {
                for (int i = 0; i < QORDER.length; i++) if (QORDER[i].equals(q)) return i;
                return QORDER.length;
            }
        });
        qualityDialog(qs);
    }

    // кастомный список качества — в стиле приложения (на 4.2.2 стандартный
    // диалог на тёмной теме рисует невидимый текст)
    private void qualityDialog(final ArrayList<String> qs) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(10), dp(16), dp(2));
        for (int i = 0; i < qs.size(); i++) {
            final String q = qs.get(i);
            boolean on = q.equals(curQ);
            TextView row = tv(on ? DARK : TX, 15, on);
            row.setText(q + (on ? "  ✓" : ""));
            row.setPadding(dp(16), dp(13), dp(16), dp(13));
            row.setBackgroundDrawable(roundBg(on ? AC : BG2C, on ? AC : LINE, 8, 1));
            LinearLayout.LayoutParams lp = lpWrap();
            lp.bottomMargin = dp(8);
            row.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    curQ = q;
                    openSeasonMx(selSeason, q);
                }
            });
            box.addView(row, lp);
        }
        new AlertDialog.Builder(this)
            .setTitle(R.string.quality_title)
            .setView(box)
            .setNegativeButton(R.string.cancel, null)
            .show();
    }

    // ---------- сезон целиком: video_list (Uri[]) ----------
    private void openSeasonMx(int season, String q) {
        status.setText(R.string.playlist_loading);
        JSONArray ss = curTr.optJSONArray("seasons");
        if (ss == null) { status.setText(""); return; }
        JSONObject s = null;
        for (int i = 0; i < ss.length(); i++) {
            if (ss.optJSONObject(i).optInt("season", 0) == season) { s = ss.optJSONObject(i); break; }
        }
        if (s == null) { status.setText(""); return; }
        ArrayList<Uri> uris = buildSeasonUris(s, season, q);
        JSONArray epl = s.optJSONArray("episodes");
        // в структуре качества пустые (неактивный перевод) или часть серий
        // без потоков — дотягиваем сезон одним запросом /api/season и открываем
        if (uris.isEmpty() || (epl != null && uris.size() < epl.length())) {
            fetchSeasonAndOpen(season, q);
            return;
        }
        status.setText("");
        openMx(uris);
    }

    private ArrayList<Uri> buildSeasonUris(JSONObject s, int season, String q) {
        ArrayList<Uri> uris = new ArrayList<Uri>();
        JSONArray eps = s.optJSONArray("episodes");
        if (eps == null) return uris;
        for (int i = 0; i < eps.length(); i++) {
            JSONObject e = eps.optJSONObject(i);
            JSONObject qs = e.optJSONObject("qualities");
            if (qs == null || qs.length() == 0) continue;   // без потоков — пропуск
            int n = e.optInt("episode", i + 1);
            String pick = pickQ(qs, q);
            if (pick == null) continue;
            String u = qs.optString(pick);
            String label = String.format(Locale.US, "s%02de%02d.mp4", season, n);
            uris.add(Uri.parse(base + "/api/stream_proxy/" + label + "?url=" + Uri.encode(u)));
        }
        return uris;
    }

    private void openMx(ArrayList<Uri> uris) {
        if (uris.size() == 0) {
            Toast.makeText(this, R.string.no_links, Toast.LENGTH_SHORT).show();
            return;
        }
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(uris.get(0), "video/*");
        i.putExtra("video_list", uris.toArray(new Uri[0]));
        String mx = findMx();
        if (mx != null) i.setPackage(mx);
        try {
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_player, Toast.LENGTH_SHORT).show();
        }
    }

    // есть ли у перевода сезон с номером s (для сохранения при смене озвучки)
    private boolean seasonExists(JSONObject tr, int s) {
        JSONArray ss = tr == null ? null : tr.optJSONArray("seasons");
        if (ss == null) return false;
        for (int i = 0; i < ss.length(); i++)
            if (ss.optJSONObject(i).optInt("season", 0) == s) return true;
        return false;
    }

    // номер первого сезона перевода (список уже отсортирован сервером)
    private int firstSeason(JSONObject tr) {
        JSONArray ss = tr == null ? null : tr.optJSONArray("seasons");
        if (ss != null && ss.length() > 0) return ss.optJSONObject(0).optInt("season", 1);
        return 1;
    }

    // сезон для выбранного перевода (в т.ч. неактивного): сервер сам
    // параллельно тянет потоки всех серий сезона, клиент подмешивает в curTr
    private void fetchSeasonAndOpen(final int season, final String q) {
        new AsyncTask<Void, Void, JSONObject>() {
            String err;
            @Override protected JSONObject doInBackground(Void... a) {
                try {
                    String u = base + "/api/season?id=" + data.optString("id")
                            + "&tid=" + curTr.optInt("id", 0)
                            + "&season=" + season
                            + "&url=" + Uri.encode(titleUrl);
                    return new JSONObject(Api.get(u));
                } catch (Exception e) { err = e.getMessage(); return null; }
            }
            @Override protected void onPostExecute(JSONObject o) {
                status.setText("");
                if (o == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                mergeSeasonQs(o, season);
                JSONObject s = null;
                JSONArray ss = curTr.optJSONArray("seasons");
                if (ss != null) {
                    for (int i = 0; i < ss.length(); i++) {
                        if (ss.optJSONObject(i).optInt("season", 0) == season) { s = ss.optJSONObject(i); break; }
                    }
                }
                ArrayList<Uri> uris = s != null ? buildSeasonUris(s, season, q) : new ArrayList<Uri>();
                openMx(uris);
            }
        }.execute();
    }

    // дотянуть сезон и выполнить after (в UI-потоке) — для «сезона целиком»,
    // когда в структуре качеств ещё нет
    private void fetchSeason(final int season, final Runnable after) {
        final int sn = season;
        new AsyncTask<Void, Void, JSONObject>() {
            String err;
            @Override protected JSONObject doInBackground(Void... a) {
                try {
                    String u = base + "/api/season?id=" + data.optString("id")
                            + "&tid=" + curTr.optInt("id", 0)
                            + "&season=" + sn
                            + "&url=" + Uri.encode(titleUrl);
                    return new JSONObject(Api.get(u));
                } catch (Exception e) { err = e.getMessage(); return null; }
            }
            @Override protected void onPostExecute(JSONObject o) {
                if (o == null) {
                    status.setText(getString(R.string.err, err));
                    status.setTextColor(ERR);
                    return;
                }
                mergeSeasonQs(o, sn);
                if (after != null) after.run();
            }
        }.execute();
    }

    // подмешиваем качества сезона (ответ /api/season) в структуру выбранного перевода
    private void mergeSeasonQs(JSONObject o, final int season) {
        try {
            JSONArray eps = o.optJSONArray("episodes");
            JSONArray ss = curTr.optJSONArray("seasons");
            if (eps != null && ss != null) {
                for (int i = 0; i < ss.length(); i++) {
                    JSONObject s = ss.getJSONObject(i);
                    if (s.optInt("season", 0) == season) {
                        JSONArray epl = s.optJSONArray("episodes");
                        if (epl != null) {
                            for (int k = 0; k < epl.length(); k++) {
                                JSONObject e = epl.getJSONObject(k);
                                int n = e.optInt("episode", k + 1);
                                for (int j = 0; j < eps.length(); j++) {
                                    JSONObject ej = eps.getJSONObject(j);
                                    if (ej.optInt("episode", 0) == n) {
                                        e.put("qualities", ej.optJSONObject("qualities"));
                                        break;
                                    }
                                }
                            }
                        }
                        break;
                    }
                }
            }
        } catch (Exception ignored) { }
    }

    // при переключении перевода дотягиваем потоки его активного сезона,
    // чтобы появился выбор качества и сезон собрался сразу
    private void seedSeasonQs() {
        JSONArray ss = curTr.optJSONArray("seasons");
        if (ss != null) {
            for (int i = 0; i < ss.length(); i++) {
                JSONObject s = ss.optJSONObject(i);
                if (s.optInt("season", 0) == selSeason) {
                    JSONArray epl = s.optJSONArray("episodes");
                    if (epl != null && epl.length() > 0) {
                        JSONObject e0 = epl.optJSONObject(0);
                        JSONObject qs0 = e0 == null ? null : e0.optJSONObject("qualities");
                        if (qs0 != null && qs0.length() > 0) return;   // уже есть
                    }
                }
            }
        }
        new AsyncTask<Void, Void, JSONObject>() {
            String err;
            @Override protected JSONObject doInBackground(Void... a) {
                try {
                    String u = base + "/api/season?id=" + data.optString("id")
                            + "&tid=" + curTr.optInt("id", 0)
                            + "&season=" + selSeason
                            + "&url=" + Uri.encode(titleUrl);
                    return new JSONObject(Api.get(u));
                } catch (Exception e) { err = e.getMessage(); return null; }
            }
            @Override protected void onPostExecute(JSONObject o) {
                if (o != null) {
                    mergeSeasonQs(o, selSeason);
                    render();   // перерисовать: появятся качества и кнопка сезона
                }
            }
        }.execute();
    }

    private String findMx() {
        String[] cand = { MX, "com.mxtech.videoplayer.ad" };
        android.content.pm.PackageManager pm = getPackageManager();
        for (String c : cand) {
            try {
                if (pm.getLaunchIntentForPackage(c) != null) return c;
            } catch (Exception ignored) { }
        }
        return null;
    }

    // ---------- хелперы ----------
    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }

    private LinearLayout.LayoutParams lpWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private TextView tv(int color, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setTextColor(color);
        t.setTextSize(sp);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }

    private void sec(String text) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(1);
        LinearLayout.LayoutParams rlp = lpWrap();
        rlp.topMargin = dp(16);
        rlp.bottomMargin = dp(10);

        View bar = new View(this);
        bar.setBackgroundDrawable(roundBg(AC, AC, 2, 0));
        bar.setLayoutParams(new LinearLayout.LayoutParams(dp(4), dp(18)));
        row.addView(bar);

        TextView t = tv(TX, 15, true);
        t.setText(text);
        t.setPadding(dp(10), 0, 0, 0);
        row.addView(t);

        root.addView(row, rlp);
    }

    static android.graphics.drawable.Drawable roundBg(int fill, int stroke, int radius, int strokeW) {
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(radius * 1.6f);
        if (strokeW > 0) g.setStroke(strokeW, stroke);
        return g;
    }

    static class ImageViewWrap extends android.widget.ImageView {
        public ImageViewWrap(android.content.Context c) { super(c); }
    }
}