package ru.qrcatalogue.mobile;
import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.SystemClock;
import java.util.*;
import java.util.concurrent.*;

final class MdnsDiscovery {
    static List<Discovery.Server> find(Context context){
        List<Discovery.Server> result=new ArrayList<>();
        NsdManager manager=(NsdManager)context.getSystemService(Context.NSD_SERVICE);
        if(manager==null)return result;
        BlockingQueue<NsdServiceInfo> services=new LinkedBlockingQueue<>();
        NsdManager.DiscoveryListener listener=new NsdManager.DiscoveryListener(){
            public void onDiscoveryStarted(String type){}
            public void onDiscoveryStopped(String type){}
            public void onStartDiscoveryFailed(String type,int error){}
            public void onStopDiscoveryFailed(String type,int error){}
            public void onServiceFound(NsdServiceInfo info){services.offer(info);}
            public void onServiceLost(NsdServiceInfo info){}
        };
        try{
            manager.discoverServices("_qrcatalogue._tcp.",NsdManager.PROTOCOL_DNS_SD,listener);
            long deadline=SystemClock.elapsedRealtime()+4500;
            Set<String> seen=new HashSet<>();
            while(SystemClock.elapsedRealtime()<deadline && seen.size()<6){
                NsdServiceInfo info=services.poll(400,TimeUnit.MILLISECONDS);
                if(info==null||!seen.add(info.getServiceName()))continue;
                BlockingQueue<NsdServiceInfo> resolved=new LinkedBlockingQueue<>();
                manager.resolveService(info,new NsdManager.ResolveListener(){
                    public void onResolveFailed(NsdServiceInfo info,int error){}
                    public void onServiceResolved(NsdServiceInfo info){resolved.offer(info);}
                });
                NsdServiceInfo found=resolved.poll(1500,TimeUnit.MILLISECONDS);
                if(found==null||found.getHost()==null)continue;
                try{
                    Discovery.Server s=Discovery.verify("http://"+found.getHost().getHostAddress()+":"+found.getPort());
                    result.add(s);
                }catch(Exception ignored){}
            }
        }catch(Exception ignored){}
        finally{try{manager.stopServiceDiscovery(listener);}catch(Exception ignored){}}
        return result;
    }
}
