(()=>{
// Private browsing and managed browser profiles may deny storage access.
// Keep the current session usable in memory in that case.
function readSetting(storage, key) {
 try { return window[storage].getItem(key) || ""; }
 catch { return ""; }
}
function saveSetting(storage, key, value) {
 try {
  if (value) window[storage].setItem(key, value);
  else window[storage].removeItem(key);
 } catch { /* The active connection and token are also held in S. */ }
}
const $=s=>document.querySelector(s),S={api:readSetting("localStorage","qr_api"),token:readSetting("sessionStorage","qr_token"),items:[],categories:[],viewer:null,assemblyItems:[],selectedComponentId:null};
const url=p=>(S.api?S.api.replace(/\/+$/,""):"")+p;
function displayShare(share){
 const path=share.url+"?project="+encodeURIComponent(S.project);
 const base=share.origin||S.api||location.origin;
 $("#share-link").value=new URL(path,base).href;
 const alternatives=$("#lan-alternatives");
 alternatives.replaceChildren();
 for(const origin of share.lan_origins){
  const link=document.createElement("a");
  link.href=new URL(path,origin).href;
  link.textContent=link.href;
  const row=document.createElement("p");
  row.append("Адрес по IP: ",link);
  alternatives.append(row);
 }
 if(share.origin && !share.lan_origins.length){
  alternatives.textContent="Сетевой адрес не найден. Подключите сервер к локальной сети и перезапустите QR.";
 }
}
async function req(p,o={}){const token=S.token;const h=new Headers(o.headers||{});if(S.token)h.set("Authorization","Bearer "+S.token);if(o.body&&!(o.body instanceof FormData))h.set("Content-Type","application/json");const r=await fetch(url(p),{...o,headers:h,signal:o.signal || (o.method ? undefined : AbortSignal.timeout(15000))});const d=await r.json().catch(()=>({}));if(r.status===401 && token && token===S.token && document.body.classList.contains("signed-in")) endSession();if(!r.ok)throw Object.assign(Error(d.detail||"Ошибка "+r.status),{status:r.status});return d}
function note(t){const x=$("#toast");x.textContent=t;x.classList.add("show");setTimeout(()=>x.classList.remove("show"),2800)}
function page(p){if(!document.body.classList.contains("signed-in"))return;$("#boot").classList.add("hidden");["catalog","settings","detail","categories","members"].forEach(x=>$("#"+x)?.classList.toggle("hidden",x!==p));$("#heading").textContent=({catalog:"Каталог деталей",settings:"Подключение",detail:"Карточка детали",categories:"Категории",members:"Пользователи и проекты"})[p];document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x.dataset.page===p))}
function auth(first,msg){
 document.body.classList.remove("signed-in","choosing-server");
 $("#heading").textContent=first?"Создание рабочей области":"Вход в QR";
 const form=$("#auth-form");
 form.reset();
 form.elements.password.autocomplete=first?"new-password":"current-password";
 form.elements.password_confirmation.disabled=!first;
 form.elements.password_confirmation.required=first;
 $("#confirm-label").classList.toggle("hidden",!first);
 $("#project-picker").classList.add("hidden");
 $('[data-page="members"]').classList.add("hidden");
 $("#org").textContent="Рабочая область";
 $("#member-rows").replaceChildren();
 $("#create-user").reset();$("#boot").classList.add("hidden");$("#logout").classList.add("hidden");$("#auth").classList.remove("hidden");$("#catalog").classList.add("hidden");["settings","detail","categories","members"].forEach(x=>$("#"+x)?.classList.add("hidden"));$("#name-label").classList.toggle("hidden",!first);$("#org-label").classList.toggle("hidden",!first);$("#auth-form").elements.display_name.required=first;$("#auth-form").elements.organization_name.required=first;$("#auth-form").dataset.first=String(first);$("#auth-title").textContent=first?"Создайте рабочую область":"Вход в QR";$("#auth-note").textContent=msg|| (first?"Создайте администратора и первую организацию.":"Введите email и пароль.");$("#auth-submit").textContent=first?"Создать":"Войти"}
