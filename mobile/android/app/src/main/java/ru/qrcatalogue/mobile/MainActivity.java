package ru.qrcatalogue.mobile;

import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.webkit.*;
import android.widget.*;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends AppCompatActivity {
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final ExecutorService downloads=Executors.newSingleThreadExecutor();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private android.content.SharedPreferences prefs;
    private TextView status;
    private EditText number;
    private WebView web;
    private LinearLayout root;
    private String origin="", pinned="", pending="/";
    private boolean busy=false, online=false, active=false, destroyed=false;
    private int epoch=0;
    private Download pendingDownload;
    private ValueCallback<Uri[]> fileCallback;
    private final ActivityResultLauncher<ScanOptions> scanner=registerForActivityResult(new ScanContract(),result->{
        if(result.getContents()!=null)openCode(result.getContents());
    });
    private final ActivityResultLauncher<String> saveFile=registerForActivityResult(new ActivityResultContracts.CreateDocument("application/octet-stream"),uri->{
        Download d=pendingDownload;pendingDownload=null;
        if(uri!=null && d!=null)downloads.execute(()->download(d,uri));
    });
    private final ActivityResultLauncher<String[]> chooseFile=registerForActivityResult(new ActivityResultContracts.OpenDocument(),uri->{
        if(fileCallback!=null){fileCallback.onReceiveValue(uri==null?null:new Uri[]{uri});fileCallback=null;}
    });
    private final Runnable poll=new Runnable(){@Override public void run(){
        if(!active||destroyed)return;
        if(!busy)reconnect(false);
        handler.postDelayed(this,12000);
    }};

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        prefs=getSharedPreferences("qr_mobile",MODE_PRIVATE);
        origin=prefs.getString("origin","");pinned=prefs.getString("catalogue","");
        if(state!=null)pending=state.getString("pending","/");
        root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(8),dp(6),dp(8),0);
        status=new TextView(this);status.setTextSize(14);status.setPadding(dp(6),dp(6),dp(6),dp(6));root.addView(status);
        LinearLayout inputRow=new LinearLayout(this);
        number=new EditText(this);number.setSingleLine(true);number.setHint("Номер карточки");number.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        inputRow.addView(number,new LinearLayout.LayoutParams(0,-2,1));
        inputRow.addView(button("Открыть",()->openCode(number.getText().toString())));
        inputRow.addView(button("Сканер",()->{
            ScanOptions options=new ScanOptions();options.setDesiredBarcodeFormats(Arrays.asList("QR_CODE","DATA_MATRIX"));
            options.setPrompt("Наведите камеру на QR или Data Matrix");options.setBeepEnabled(false);options.setOrientationLocked(false);
            scanner.launch(options);
        }));root.addView(inputRow);
        LinearLayout actions=new LinearLayout(this);
        actions.addView(button("Каталог",()->openPath("/")),new LinearLayout.LayoutParams(0,-2,1));
        actions.addView(button("Поиск ПК",()->reconnect(true)),new LinearLayout.LayoutParams(0,-2,1));
        actions.addView(button("Сервер",this::settings),new LinearLayout.LayoutParams(0,-2,1));
        root.addView(actions);setContentView(root);makeWeb();
        showStatus("Нет соединения. Найдите ПК или укажите адрес.",false);
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private Button button(String text,Runnable run){Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setOnClickListener(v->run.run());return b;}
    private void showStatus(String text,boolean ok){status.setText(text);status.setTextColor(ok?Color.rgb(27,130,69):Color.rgb(183,91,25));}
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    @Override protected void onResume(){super.onResume();active=true;handler.removeCallbacks(poll);handler.post(poll);}
    @Override protected void onPause(){active=false;handler.removeCallbacks(poll);super.onPause();}
    @Override protected void onSaveInstanceState(Bundle b){b.putString("pending",pending);super.onSaveInstanceState(b);}
    @Override protected void onDestroy(){destroyed=true;epoch++;handler.removeCallbacksAndMessages(null);worker.shutdownNow();downloads.shutdownNow();if(web!=null){root.removeView(web);web.destroy();}super.onDestroy();}

    private void makeWeb(){
        if(web!=null){root.removeView(web);web.destroy();}
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings s=web.getSettings();
        s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setUserAgentString(s.getUserAgentString()+" QRMobile/1");
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);s.setJavaScriptCanOpenWindowsAutomatically(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView w,WebResourceRequest r){return !sameOrigin(r.getUrl());}
            @Override public WebResourceResponse shouldInterceptRequest(WebView w,WebResourceRequest r){
                String scheme=r.getUrl().getScheme();
                if(("http".equals(scheme)||"https".equals(scheme))&&!sameOrigin(r.getUrl()))
                    return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public void onReceivedError(WebView w,WebResourceRequest r,WebResourceError e){
                if(r.isForMainFrame()){online=false;showStatus("Связь с ПК потеряна: "+e.getDescription(),false);}
            }
            @Override public void onReceivedSslError(WebView w,SslErrorHandler h,android.net.http.SslError e){h.cancel();online=false;showStatus("Ошибка сертификата HTTPS",false);}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView w,ValueCallback<Uri[]> cb,FileChooserParams p){
                if(fileCallback!=null)fileCallback.onReceiveValue(null);
                fileCallback=cb;chooseFile.launch(new String[]{"*/*"});return true;
            }
        });
        if(!origin.isEmpty() && WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)){
            WebViewCompat.addWebMessageListener(web,"QRNative",Collections.singleton(origin),(view,message,source,isMain,reply)->{
                if(isMain&&sameOrigin(source))receiveDownload(message.getData());
            });
        }
    }
    private boolean sameOrigin(Uri u){
        if(origin.isEmpty())return false;
        try{
            Uri o=Uri.parse(origin);int p=u.getPort(),q=o.getPort();
            if(p<0)p="https".equals(u.getScheme())?443:80;
            if(q<0)q="https".equals(o.getScheme())?443:80;
            return Objects.equals(u.getScheme(),o.getScheme())&&Objects.equals(u.getHost(),o.getHost())&&p==q;
        }catch(Exception e){return false;}
    }
    private void openCode(String raw){
        String path=Locator.path(raw);
        if(path==null){toast("Нужен номер карточки, QR или Data Matrix из каталога QR.");return;}
        if(path.startsWith("/n/"))number.setText(path.substring(3));
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(number.getWindowToken(),0);
        openPath(path);
    }
    private void openPath(String path){
        pending=path;
        if(online){web.loadUrl(origin+pending);}
        else{showStatus("Поиск сервера для открытия карточки…",false);reconnect(true);}
    }
    private void reconnect(boolean force){
        if(busy||destroyed)return;
        busy=true;final int ticket=epoch;
        final String previous=origin, expected=pinned;
        if(force||!online)showStatus("Поиск сервера QR…",false);
        worker.execute(()->{
            Discovery.Server verified=null;
            if(!previous.isEmpty())try{verified=Discovery.verify(previous);}catch(Exception ignored){}
            if(verified!=null&&!expected.isEmpty()&&expected.equals(verified.id)){
                final Discovery.Server result=verified;
                runOnUiThread(()->{if(ticket!=epoch||destroyed)return;busy=false;accept(result);});return;
            }
            WifiManager.MulticastLock lock=null;
            List<Discovery.Server> found;
            try{
                WifiManager wifi=(WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);
                if(wifi!=null){lock=wifi.createMulticastLock("qr-discovery");lock.setReferenceCounted(false);lock.acquire();}
                found=Discovery.find();
            }catch(Exception e){found=new ArrayList<>();}
            finally{if(lock!=null&&lock.isHeld())lock.release();}
            if(verified!=null){boolean exists=false;for(Discovery.Server x:found)if(x.id.equals(verified.id))exists=true;if(!exists)found.add(verified);}
            final List<Discovery.Server> candidates=found;
            runOnUiThread(()->{
                if(ticket!=epoch||destroyed)return;busy=false;
                for(Discovery.Server x:candidates)if(!expected.isEmpty()&&expected.equals(x.id)){accept(x);return;}
                online=false;
                showStatus("Нет связи с сохранённым ПК. Проверьте сеть и брандмауэр.",false);
                if(!candidates.isEmpty()&&(force||expected.isEmpty()))pick(candidates);
                else if(force)toast("Сервер не обнаружен. Укажите IP:порт в разделе «Сервер».");
            });
        });
    }
    private void pick(List<Discovery.Server> servers){
        String[] names=new String[servers.size()];for(int i=0;i<names.length;i++)names[i]=servers.get(i).toString();
        new AlertDialog.Builder(this).setTitle("Выберите свой компьютер").setItems(names,(d,i)->confirm(servers.get(i))).setNegativeButton("Отмена",null).show();
    }
    private void confirm(Discovery.Server s){
        String message=s.origin+"\nID базы: "+s.id+"\nСверьте ID с окном QR на ПК.";
        if(s.origin.startsWith("http://"))message+="\nHTTP не шифруется. Используйте только доверенную локальную сеть.";
        if(!pinned.isEmpty()&&!pinned.equals(s.id))message+="\nВНИМАНИЕ: другая база. Те же номера могут обозначать другие детали.";
        new AlertDialog.Builder(this).setTitle("Подтвердить сервер").setMessage(message).setPositiveButton("Подключить",(d,w)->{
            epoch++;busy=false;online=false;pinned=s.id;origin=s.origin;
            prefs.edit().putString("catalogue",pinned).putString("origin",origin).apply();
            makeWeb();accept(s);
        }).setNegativeButton("Отмена",null).show();
    }
    private void accept(Discovery.Server s){
        boolean change=!s.origin.equals(origin), reload=!online||change;
        if(change){origin=s.origin;prefs.edit().putString("origin",origin).apply();makeWeb();}
        online=true;showStatus("Подключено: "+origin+"  •  "+s.id.substring(0,8),true);
        if(reload)web.loadUrl(origin+pending);
    }
    private void settings(){
        EditText field=new EditText(this);field.setSingleLine(true);field.setHint("192.168.43.123:8765");field.setText(origin);
        new AlertDialog.Builder(this).setTitle("Подключение к ПК").setMessage("Адрес из окна QR на компьютере. Можно указать IP VPN или HTTPS.").setView(field)
          .setPositiveButton("Проверить",(d,w)->manual(field.getText().toString()))
          .setNeutralButton("Забыть ПК",(d,w)->{
              epoch++;busy=false;online=false;origin="";pinned="";pending="/";prefs.edit().clear().apply();makeWeb();showStatus("Сервер сброшен",false);
          }).setNegativeButton("Отмена",null).show();
    }
    private void manual(String raw){
        epoch++;final int ticket=epoch;busy=true;showStatus("Проверка адреса…",false);
        worker.execute(()->{
            try{Discovery.Server s=Discovery.verify(raw);runOnUiThread(()->{if(ticket!=epoch||destroyed)return;busy=false;if(pinned.equals(s.id))accept(s);else confirm(s);});}
            catch(Exception e){runOnUiThread(()->{if(ticket!=epoch||destroyed)return;busy=false;showStatus("Ошибка подключения: "+e.getMessage(),false);});}
        });
    }
    private static final class Download{
        final String origin,path,filename,token;
        Download(String o,String p,String f,String t){origin=o;path=p;filename=f;token=t;}
    }
    private void receiveDownload(String raw){
        if(pendingDownload!=null||!online)return;
        try{
            JSONObject j=new JSONObject(raw);
            String path=j.getString("path"),token=j.getString("token"),name=j.optString("filename","file");
            if(!path.matches("/api/(documents|models)/[A-Za-z0-9_-]+/download")&&!path.matches("/api/mobile/parts/[A-Za-z0-9_-]+/label/(qr|datamatrix)/(svg|png|pdf)"))throw new IllegalArgumentException();
            if(token.isEmpty()||token.length()>8192||token.contains("\r")||token.contains("\n"))throw new IllegalArgumentException();
            name=name.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_");if(name.isEmpty())name="file";
            pendingDownload=new Download(origin,path,name,token);saveFile.launch(name);
        }catch(Exception e){pendingDownload=null;toast("Невозможно подготовить файл");}
    }
    private void download(Download d,Uri uri){
        HttpURLConnection c=null;
        try{
            c=(HttpURLConnection)new URL(d.origin+d.path).openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(5000);c.setReadTimeout(30000);
            c.setRequestProperty("Authorization","Bearer "+d.token);
            if(c.getResponseCode()!=200)throw new IOException("HTTP "+c.getResponseCode());
            long length=c.getContentLengthLong();if(length>300L*1024*1024)throw new IOException("Файл превышает 300 МБ");
            try(InputStream in=c.getInputStream();OutputStream out=getContentResolver().openOutputStream(uri,"w")){
                if(out==null)throw new IOException("Нет доступа к файлу");
                byte[] b=new byte[65536];int n;long total=0;
                while((n=in.read(b))!=-1){total+=n;if(total>300L*1024*1024)throw new IOException("Файл превышает 300 МБ");out.write(b,0,n);}
            }
            runOnUiThread(()->toast("Файл сохранён: "+d.filename));
        }catch(Exception e){
            try{android.provider.DocumentsContract.deleteDocument(getContentResolver(),uri);}catch(Exception ignored){}
            runOnUiThread(()->toast("Ошибка скачивания: "+e.getMessage()));
        }finally{if(c!=null)c.disconnect();}
    }
    @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
}
