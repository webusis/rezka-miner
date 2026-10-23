package di.rezka;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/** Простейший HTTP-клиент на HttpURLConnection. */
public class Api {

    public static String get(String urlStr) throws Exception {
        return get(urlStr, 60000);
    }

    public static String get(String urlStr, int timeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(urlStr).openConnection();
        c.setConnectTimeout(timeoutMs);
        c.setReadTimeout(timeoutMs);
        c.setRequestProperty("User-Agent", "Rezka/1.0");
        int code = c.getResponseCode();
        InputStream in = (code >= 400) ? c.getErrorStream() : c.getInputStream();
        if (in == null) throw new Exception("HTTP " + code);
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line).append('\n');
        r.close();
        c.disconnect();
        if (code >= 400) throw new Exception("HTTP " + code);
        return sb.toString();
    }
}