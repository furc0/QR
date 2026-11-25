const $=s=>document.querySelector(s),S={api:localStorage.getItem("qr_api")||"",token:sessionStorage.getItem("qr_token")||"",items:[],categories:[],viewer:null};
const url=p=>(S.api?S.api.replace(/\/+$/,""):"")+p;
async function req(p,o={}){const h=new Headers(o.headers||{});if(S.token)h.set("Authorization","Bearer "+S.token);if(o.body&&!(o.body instanceof FormData))h.set("Content-Type","application/json");const r=await fetch(url(p),{...o,headers:h});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"Ошибка "+r.status);return d}
function note(t){const x=$("#toast");x.textContent=t;x.classList.add("show");setTimeout(()=>x.classList.remove("show"),2800)}
function page(p){["catalog","settings","detail","categories"].forEach(x=>$("#"+x)?.classList.toggle("hidden",x!==p));$("#heading").textContent=({catalog:"Каталог деталей",settings:"Подключение",detail:"Карточка детали",categories:"Категории"})[p];document.querySelectorAll("nav button").forEach(x=>x.classList.toggle("active",x.dataset.page===p))}
function auth(first,msg){$("#logout").classList.add("hidden");$("#auth").classList.remove("hidden");$("#catalog").classList.add("hidden");["settings","detail","categories"].forEach(x=>$("#"+x)?.classList.add("hidden"));$("#name-label").classList.toggle("hidden",!first);$("#org-label").classList.toggle("hidden",!first);$("#auth-form").elements.display_name.required=first;$("#auth-form").elements.organization_name.required=first;$("#auth-form").dataset.first=String(first);$("#auth-title").textContent=first?"Создайте рабочую область":"Вход в QR";$("#auth-note").textContent=msg|| (first?"Создайте администратора и первую организацию.":"Введите email и пароль.");$("#auth-submit").textContent=first?"Создать":"Войти"}
async function start(){ $("#remote").value=S.api;$("#endpoint").textContent=url("/api");$("#mode").textContent=S.api?"Удалённый сервер":"Локальный сервер";try{if(S.token){await home();return}const s=await req("/api/setup-status");auth(s.setup_required)}catch(e){auth(false,"Сервер недоступен: "+e.message)}}
async function home(){const m=await req("/api/me");$("#org").textContent=m.organizations[0]?.name||"Организация";$("#auth").classList.add("hidden");$("#logout").classList.remove("hidden");await loadCategories();const id=location.pathname.match(/^\/parts\/([^/]+)/)?.[1];if(id){page("detail");await showDetail(id)}else{page("catalog");await load()}}
async function loadCategories(){S.categories=await req("/api/categories");const options=S.categories.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join("");const sel=$("#part-category");if(sel)sel.innerHTML='<option value="">Без категории</option>'+options;const detail=$("#detail-category");if(detail){const current=detail.value;detail.innerHTML='<option value="">Без категории</option>'+options;detail.value=current}const filter=$("#category-filter");if(filter){const current=filter.value;filter.innerHTML='<option value="">Все категории</option>'+options;filter.value=current}}

