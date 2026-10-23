package di.rezka;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.view.Gravity;
import android.view.SurfaceView;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.android.exoplayer2.SimpleExoPlayer;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.ExoPlaybackException;
import com.google.android.exoplayer2.source.MediaSource;
import com.google.android.exoplayer2.source.ProgressiveMediaSource;
import com.google.android.exoplayer2.source.dash.DashMediaSource;
import com.google.android.exoplayer2.source.dash.DefaultDashChunkSource;
import com.google.android.exoplayer2.source.TrackGroupArray;
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector;
import com.google.android.exoplayer2.trackselection.TrackSelectionArray;
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource;
import com.google.android.exoplayer2.upstream.HttpDataSource;

/**
 * Свой плеер ютуба: ExoPlayer 2.13.3 (core+dash, без ui-модуля — у PlayerView
 * свои R-ресурсы, в ручной сборке не склеиваются).
 * Жрёт MPD с сервиса, дорожки мёржит сам, ffmpeg/логины не участвуют.
 * Контролы: play/pause, ±10с, полоса перемотки, таймкоды. Тап по видео — пауза.
 * Параметр h в URL ограничивает максимальную высоту (выбор качества в меню).
 */
public class PlayerActivity extends Activity {
    private SimpleExoPlayer player;
    private SeekBar bar;
    private TextView times;
    private ImageButton playPause;
    private TextView errView;
    private boolean dragging;
    private String lastFmt = "";
    private final Handler timer = new Handler();
    private LinearLayout panel;
    private FitFrame fit;
    private final Handler ui = new Handler();
    private final Runnable hideUi = new Runnable() {
        @Override public void run() {
            if (panel != null && panel.getVisibility() == View.VISIBLE) {
                panel.animate().alpha(0f).setDuration(300).withEndAction(new Runnable() {
                    @Override public void run() {
                        if (panel.getAlpha() == 0f) panel.setVisibility(View.GONE);
                    }
                }).start();
            }
        }
    };
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (player != null) {
                long dur = player.getDuration();
                long pos = player.getCurrentPosition();
                if (!dragging && dur > 0) {
                    bar.setProgress((int) (pos * 1000 / dur));
                    times.setText(fmt(pos) + " / " + fmt(dur));
                }
                com.google.android.exoplayer2.Format vf = player.getVideoFormat();
                if (vf != null && vf.width > 0 && vf.height > 0 && fit != null) {
                    fit.setAspect(vf.width * vf.pixelWidthHeightRatio / vf.height);
                }
                String f = player.getVideoFormat() + "|" + player.getAudioFormat();
                if (!f.equals(lastFmt)) {
                    lastFmt = f;
                    android.util.Log.i("RezkaPlayer", "fmt " + f);
                }
                syncPlayIcon();
            }
            timer.postDelayed(this, 500);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN
                | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);

        String url = getIntent().getDataString();
        if (url == null) {
            Toast.makeText(this, R.string.no_url, Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        int maxH = 0;
        try {
            String hs = Uri.parse(url).getQueryParameter("h");
            if (hs != null) maxH = Integer.parseInt(hs);
        } catch (Exception ignored) { }
        final boolean prog = getIntent().getBooleanExtra("prog", false);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);   // фон по умолчанию — чёрный, серый слепит

        // Видео вписываем по аспекту (letterbox), иначе SurfaceView растянет кадр
        fit = new FitFrame(this);
        final SurfaceView sv = new SurfaceView(this);
        fit.addView(sv, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        root.addView(fit, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        errView = new TextView(this);
        errView.setTextColor(getResources().getColor(R.color.ub_orange_hi));
        errView.setTextSize(16);
        errView.setGravity(Gravity.CENTER);
        errView.setBackgroundResource(R.drawable.ub_err);
        errView.setPadding(dp(18), dp(14), dp(18), dp(14));
        errView.setVisibility(View.GONE);
        root.addView(errView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.CENTER));

        panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.HORIZONTAL);
        panel.setGravity(Gravity.CENTER_VERTICAL);
        panel.setBackgroundResource(R.drawable.ub_panel);
        panel.setPadding(dp(10), dp(8), dp(12), dp(8));

        final ImageButton rew = mediaBtn(android.R.drawable.ic_media_rew);
        rew.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { seekBy(-10000); showControls(); }
        });
        panel.addView(rew);

        playPause = mediaBtn(android.R.drawable.ic_media_pause);
        playPause.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (player != null) {
                    player.setPlayWhenReady(!player.getPlayWhenReady());
                    syncPlayIcon();
                }
                showControls();
            }
        });
        panel.addView(playPause);

        final ImageButton ff = mediaBtn(android.R.drawable.ic_media_ff);
        ff.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { seekBy(10000); showControls(); }
        });
        panel.addView(ff);

        times = new TextView(this);
        times.setTextColor(getResources().getColor(R.color.ub_text));
        times.setTextSize(14);
        times.setTypeface(android.graphics.Typeface.MONOSPACE);
        times.setText("00:00 / 00:00");
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        tlp.leftMargin = dp(8);
        tlp.rightMargin = dp(8);
        panel.addView(times, tlp);

        bar = new SeekBar(this);
        bar.setMax(1000);
        bar.setProgressDrawable(getResources().getDrawable(R.drawable.ub_seek));
        bar.setThumb(getResources().getDrawable(R.drawable.ub_thumb));
        bar.setThumbOffset(dp(7));
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        bar.setLayoutParams(blp);
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar sb, int p, boolean fromUser) {
                if (fromUser && player != null && player.getDuration() > 0) {
                    times.setText(fmt(player.getDuration() * p / 1000)
                            + " / " + fmt(player.getDuration()));
                }
            }
            @Override public void onStartTrackingTouch(SeekBar sb) {
                dragging = true;
                ui.removeCallbacks(hideUi);
            }
            @Override public void onStopTrackingTouch(SeekBar sb) {
                dragging = false;
                if (player != null && player.getDuration() > 0) {
                    player.seekTo(player.getDuration() * sb.getProgress() / 1000);
                }
                showControls();
            }
        });
        panel.addView(bar);

        FrameLayout.LayoutParams plp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        plp.leftMargin = dp(6);
        plp.rightMargin = dp(6);
        plp.bottomMargin = dp(6);
        root.addView(panel, plp);
        setContentView(root);

        DefaultHttpDataSource.Factory http = new DefaultHttpDataSource.Factory();
        http.setUserAgent("Rezka/1.0 (Linux; Android 4.2.2)");
        DefaultDashChunkSource.Factory dcsf = new DefaultDashChunkSource.Factory(http);
        DashMediaSource.Factory dsf = new DashMediaSource.Factory(dcsf, http);

        DefaultTrackSelector ts = new DefaultTrackSelector(this);
        if (maxH > 0) {
            ts.setParameters(ts.getParameters().buildUpon()
                    .setMaxVideoSize(Integer.MAX_VALUE, maxH)
                    .build());
        }

        player = new SimpleExoPlayer.Builder(this)
                .setTrackSelector(ts)
                .setMediaSourceFactory(dsf)
                .build();
        player.addListener(new Player.EventListener() {
            @Override public void onTracksChanged(TrackGroupArray groups,
                                                   TrackSelectionArray selections) {
                android.util.Log.i("RezkaPlayer", "tracks vfmt=" + player.getVideoFormat()
                        + " afmt=" + player.getAudioFormat());
            }
            @Override public void onPlayerError(final ExoPlaybackException e) {
                android.util.Log.e("RezkaPlayer", "player error", e);
                runOnUiThread(new Runnable() {
                    @Override public void run() { showError(describe(e)); }
                });
            }
        });
        player.setVideoSurfaceView(sv);
        if (prog) {
            // прогрессивный (muxed) mp4: один поток, ExoPlayer разбирает Mp4Extractor'ом
            MediaSource src = new ProgressiveMediaSource.Factory(http)
                    .createMediaSource(MediaItem.fromUri(Uri.parse(url)));
            player.setMediaSource(src);
        } else {
            player.setMediaItem(MediaItem.fromUri(Uri.parse(url)));
        }
        player.prepare();
        player.setPlayWhenReady(true);

        sv.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                player.setPlayWhenReady(!player.getPlayWhenReady());
                syncPlayIcon();
                showControls();
            }
        });
        timer.postDelayed(tick, 500);
        showControls();
    }

    /** Показать панель и перезапустить таймер автоскрытия. */
    private void showControls() {
        if (panel != null) {
            panel.setVisibility(View.VISIBLE);
            panel.setAlpha(1f);
        }
        ui.removeCallbacks(hideUi);
        ui.postDelayed(hideUi, 4000);
    }

    /** Контейнер видео: держит аспект кадра (letterbox), центрирует SurfaceView. */
    private class FitFrame extends FrameLayout {
        private float ar;

        FitFrame(android.content.Context c) { super(c); }

        void setAspect(float a) {
            if (a > 0 && Math.abs(a - ar) > 0.001f) {
                ar = a;
                requestLayout();
            }
        }

        @Override protected void onMeasure(int wSpec, int hSpec) {
            int w = MeasureSpec.getSize(wSpec);
            int h = MeasureSpec.getSize(hSpec);
            if (ar <= 0 || w <= 0 || h <= 0) {
                super.onMeasure(wSpec, hSpec);
                return;
            }
            int vw = w, vh = Math.round(w / ar);
            if (vh > h) { vh = h; vw = Math.round(h * ar); }
            int cw = MeasureSpec.makeMeasureSpec(vw, MeasureSpec.EXACTLY);
            int ch = MeasureSpec.makeMeasureSpec(vh, MeasureSpec.EXACTLY);
            for (int i = 0; i < getChildCount(); i++) getChildAt(i).measure(cw, ch);
            setMeasuredDimension(w, h);
        }

        @Override protected void onLayout(boolean changed, int l, int t, int r, int b) {
            int w = r - l, h = b - t;
            for (int i = 0; i < getChildCount(); i++) {
                View c = getChildAt(i);
                int cw = c.getMeasuredWidth(), ch = c.getMeasuredHeight();
                c.layout((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2);
            }
        }
    }

    private ImageButton mediaBtn(int res) {
        ImageButton b = new ImageButton(this);
        b.setImageResource(res);
        b.setBackgroundResource(R.drawable.ub_btn);
        b.setColorFilter(getResources().getColor(R.color.ub_text));
        b.setPadding(dp(9), dp(9), dp(9), dp(9));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(46), dp(46));
        lp.leftMargin = dp(2);
        lp.rightMargin = dp(2);
        b.setLayoutParams(lp);
        return b;
    }

    private void seekBy(long deltaMs) {
        if (player == null) return;
        long dur = player.getDuration();
        long target = player.getCurrentPosition() + deltaMs;
        if (target < 0) target = 0;
        if (dur > 0 && target > dur) target = dur;
        player.seekTo(target);
    }

    private void syncPlayIcon() {
        if (player == null || playPause == null) return;
        playPause.setImageResource(player.getPlayWhenReady()
                ? android.R.drawable.ic_media_pause
                : android.R.drawable.ic_media_play);
    }

    private void showError(String msg) {
        if (errView != null) {
            errView.setText(msg);
            errView.setVisibility(View.VISIBLE);
        }
        if (times != null) times.setText("00:00 / 00:00");
    }

    private String describe(ExoPlaybackException e) {
        Throwable c = e.getCause();
        if (c instanceof HttpDataSource.InvalidResponseCodeException) {
            int code = ((HttpDataSource.InvalidResponseCodeException) c).responseCode;
            if (code == 500) {
                return "Видео недоступно\n(удалено или закрыто на YouTube)";
            }
            return "Ошибка сети: HTTP " + code;
        }
        return "Ошибка воспроизведения\n"
                + (c != null ? c.getClass().getSimpleName() : "");
    }

    private String fmt(long ms) {
        if (ms < 0) ms = 0;
        long s = ms / 1000;
        long h = s / 3600, m = (s % 3600) / 60, sec = s % 60;
        if (h > 0) return String.format("%d:%02d:%02d", h, m, sec);
        return String.format("%02d:%02d", m, sec);
    }

    private int dp(int v) {
        return Math.round(getResources().getDisplayMetrics().density * v);
    }

    @Override
    protected void onDestroy() {
        timer.removeCallbacks(tick);
        ui.removeCallbacks(hideUi);
        if (player != null) {
            player.release();
            player = null;
        }
        super.onDestroy();
    }
}