async function start(){
 $("#remote").value=S.api;
 $("#endpoint").textContent=url("/api");
 $("#mode").textContent=S.api?"Удалённый сервер":"Локальный сервер";
 try {
  if(S.token){
   try { await home(); return; }
   catch(error){
    if(error.status!==401)throw error;
    S.token="";
    saveSetting("sessionStorage","qr_token","");
   }
  }
  const status=await req("/api/setup-status");
  auth(status.setup_required);
 } catch(error){
  auth(false,"Не удалось открыть каталог. Проверьте подключение к серверу. "+error.message);
 }
}
async function home(){let m=await req("/api/me");
 const linked=new URLSearchParams(location.search).get("project");
 if(location.pathname.startsWith("/parts/") && linked && linked!==m.active_project_id){
  await selectProject(linked);
  m=await req("/api/me");
 }
 const active=m.organizations.find(project=>project.id===m.active_project_id);
 document.body.classList.remove("choosing-server");
 document.body.classList.add("signed-in");
 S.project=active.id;
 $("#org").textContent=m.user.display_name;
 $("#project-select").replaceChildren(...m.organizations.map(project=>new Option(project.name,project.id,false,project.id===active.id)));
 $("#project-picker").classList.remove("hidden");
 $('[data-page="members"]').classList.toggle("hidden",active.role!=="admin");
 $("#auth").classList.add("hidden");$("#logout").classList.remove("hidden");await loadCategories();const id=location.pathname.match(/^\/parts\/([^/]+)/)?.[1];if(id){page("detail");await showDetail(id)}else{page("catalog");await load()}}
async function loadCategories(){S.categories=await req("/api/categories");const options=S.categories.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join("");const sel=$("#part-category");if(sel)sel.innerHTML='<option value="">Без категории</option>'+options;const detail=$("#detail-category");if(detail){const current=detail.value;detail.innerHTML='<option value="">Без категории</option>'+options;detail.value=current}const filter=$("#category-filter");if(filter){const current=filter.value;filter.innerHTML='<option value="">Все категории</option>'+options;filter.value=current}}