function esc(v){return String(v||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function load(){const q=encodeURIComponent($("#search").value),k=encodeURIComponent($("#filter").value),category=$("#category-filter").value;S.items=await req("/api/parts?q="+q+"&kind="+k);if(category)S.items=S.items.filter(p=>p.category_id===category);const cats=Object.fromEntries(S.categories.map(c=>[c.id,c.name]));$("#rows").innerHTML=S.items.map(p=>"<tr><td><b>"+esc(p.part_code)+"</b></td><td>"+esc(p.title)+"<small>"+esc(p.description)+"</small></td><td>"+(p.kind==="assembly"?"Сборка":"Деталь")+"</td><td>"+esc(cats[p.category_id]||"—")+"</td><td>"+esc(p.material||"—")+"</td><td>R"+p.revision+"</td><td><button data-id='"+p.id+"' class='open'>Открыть</button></td></tr>").join("")||'<tr><td colspan="7" class="empty">Записей пока нет. Создайте первую деталь или сборку.</td></tr>';$("#total").textContent=S.items.length;$("#parts").textContent=S.items.filter(x=>x.kind==="part").length;$("#assemblies").textContent=S.items.filter(x=>x.kind==="assembly").length;$("#count").textContent=S.items.length+" записей"}
$("#auth-form").onsubmit=async e=>{e.preventDefault();const first=e.currentTarget.dataset.first==="true",data=Object.fromEntries(new FormData(e.currentTarget));try{const r=await req(first?"/api/setup":"/api/login",{method:"POST",body:JSON.stringify(data)});S.token=r.token;sessionStorage.setItem("qr_token",r.token);await home()}catch(x){note(x.message)}};
$("#new").onclick=()=>$("#modal").classList.remove("hidden");$("#close").onclick=()=>$("#modal").classList.add("hidden");
$("#part-form").onsubmit=async e=>{e.preventDefault();try{const data=Object.fromEntries(new FormData(e.currentTarget));await req("/api/parts",{method:"POST",body:JSON.stringify(data)});$("#modal").classList.add("hidden");e.currentTarget.reset();await load();note("Карточка создана")}catch(x){note(x.message)}};
$("#rows").onclick=e=>{const id=e.target.dataset.id;if(id)location.href="/parts/"+id};
let timer;$("#search").oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>load().catch(x=>note(x.message)),250)};$("#filter").onchange=()=>load().catch(x=>note(x.message));$("#category-filter").onchange=()=>load().catch(x=>note(x.message));
$("#logout").onclick=()=>{S.token="";sessionStorage.removeItem("qr_token");auth(false)};
$("#connect").onclick=()=>{const v=$("#remote").value.trim().replace(/\/+$/,"");if(!/^https?:\/\//i.test(v))return note("Введите полный URL сервера");S.api=v;localStorage.setItem("qr_api",v);S.token="";sessionStorage.removeItem("qr_token");start()};
$("#local").onclick=()=>{localStorage.removeItem("qr_api");sessionStorage.removeItem("qr_token");location.href="/"};
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{page(b.dataset.page);if(b.dataset.page==="catalog")load().catch(x=>note(x.message));if(b.dataset.page==="categories")loadCategories().then(renderCategories).catch(x=>note(x.message))});
$("#category-create").onclick=async()=>{const name=$("#category-name").value.trim();if(!name)return note("Введите название категории");try{await req("/api/categories",{method:"POST",body:JSON.stringify({name})});$("#category-name").value="";await loadCategories();renderCategories();note("Категория создана")}catch(e){note(e.message)}};
function renderCategories(){$("#category-rows").innerHTML=S.categories.map(c=>'<tr><td>'+esc(c.name)+'</td><td>'+c.part_count+'</td><td><button data-rename="'+c.id+'">Переименовать</button> <button data-delete="'+c.id+'">Удалить</button></td></tr>').join("")||'<tr><td colspan="3">Категорий пока нет</td></tr>'}
$("#category-rows").onclick=async e=>{try{if(e.target.dataset.delete){if(!confirm("Удалить категорию? Детали сохранятся без категории."))return;await req("/api/categories/"+e.target.dataset.delete,{method:"DELETE"})}if(e.target.dataset.rename){const c=S.categories.find(x=>x.id===e.target.dataset.rename),name=prompt("Новое название категории",c.name);if(name===null)return;await req("/api/categories/"+c.id,{method:"PATCH",body:JSON.stringify({name})})}await loadCategories();renderCategories();await load()}catch(x){note(x.message)}};
$("#detail-category").onchange=async e=>{const id=location.pathname.split("/").pop();try{await req("/api/parts/"+id+"/category",{method:"PATCH",body:JSON.stringify({category_id:e.target.value||null})});note("Категория обновлена")}catch(x){note(x.message)}};
$("#share-copy").onclick=()=>{navigator.clipboard.writeText($("#share-link").value).then(()=>note("Ссылка скопирована")).catch(()=>note("Не удалось скопировать ссылку"))};
$("#detail-back").onclick=()=>location.href="/";
$("#models-list").onclick=async e=>{try{const previewId=e.target.dataset.modelPreview;if(previewId){const id=location.pathname.split("/").pop(),models=await req("/api/parts/"+id+"/models"),model=models.find(x=>x.id===previewId);if(model)await load3d(model);return}const mid=e.target.dataset.modelDownload;if(!mid)return;const r=await fetch(url("/api/models/"+mid+"/download"),{headers:{Authorization:"Bearer "+S.token}});if(!r.ok)throw Error("Не удалось скачать модель");const blob=await r.blob(),a=document.createElement("a"),u=URL.createObjectURL(blob);a.href=u;a.download=e.target.dataset.filename||"model";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}catch(x){note(x.message)}};
$("#model-upload").onsubmit=async e=>{e.preventDefault();const id=location.pathname.split("/").pop();try{await req("/api/parts/"+id+"/models",{method:"POST",body:new FormData(e.currentTarget)});e.currentTarget.reset();await showDetail(id);note("3D-модель загружена")}catch(x){note(x.message)}};
async function showDetail(id){const d=await req("/api/parts/"+id),p=d.part;$("#detail-title").textContent=p.title;$("#detail-code").textContent=p.part_code;$("#detail-meta").innerHTML="<div>Тип<b>"+(p.kind==="assembly"?"Сборка":"Деталь")+"</b></div><div>Материал<b>"+esc(p.material||"—")+"</b></div><div>Масса<b>"+esc(p.mass||"—")+"</b></div><div>Габариты<b>"+esc(p.dimensions||"—")+"</b></div><div>Ревизия<b>R"+p.revision+"</b></div>";$("#detail-description").textContent=p.description||"Описание не заполнено";const share=await req("/api/parts/"+id+"/share");$("#share-link").value=new URL(share.url,(S.api||location.origin)+"/").href;$("#detail-category").innerHTML='<option value="">Без категории</option>'+S.categories.map(c=>'<option value="'+esc(c.id)+'" '+(c.id===p.category_id?"selected":"")+'>'+esc(c.name)+'</option>').join("");$("#documents").innerHTML=d.documents.map(x=>"<li>"+esc(x.original_filename)+"</li>").join("")||"<li>Файлов пока нет</li>";const models=await req("/api/parts/"+id+"/models");$("#models-list").innerHTML=models.map(m=>'<li>'+esc(m.original_filename)+' ('+m.file_format+') — '+(["STL","OBJ","STEP","STP"].includes(m.file_format)?'<button type="button" data-model-preview="'+m.id+'">просмотр</button> ':"")+'<button type="button" data-model-download="'+m.id+'" data-filename="'+esc(m.original_filename)+'">скачать</button></li>').join("")||"<li>3D-модели не добавлены</li>";const preview=models.find(m=>["STL","OBJ"].includes(m.file_format));if(preview){$("#viewer-fit").disabled=false;await load3d(preview)}else{$("#viewer-fit").disabled=true;$("#viewer-note").textContent=models.length?"STEP/STP сохранён. Для просмотра необходима CAD-конвертация; исходный файл можно скачать.":"Загрузите STL или OBJ для интерактивного просмотра."}}
async function load3d(m){
 const noteEl=$("#viewer-note"),canvas=$("#model-view");$("#viewer-fit").disabled=true;$("#model-dimensions").textContent="";
 try{
  if(!window.THREE)throw Error("Локальная 3D-библиотека не загружена.");
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
   if(typeof window.occtimportjs!=="function")throw Error("Не загружен модуль OpenCascade. Проверьте файлы web/vendor/occt и повторите запуск.");
   const runtime=await fetch("/vendor/occt/occt-import-js.wasm",{method:"HEAD"});
   if(!runtime.ok)throw Error("STEP-просмотр не установлен. Подключите интернет и запустите install_step_runtime.py.");
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
start();
