package ru.qrcatalogue.mobile;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.JSONObject;

final class Discovery {
    static final int PORT = 8764;
    static final class Server {
        final String origin, id;
        Server(String origin, String id){this.origin=origin;this.id=id;}
        @Override public String toString(){return origin+"  ["+id.substring(0,8)+"]";}
    }
    static Server verify(String candidate) throws Exception {
        String origin=Locator.origin(candidate);
        HttpURLConnection c=(HttpURLConnection)new URL(origin+"/api/mobile/info").openConnection();
        c.setConnectTimeout(1800);c.setReadTimeout(1800);c.setInstanceFollowRedirects(false);
        try {
            if(c.getResponseCode()!=200) throw new IOException("Сервер QR Mobile не найден");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream in=c.getInputStream()){
                byte[] b=new byte[1024];int n;
                while((n=in.read(b))!=-1){if(bytes.size()+n>8192)throw new IOException("Ответ слишком большой");bytes.write(b,0,n);}
            }
            JSONObject j=new JSONObject(bytes.toString("UTF-8"));
            if(!"qr".equals(j.optString("service"))||j.optInt("protocol")!=1)throw new IOException("Несовместимый сервер");
            String id=UUID.fromString(j.getString("catalogue_id")).toString();
            return new Server(origin,id);
        } finally {c.disconnect();}
    }
    static List<Server> find() {
        Map<String,Server> results=new LinkedHashMap<>();
        try(DatagramSocket socket=new DatagramSocket(null)){
            socket.setReuseAddress(true);socket.bind(new InetSocketAddress(PORT));socket.setBroadcast(true);socket.setSoTimeout(350);
            Set<InetAddress> broadcasts=new HashSet<>();
            broadcasts.add(InetAddress.getByName("255.255.255.255"));
            Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();
            if(interfaces!=null)while(interfaces.hasMoreElements()){
                NetworkInterface ni=interfaces.nextElement();
                if(!ni.isUp()||ni.isLoopback())continue;
                for(InterfaceAddress ia:ni.getInterfaceAddresses())if(ia.getBroadcast()!=null)broadcasts.add(ia.getBroadcast());
            }
            byte[] query="QR_DISCOVER_V1".getBytes(StandardCharsets.US_ASCII);
            long deadline=android.os.SystemClock.elapsedRealtime()+4000;
            long next=0;
            Set<String> checked=new HashSet<>();
            while(android.os.SystemClock.elapsedRealtime()<deadline){
                long now=android.os.SystemClock.elapsedRealtime();
                if(now>=next){for(InetAddress address:broadcasts)try{socket.send(new DatagramPacket(query,query.length,address,PORT));}catch(IOException ignored){} next=now+1000;}
                byte[] buf=new byte[512];DatagramPacket p=new DatagramPacket(buf,buf.length);
                try {
                    socket.receive(p);
                    JSONObject j=new JSONObject(new String(buf,0,p.getLength(),StandardCharsets.UTF_8));
                    if(!"qr".equals(j.optString("service"))||j.optInt("protocol")!=1)continue;
                    int port=j.getInt("port");if(port<1||port>65535)continue;
                    String candidate="http://"+p.getAddress().getHostAddress()+":"+port;
                    if(!checked.add(candidate)||checked.size()>12)continue;
                    Server s=verify(candidate);
                    if(s.id.equals(j.optString("catalogue_id")))results.putIfAbsent(s.id,s);
                }catch(Exception ignored){}
            }
        }catch(Exception ignored){}
        return new ArrayList<>(results.values());
    }
}
