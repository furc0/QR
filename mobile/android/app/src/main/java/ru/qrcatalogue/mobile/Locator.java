package ru.qrcatalogue.mobile;

import java.net.URI;
import java.util.Locale;

final class Locator {
    private Locator() {}
    static String path(String raw) {
        String value = raw.trim();
        if (value.matches("[0-9]{1,18}") && !value.matches("0+")) return "/n/" + value;
        if (value.startsWith("QR:")) return path(value.substring(3));
        // Legacy links are resolved only on the paired server, never on the scanned host.
        try {
            URI uri = new URI(value);
            if (!("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme()))) return null;
            String p = uri.getPath();
            if (p == null) return null;
            if (p.matches("/n/[0-9]{1,18}") && !p.substring(3).matches("0+")) return p;
            if (p.matches("/s/[A-Za-z0-9_-]{1,100}") || p.matches("/parts/[0-9a-fA-F-]{36}")) return p;
        } catch (Exception ignored) {}
        return null;
    }
    static String origin(String raw) throws Exception {
        String value = raw.trim();
        if (!value.contains("://")) value = "http://" + value;
        URI u = new URI(value);
        String scheme = u.getScheme().toLowerCase(Locale.ROOT);
        if (!scheme.equals("http") && !scheme.equals("https")) throw new IllegalArgumentException("HTTP/HTTPS");
        String host = u.getHost();
        if (host == null || u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null ||
            !(u.getPath().isEmpty() || u.getPath().equals("/")) || u.getPort()==0 || u.getPort()>65535)
            throw new IllegalArgumentException("Введите адрес сервера без пути");
        int port = u.getPort();
        if (scheme.equals("http")) {
            // Plain HTTP is restricted to explicit local/private IPv4 (including VPN CGNAT).
            String[] octets = host.split("\\.");
            if (octets.length!=4) throw new IllegalArgumentException("Для HTTP используйте локальный IPv4");
            int[] n = new int[4];
            for(int i=0;i<4;i++) { if(!octets[i].matches("[0-9]{1,3}")) throw new IllegalArgumentException("IPv4"); n[i]=Integer.parseInt(octets[i]); if(n[i]>255) throw new IllegalArgumentException("IPv4"); }
            if (!(n[0]==10 || (n[0]==172 && n[1]>=16 && n[1]<=31) || (n[0]==192 && n[1]==168) || (n[0]==100 && n[1]>=64 && n[1]<=127)))
                throw new IllegalArgumentException("HTTP разрешён только для локальной сети/VPN");
            if(port<0)port=8765;
        }
        if ((scheme.equals("https") && port==443) || (scheme.equals("http") && port==80)) port=-1;
        return new URI(scheme,null,host,port,null,null,null).toString();
    }
}