function esc(v){return String(v||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function load(){const q=encodeURIComponent($("#search").value),k=encodeURIComponent($("#filter").value),category=$("#category-filter").value;S.items=await req("/api/parts?q="+q+"&kind="+k);if(category)S.items=S.items.filter(p=>p.category_id===category);const cats=Object.fromEntries(S.categories.map(c=>[c.id,c.name]));$("#rows").innerHTML=S.items.map(p=>"<tr><td><b>"+esc(p.part_code)+"</b></td><td>"+esc(p.title)+"<small>"+esc(p.description)+"</small></td><td>"+(p.kind==="assembly"?"Сборка":"Деталь")+"</td><td>"+esc(cats[p.category_id]||"—")+"</td><td>"+esc(p.material||"—")+"</td><td>R"+p.revision+"</td><td><button data-id='"+p.id+"' class='open'>Открыть</button></td></tr>").join("")||'<tr><td colspan="7" class="empty">Записей пока нет. Создайте первую деталь или сборку.</td></tr>';$("#total").textContent=S.items.length;$("#parts").textContent=S.items.filter(x=>x.kind==="part").length;$("#assemblies").textContent=S.items.filter(x=>x.kind==="assembly").length;$("#count").textContent=S.items.length+" записей"}
function passwordsMatch(form){
 const confirm=form.elements.password_confirmation;
 if(confirm.value===form.elements.password.value)return true;
 confirm.setCustomValidity("Пароли не совпадают. Повторите пароль.");
 confirm.reportValidity();
 confirm.setCustomValidity("");
 return false;
}
$("#auth-server").onclick=()=>{
 document.body.classList.add("choosing-server");
 $("#settings").classList.remove("hidden");
 $("#remote").focus();
};
$("#auth-form").onsubmit=async e=>{e.preventDefault();const first=e.currentTarget.dataset.first==="true",data=Object.fromEntries(new FormData(e.currentTarget));if(first && !passwordsMatch(e.currentTarget))return;delete data.password_confirmation;try{const r=await req(first?"/api/setup":"/api/login",{method:"POST",body:JSON.stringify(data)});S.token=r.token;saveSetting("sessionStorage","qr_token",r.token);await home()}catch(x){note(x.message)}};
$("#new").onclick=()=>$("#modal").classList.remove("hidden");$("#close").onclick=()=>$("#modal").classList.add("hidden");
$("#part-form").onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;try{const data=Object.fromEntries(new FormData(form));data.category_id=data.category_id||null;await req("/api/parts",{method:"POST",body:JSON.stringify(data)});$("#modal").classList.add("hidden");form.reset();await load();note("Карточка создана")}catch(x){note(x.message)}};
$("#rows").onclick=e=>{const id=e.target.dataset.id;if(id)location.href="/parts/"+id};
let timer;$("#search").oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>load().catch(x=>note(x.message)),250)};$("#filter").onchange=()=>load().catch(x=>note(x.message));$("#category-filter").onchange=()=>load().catch(x=>note(x.message));
function endSession(){
 document.body.classList.remove("signed-in","choosing-server");
 S.token="";
 saveSetting("sessionStorage","qr_token","");
 location.replace("/");
}
$("#logout").onclick=endSession;
window.addEventListener("pagehide",()=>document.body.classList.remove("signed-in"));
window.addEventListener("pageshow",event=>{if(event.persisted)location.reload();});
$("#connect").onclick=()=>{const v=$("#remote").value.trim().replace(/\/+$/,"");if(!/^https?:\/\//i.test(v))return note("Введите полный URL сервера");document.body.classList.remove("signed-in");S.api=v;saveSetting("localStorage","qr_api",v);S.token="";saveSetting("sessionStorage","qr_token","");start()};
$("#local").onclick=()=>{saveSetting("localStorage","qr_api","");saveSetting("sessionStorage","qr_token","");location.href="/"};
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{if(!document.body.classList.contains("signed-in"))return;page(b.dataset.page);if(b.dataset.page==="catalog")load().catch(x=>note(x.message));if(b.dataset.page==="members")refreshMembers().catch(x=>note(x.message));if(b.dataset.page==="categories")loadCategories().then(renderCategories).catch(x=>note(x.message))});
$("#category-create").onclick=async()=>{const name=$("#category-name").value.trim();if(!name)return note("Введите название категории");try{await req("/api/categories",{method:"POST",body:JSON.stringify({name})});$("#category-name").value="";await loadCategories();renderCategories();note("Категория создана")}catch(e){note(e.message)}};
function renderCategories(){$("#category-rows").innerHTML=S.categories.map(c=>'<tr><td>'+esc(c.name)+'</td><td>'+c.part_count+'</td><td><button data-rename="'+c.id+'">Переименовать</button> <button data-delete="'+c.id+'">Удалить</button></td></tr>').join("")||'<tr><td colspan="3">Категорий пока нет</td></tr>'}
$("#category-rows").onclick=async e=>{try{if(e.target.dataset.delete){if(!confirm("Удалить категорию? Детали сохранятся без категории."))return;await req("/api/categories/"+e.target.dataset.delete,{method:"DELETE"})}if(e.target.dataset.rename){const c=S.categories.find(x=>x.id===e.target.dataset.rename),name=prompt("Новое название категории",c.name);if(name===null)return;await req("/api/categories/"+c.id,{method:"PATCH",body:JSON.stringify({name})})}await loadCategories();renderCategories();await load()}catch(x){note(x.message)}};
$("#detail-category").onchange=async e=>{const id=location.pathname.split("/").pop();try{await req("/api/parts/"+id+"/category",{method:"PATCH",body:JSON.stringify({category_id:e.target.value||null})});note("Категория обновлена")}catch(x){note(x.message)}};
$("#share-copy").onclick=async()=>{
 const field=$("#share-link");
 try{
  if(navigator.clipboard){await navigator.clipboard.writeText(field.value);note("Ссылка скопирована");return}
 }catch{}
 field.focus();field.select();
 note(document.execCommand("copy")?"Ссылка скопирована":"Нажмите Ctrl+C, чтобы скопировать ссылку");
};
$("#documents").onclick=e=>{
 const button=e.target.closest("[data-doc]");
 if(button)downloadComponentFile("doc",button.dataset.doc,button.dataset.filename).catch(x=>note(x.message));
};
$("#detail-back").onclick=()=>location.href="/";
$("#models-list").onclick=async e=>{try{const previewId=e.target.dataset.modelPreview;if(previewId){const id=location.pathname.split("/").pop(),models=await req("/api/parts/"+id+"/models"),model=models.find(x=>x.id===previewId);if(model)await load3d(model);return}const mid=e.target.dataset.modelDownload;if(!mid)return;const r=await fetch(url("/api/models/"+mid+"/download"),{headers:{Authorization:"Bearer "+S.token}});if(!r.ok)throw Error("Не удалось скачать модель");const blob=await r.blob(),a=document.createElement("a"),u=URL.createObjectURL(blob);a.href=u;a.download=e.target.dataset.filename||"model";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}catch(x){note(x.message)}};
$("#model-upload").onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,id=location.pathname.split("/").pop();try{await req("/api/parts/"+id+"/models",{method:"POST",body:new FormData(form)});form.reset();await showDetail(id);note("3D-модель загружена")}catch(x){note(x.message)}};
function renderAssembly(items,isAssembly){
 const panel=$("#assembly-panel");
 if(!panel)return;
 panel.classList.toggle("hidden",!isAssembly);
 if(!isAssembly){S.assemblyItems=[];S.selectedComponentId=null;return}
 S.assemblyItems=Array.isArray(items)?items:[];
 const query=$("#assembly-search").value.trim().toLocaleLowerCase();
 const visible=S.assemblyItems.filter(x=>(x.part_code+" "+x.title).toLocaleLowerCase().includes(query));
 $("#assembly-count").textContent=query?visible.length+" из "+S.assemblyItems.length+" компонентов":S.assemblyItems.length+" компонентов";
 $("#assembly-rows").innerHTML=visible.map(x=>{
  const selected=x.component_part_id===S.selectedComponentId;
  const match=!!query;
  return '<tr data-component-id="'+esc(x.component_part_id)+'" class="'+(selected?"component-selected ": "")+(match?"component-match":"")+'"><td>'+esc(x.position_no||"—")+'</td><td><b>'+esc(x.part_code)+'</b></td><td>'+esc(x.title)+'</td><td>'+esc(x.quantity)+' '+esc(x.unit_code||"шт.")+'</td></tr>';
 }).join("")||'<tr><td colspan="4" class="empty">'+(query?"Совпадений не найдено":"В сборку пока не добавлены компоненты")+'</td></tr>';
 if(S.selectedComponentId&&!visible.some(x=>x.component_part_id===S.selectedComponentId)){
  $("#component-detail").innerHTML='<div class="empty">Выбранная деталь не соответствует текущему поиску. Очистите поиск, чтобы вернуться к ней.</div>';
 }
}
async function showComponentDetail(partId){
 S.selectedComponentId=partId;
 renderAssembly(S.assemblyItems,true);
 const box=$("#component-detail");
 box.innerHTML='<div class="empty">Загружаю данные компонента…</div>';
 try{
  const d=await req("/api/parts/"+encodeURIComponent(partId)),p=d.part;
  const models=await req("/api/parts/"+encodeURIComponent(partId)+"/models");
  const docs=(d.documents||[]).map(x=>'<li><span>'+esc(x.original_filename)+' <small>R'+esc(x.version_number)+'</small></span><button type="button" data-component-download-doc="'+esc(x.id)+'" data-filename="'+esc(x.original_filename)+'">Скачать</button></li>').join("");
  const modelRows=models.map(x=>'<li><span>'+esc(x.original_filename)+' <small>'+esc(x.file_format)+' · '+esc(x.size_bytes)+' байт</small></span><span><button type="button" data-component-download-model="'+esc(x.id)+'" data-filename="'+esc(x.original_filename)+'">Скачать</button> '+(["STL","OBJ","STEP","STP"].includes(x.file_format)?'<button type="button" data-component-preview="'+esc(x.id)+'">3D</button>':"")+'</span></li>').join("");
  box.innerHTML='<div class="component-detail-head"><small>ВЫБРАННЫЙ КОМПОНЕНТ</small><h3>'+esc(p.part_code)+'</h3><b>'+esc(p.title)+'</b></div><dl class="component-fields"><div><dt>Тип</dt><dd>'+(p.kind==="assembly"?"Сборка":"Деталь")+'</dd></div><div><dt>Материал</dt><dd>'+esc(p.material||"—")+'</dd></div><div><dt>Масса</dt><dd>'+esc(p.mass||"—")+'</dd></div><div><dt>Габариты</dt><dd>'+esc(p.dimensions||"—")+'</dd></div><div><dt>Ревизия</dt><dd>R'+esc(p.revision)+'</dd></div></dl><p class="component-description">'+esc(p.description||"Описание не заполнено")+'</p><h4>Документы ('+(d.documents||[]).length+')</h4><ul class="component-files">'+(docs||"<li>Документы не добавлены</li>")+'</ul><h4>3D-файлы ('+models.length+')</h4><ul class="component-files">'+(modelRows||"<li>3D-модели не добавлены</li>")+'</ul>';
 }catch(e){box.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}
}
async function downloadComponentFile(kind,id,name){
 const path=kind==="doc"?"/api/documents/"+encodeURIComponent(id)+"/download":"/api/models/"+encodeURIComponent(id)+"/download";
 const r=await fetch(url(path),{headers:{Authorization:"Bearer "+S.token}});
 if(!r.ok)throw Error("Не удалось скачать файл");
 const blob=await r.blob(),a=document.createElement("a"),u=URL.createObjectURL(blob);
 a.href=u;a.download=name||"file";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);
}
$("#assembly-search").oninput=()=>renderAssembly(S.assemblyItems,true);
$("#assembly-rows").onclick=e=>{
 const row=e.target.closest("tr[data-component-id]");if(!row)return;
 showComponentDetail(row.dataset.componentId).catch(x=>note(x.message));
};
$("#component-detail").onclick=async e=>{
 try{
  const doc=e.target.dataset.componentDownloadDoc,model=e.target.dataset.componentDownloadModel,preview=e.target.dataset.componentPreview;
  if(doc)await downloadComponentFile("doc",doc,e.target.dataset.filename);
  else if(model)await downloadComponentFile("model",model,e.target.dataset.filename);
  else if(preview){const models=await req("/api/parts/"+encodeURIComponent(S.selectedComponentId)+"/models"),m=models.find(x=>x.id===preview);if(m)await load3d(m)}
 }catch(x){note(x.message)}
};
async function showDetail(id){const d=await req("/api/parts/"+id),p=d.part;renderAssembly(d.bom,p.kind==="assembly");$("#detail-title").textContent=p.title;$("#detail-code").textContent=p.part_code;$("#detail-meta").innerHTML="<div>Тип<b>"+(p.kind==="assembly"?"Сборка":"Деталь")+"</b></div><div>Материал<b>"+esc(p.material||"—")+"</b></div><div>Масса<b>"+esc(p.mass||"—")+"</b></div><div>Габариты<b>"+esc(p.dimensions||"—")+"</b></div><div>Ревизия<b>R"+p.revision+"</b></div>";$("#detail-description").textContent=p.description||"Описание не заполнено";const share=await req("/api/parts/"+id+"/share");displayShare(share);$("#detail-category").innerHTML='<option value="">Без категории</option>'+S.categories.map(c=>'<option value="'+esc(c.id)+'" '+(c.id===p.category_id?"selected":"")+'>'+esc(c.name)+'</option>').join("");$("#documents").innerHTML=d.documents.map(x=>"<li>"+esc(x.original_filename)+' <button type="button" data-doc="'+esc(x.id)+'" data-filename="'+esc(x.original_filename)+'">Скачать</button></li>').join("")||"<li>Файлов пока нет</li>";const models=await req("/api/parts/"+id+"/models");$("#models-list").innerHTML=models.map(m=>'<li>'+esc(m.original_filename)+' ('+m.file_format+') — '+(["STL","OBJ","STEP","STP"].includes(m.file_format)?'<button type="button" data-model-preview="'+m.id+'">просмотр</button> ':"")+'<button type="button" data-model-download="'+m.id+'" data-filename="'+esc(m.original_filename)+'">скачать</button></li>').join("")||"<li>3D-модели не добавлены</li>";const preview=models.find(m=>["STL","OBJ"].includes(m.file_format));if(preview){$("#viewer-fit").disabled=false;await load3d(preview)}else{$("#viewer-fit").disabled=true;$("#viewer-note").textContent=models.length?"STEP/STP сохранён. Для просмотра необходима CAD-конвертация; исходный файл можно скачать.":"Загрузите STL или OBJ для интерактивного просмотра."}}
async function load3d(m){
 const noteEl=$("#viewer-note"),canvas=$("#model-view");$("#viewer-fit").disabled=true;$("#model-dimensions").textContent="";
 try{
  if(!window.THREE)throw Error("Локальная 3D-библиотека не загружена.");
  if(m.file_format==="STEP"||m.file_format==="STP"){
   if(typeof window.occtimportjs!=="function")throw Error("Не загружен модуль OpenCascade. Проверьте файлы web/vendor/occt и повторите запуск.");
   const runtime=await fetch("/vendor/occt/occt-import-js.wasm",{method:"HEAD"});
   if(!runtime.ok)throw Error("STEP-просмотр не установлен. Подключите интернет и запустите install_step_runtime.py.");
  }
  if(S.viewer){cancelAnimationFrame(S.viewer.frame);S.viewer.resizeObserver?.disconnect();S.viewer.scene.traverse(o=>{o.geometry?.dispose();if(Array.isArray(o.material))o.material.forEach(x=>x.dispose());else o.material?.dispose()});S.viewer.renderer.dispose();S.viewer.renderer.forceContextLoss();S.viewer=null}
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setSize(canvas.clientWidth,canvas.clientHeight,false);
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x101b23);
  const camera=new THREE.PerspectiveCamera(42,canvas.clientWidth/Math.max(canvas.clientHeight,1),.01,1e9);
  scene.add(new THREE.HemisphereLight(0xffffff,0x405060,2));
  const key=new THREE.DirectionalLight(0xffffff,2.2);key.position.set(1,2,3);scene.add(key);
  const fill=new THREE.DirectionalLight(0x9bbcff,.7);fill.position.set(-2,-1,-2);scene.add(fill);
  const response=await fetch(url("/api/models/"+m.id+"/download"),{headers:{Authorization:"Bearer "+S.token}});
  if(!response.ok)throw Error("Не удалось получить файл 3D-модели.");
  const buffer=await response.arrayBuffer();let object;
  if(m.file_format==="STL"){const geometry=new THREE.STLLoader().parse(buffer);geometry.computeVertexNormals();object=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x91bdb5,metalness:.28,roughness:.42,side:THREE.DoubleSide}))}
  else if(m.file_format==="OBJ"){object=new THREE.OBJLoader().parse(new TextDecoder().decode(buffer));object.traverse(node=>{if(node.isMesh){node.material=new THREE.MeshStandardMaterial({color:0x91bdb5,metalness:.2,roughness:.48,side:THREE.DoubleSide});node.geometry.computeVertexNormals()}})}
  else if(m.file_format==="STEP"||m.file_format==="STP"){
   noteEl.textContent="STEP: загружаю OpenCascade и строю триангуляцию. Для крупных моделей это может занять некоторое время…";
   S.occtPromise=S.occtPromise||window.occtimportjs({locateFile:path=>"/vendor/occt/"+path});
   const occt=await S.occtPromise;
   const cad=occt.ReadStepFile(new Uint8Array(buffer),{linearUnit:"millimeter",linearDeflectionType:"bounding_box_ratio",linearDeflection:.001,angularDeflection:.5});
   if(!cad||!cad.success||!Array.isArray(cad.meshes)||!cad.meshes.length)throw Error("OpenCascade не смог построить геометрию из STEP-файла.");
   object=new THREE.Group();
   for(const part of cad.meshes){
    const positions=part.attributes?.position?.array;if(!positions||positions.length<9)continue;
    const geometry=new THREE.BufferGeometry();geometry.setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
    const normals=part.attributes?.normal?.array;if(normals?.length===positions.length)geometry.setAttribute("normal",new THREE.Float32BufferAttribute(normals,3));
    let indices=part.index?.array;if(indices?.length){if(Array.isArray(indices[0]))indices=indices.flat();geometry.setIndex(indices)}
    if(!normals||normals.length!==positions.length)geometry.computeVertexNormals();
    const fallback=Array.isArray(part.color)&&part.color.length>=3?part.color:[0.57,0.74,0.71];
    const faces=Array.isArray(part.brep_faces)?part.brep_faces:[];
    const materials=[],materialByColor=new Map();
    const materialFor=colorValues=>{const values=Array.isArray(colorValues)&&colorValues.length>=3?colorValues:fallback,key=values.map(v=>Number(v).toFixed(5)).join(",");if(!materialByColor.has(key)){materialByColor.set(key,materials.length);materials.push(new THREE.MeshStandardMaterial({color:new THREE.Color(values[0],values[1],values[2]),metalness:.22,roughness:.48,side:THREE.DoubleSide}))}return materialByColor.get(key)};
    if(indices?.length&&faces.length){for(const face of faces){const first=Math.max(0,Number(face.first)||0),last=Math.max(first,Number(face.last)||first);geometry.addGroup(first*3,(last-first+1)*3,materialFor(face.color))}}
    if(!materials.length)materials.push(new THREE.MeshStandardMaterial({color:new THREE.Color(fallback[0],fallback[1],fallback[2]),metalness:.22,roughness:.48,side:THREE.DoubleSide}));
    const mesh=new THREE.Mesh(geometry,materials.length===1?materials[0]:materials);
    mesh.name=part.name||"STEP body";object.add(mesh);
   }
   if(!object.children.length)throw Error("STEP-файл прочитан, но триангуляция не содержит отображаемых тел.");
  }
  else throw Error("Формат этой 3D-модели не поддерживается для просмотра.");const bounds=new THREE.Box3().setFromObject(object),center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3()),maxDim=Math.max(size.x,size.y,size.z);
  if(!Number.isFinite(maxDim)||maxDim<=0)throw Error("В модели нет корректной геометрии.");
  object.position.sub(center);scene.add(object);const dimensionUnit=(m.file_format==="STEP"||m.file_format==="STP")?"мм (выход OpenCascade)":"единицы исходной модели — не определены";$("#model-dimensions").textContent="Габариты модели: "+size.x.toFixed(2)+" × "+size.y.toFixed(2)+" × "+size.z.toFixed(2)+" "+dimensionUnit;
  const grid=new THREE.GridHelper(maxDim*4,20,0x38505b,0x263943);grid.position.y=-size.y/2;scene.add(grid);
  const target=new THREE.Vector3(0,0,0),radius=maxDim/2;
  const fit=()=>{const distance=(radius/Math.sin(THREE.MathUtils.degToRad(camera.fov/2)))*1.25;camera.position.copy(target).add(new THREE.Vector3(distance*.9,distance*.72,distance*1.05));camera.near=Math.max(radius/10000,.001);camera.far=Math.max(radius*100,1000);camera.updateProjectionMatrix();camera.lookAt(target)};
  fit();let pointer=null,mode="rotate",theta=0,phi=0,distance=camera.position.distanceTo(target);
  const syncAngles=()=>{const spherical=new THREE.Spherical().setFromVector3(camera.position.clone().sub(target));theta=spherical.theta;phi=spherical.phi;distance=spherical.radius};syncAngles();
  const updateCamera=()=>{camera.position.copy(target).add(new THREE.Vector3().setFromSpherical(new THREE.Spherical(distance,phi,theta)));camera.lookAt(target)};
  canvas.oncontextmenu=e=>e.preventDefault();
  canvas.onpointerdown=e=>{mode=e.button===2||e.button===1?"pan":"rotate";pointer={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId)};
  canvas.onpointerup=()=>pointer=null;canvas.onpointercancel=()=>pointer=null;
  canvas.onpointermove=e=>{if(!pointer)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;pointer={x:e.clientX,y:e.clientY};if(mode==="rotate"){theta-=dx*.008;phi=Math.max(.02,Math.min(Math.PI-.02,phi-dy*.008))}else{const scale=distance/Math.max(canvas.clientHeight,1)*1.4;const right=new THREE.Vector3().setFromMatrixColumn(camera.matrix,0),up=new THREE.Vector3().setFromMatrixColumn(camera.matrix,1);target.addScaledVector(right,-dx*scale).addScaledVector(up,dy*scale)}updateCamera()};
  canvas.onwheel=e=>{e.preventDefault();distance=Math.max(radius*.03,Math.min(radius*100,distance*Math.exp(e.deltaY*.001)));updateCamera()};
  $("#viewer-fit").onclick=()=>{target.set(0,0,0);fit();syncAngles()};
  const resize=()=>{const w=canvas.clientWidth,h=Math.max(canvas.clientHeight,1);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()};
  const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas);
  const state={renderer,scene,resizeObserver,frame:0};S.viewer=state;
  $("#viewer-fit").disabled=false;noteEl.textContent="ЛКМ — вращение · ПКМ/средняя кнопка — перемещение · Колесо — масштаб · Вписать — показать модель целиком. STL/OBJ могут не содержать единиц измерения: проверяйте масштаб по КД.";
  const draw=()=>{if(S.viewer!==state)return;renderer.render(scene,camera);state.frame=requestAnimationFrame(draw)};draw();
 }catch(error){noteEl.textContent=error.message;note(error.message)}
}
async function selectProject(id){
 const result=await req("/api/projects/"+encodeURIComponent(id)+"/select",{method:"POST"});
 S.token=result.token;
 saveSetting("sessionStorage","qr_token",S.token);
}

async function openProject(id){
 await selectProject(id);
 history.replaceState(null,"","/");
 if(readSetting("sessionStorage","qr_token")===S.token){ location.reload(); return; }
 $("#search").value="";
 $("#filter").value="";
 $("#category-filter").value="";
 await home();
}

$("#project-select").onchange=async event=>{
 const picker=event.currentTarget;
 picker.disabled=true;
 try { await openProject(picker.value); }
 catch(error){ picker.value=S.project; note(error.message); }
 finally { picker.disabled=false; }
};

async function refreshMembers(){
 const users=await req("/api/project/users");
 $("#member-rows").replaceChildren(...users.map(user=>{
  const row=document.createElement("tr");
  for(const value of [user.display_name,user.email,user.role==="admin"?"Администратор":"Участник"]){
   row.insertCell().textContent=value;
  }
  return row;
 }));
}

for(const [selector,path] of [["#create-user","/api/project/users"],["#add-member","/api/project/members"],["#create-project","/api/projects"]]){
 $(selector).onsubmit=async event=>{
  event.preventDefault();
  const form=event.currentTarget, button=form.querySelector("button");
  if(selector==="#create-user" && !passwordsMatch(form))return;
  const data=Object.fromEntries(new FormData(form));
  delete data.password_confirmation;
  button.disabled=true;
  try {
   const result=await req(path,{method:"POST",body:JSON.stringify(data)});
   form.reset();
   if(selector==="#create-project") await openProject(result.id);
   else { await refreshMembers(); note("Пользователь добавлен в проект"); }
  } catch(error){ note(error.message); }
  finally { button.disabled=false; }
 };
}
start();
})();
