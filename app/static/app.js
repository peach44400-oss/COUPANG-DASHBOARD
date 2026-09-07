/* ===========================================================
   app.js — 셸/라우터/콘솔 날짜 UI/업로드/예측/업데이트 + 대시보드 부트스트랩
   (검증된 대시보드 렌더 로직은 dashboard.js 에 verbatim. 여기선 그 위의 얇은 셸만.)
   =========================================================== */
(function(){
"use strict";
const $=function(id){return document.getElementById(id);};
const el=function(sel,root){return (root||document).querySelector(sel);};

/* ---------- fetch 래퍼 ---------- */
async function api(path, opts){
  const r=await fetch(path, opts);
  const ct=r.headers.get('content-type')||'';
  if(!r.ok){
    let msg=r.statusText;
    try{ msg=ct.indexOf('json')>=0 ? (await r.json()).detail||msg : (await r.text()).slice(0,200);}catch(e){}
    toast(String(msg)); throw new Error(path+' '+r.status);
  }
  return ct.indexOf('json')>=0 ? r.json() : r.text();
}
function toast(txt){
  const box=$('toast'); if(!box)return; const d=document.createElement('div'); d.className='t'; d.textContent=txt;
  box.appendChild(d); setTimeout(function(){d.style.transition='opacity .4s';d.style.opacity='0';setTimeout(function(){d.remove();},400);},3200);
}
function fmtWon(v){return Math.round(v||0).toLocaleString('ko-KR');}

/* ---------- 테마 ---------- */
function applyTheme(mode){
  try{ if(mode) localStorage.setItem('cw_theme', mode);}catch(e){}
  let m=mode||(function(){try{return localStorage.getItem('cw_theme');}catch(e){return null;}})()||'light';
  const eff=(m==='dark'||m==='light')?m:((matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches)?'dark':'light');
  document.documentElement.dataset.theme=eff; document.documentElement.dataset.themeMode=m;
}
document.querySelectorAll('[data-theme-set]').forEach(function(b){b.onclick=function(){applyTheme(b.dataset.themeSet);};});

/* ---------- 라우터 ---------- */
const TITLES={dash:'통합 대시보드',forecast:'발주 예측',data:'데이터 관리',update:'업데이트'};
let dashLoaded=false;
function go(scr){
  document.querySelectorAll('#nav button').forEach(function(b){b.classList.toggle('on', b.dataset.scr===scr);});
  document.querySelectorAll('.screen').forEach(function(s){s.classList.toggle('on', s.id==='scr-'+scr);});
  $('scrTitle').textContent=TITLES[scr]||'';
  $('dashPeriod').style.display=(scr==='dash')?'':'none';
  if(scr==='dash'&&!dashLoaded) loadDash();
  if(scr==='sales') showSales();
  if(scr==='logi') showLogi();
  if(scr==='trend') showTrend();
  if(scr==='data') loadState();
  if(scr==='update') updShow();
}
$('nav').addEventListener('click',function(e){var b=e.target.closest('button[data-scr]');if(b)go(b.dataset.scr);});
$('hdrRefresh').addEventListener('click',function(){ if(el('.screen.on')&&el('.screen.on').id==='scr-dash'){dashLoaded=false;loadDash();} else loadState(); });

/* ===========================================================
   대시보드 부트스트랩
   =========================================================== */
async function loadDash(){
  try{
    const D=await api('/api/dashboard');
    if(D&&D.empty){ $('dashPeriod').textContent='데이터 없음 — [데이터 관리]에서 파일을 업로드하세요'; return; }
    window.D=D;
    // 물류/재고 조각 주입 (dashboard.js 가 이 안의 요소를 참조하므로 initDashboard 전에)
    $('logiMount').innerHTML=D.logiHtml||'';
    // 목표 기본값
    if(D.plan&&$('perfPlan')) $('perfPlan').value=(D.plan*100).toFixed(D.plan*100%1?1:0);
    // 헤더 기간
    $('dashPeriod').textContent='데이터 기간: '+D.period[0]+' ~ '+D.period[1];
    $('dashFoot').textContent='쿠팡 통합 대시보드 · 데이터 '+D.F.length.toLocaleString()+'행';
    // 대시보드 렌더 (dashboard.js)
    if(window.initDashboard) window.initDashboard();
    // 콘솔형 날짜 UI 구성
    buildDateUI(D);
    dashLoaded=true;
  }catch(e){ /* toast already shown */ }
}

/* ---------- 콘솔형 날짜 UI (범위 캘린더 + 월별/분기별 보기) ---------- */
function lastDay(y,m){return new Date(y,m,0).getDate();}      // m:1-12
function clamp(iso,lo,hi){return iso<lo?lo:(iso>hi?hi:iso);}
function setRange(s,e){ $('dStart').value=s; $('dEnd').value=e; if(window.onRange) window.onRange(); syncDD(); }

function buildDateUI(D){
  const lo=D.period[0], hi=D.period[1];
  // 고유 월/분기 (데이터에 존재하는 것만)
  const mset={}, qset={};
  D.F.forEach(function(r){var d=r[0];var ym=d.slice(0,7);mset[ym]=1;var q=Math.floor((+d.slice(5,7)-1)/3)+1;qset[d.slice(0,4)+'-Q'+q]=1;});
  const months=Object.keys(mset).sort().reverse();
  const quarters=Object.keys(qset).sort().reverse();
  // 월별 메뉴
  const mm=$('ddMonth'); mm.innerHTML='';
  months.forEach(function(ym){
    var y=+ym.slice(0,4), m=+ym.slice(5,7);
    var it=document.createElement('div'); it.className='it'; it.dataset.val=ym;
    it.innerHTML='<span class="ck"></span>'+y+'년 '+m+'월';
    it.onclick=function(){ setRange(clamp(ym+'-01',lo,hi), clamp(ym+'-'+String(lastDay(y,m)).padStart(2,'0'),lo,hi)); closeMenus(); };
    mm.appendChild(it);
  });
  // 분기별 메뉴
  const qm=$('ddQ'); qm.innerHTML='';
  quarters.forEach(function(qk){
    var y=+qk.slice(0,4), q=+qk.slice(6);
    var sm=(q-1)*3+1, em=sm+2;
    var it=document.createElement('div'); it.className='it'; it.dataset.val=qk;
    it.innerHTML='<span class="ck"></span>'+qk;
    it.onclick=function(){ setRange(clamp(y+'-'+String(sm).padStart(2,'0')+'-01',lo,hi), clamp(y+'-'+String(em).padStart(2,'0')+'-'+String(lastDay(y,em)).padStart(2,'0'),lo,hi)); closeMenus(); };
    qm.appendChild(it);
  });
  // 드롭다운 토글
  $('ddMonthBtn').onclick=function(e){e.stopPropagation();toggleMenu('ddMonth');};
  $('ddQBtn').onclick=function(e){e.stopPropagation();toggleMenu('ddQ');};
  // 초기화
  $('btnReset').onclick=function(){ setRange(lo,hi); };
  // 캘린더
  attachCal('dStart','calStart',lo,hi);
  attachCal('dEnd','calEnd',lo,hi);
  syncDD();
}
function toggleMenu(id){var m=$(id);var open=m.classList.contains('open');closeMenus();if(!open)m.classList.add('open');}
function closeMenus(){document.querySelectorAll('.ddmenu.open,.cal.open').forEach(function(x){x.classList.remove('open');});}
document.addEventListener('click',function(e){ if(!e.target.closest('.ddwrap')&&!e.target.closest('.datefield')) closeMenus(); });
function syncDD(){
  var s=$('dStart').value, e=$('dEnd').value;
  // 월 선택 표시
  document.querySelectorAll('#ddMonth .it').forEach(function(it){
    var ym=it.dataset.val, y=+ym.slice(0,4), m=+ym.slice(5,7);
    var ms=ym+'-01', me=ym+'-'+String(lastDay(y,m)).padStart(2,'0');
    var sel=(s<=ms||s.slice(0,7)===ym)&&(e>=me||e.slice(0,7)===ym)&&(s.slice(0,7)===ym&&e.slice(0,7)===ym);
    it.classList.toggle('sel', s.slice(0,7)===ym&&e.slice(0,7)===ym);
    el('.ck',it).textContent=(s.slice(0,7)===ym&&e.slice(0,7)===ym)?'✓':'';
  });
  var lbl=(s&&e&&s.slice(0,7)===e.slice(0,7))?((+s.slice(0,4))+'년 '+(+s.slice(5,7))+'월'):'월별 보기';
  $('ddMonthBtn').innerHTML=lbl+' <span class="cv">▾</span>';
  document.querySelectorAll('#ddQ .it').forEach(function(it){
    var qk=it.dataset.val,y=+qk.slice(0,4),q=+qk.slice(6),sm=(q-1)*3+1,em=sm+2;
    var qs=y+'-'+String(sm).padStart(2,'0')+'-01', qe=y+'-'+String(em).padStart(2,'0')+'-'+String(lastDay(y,em)).padStart(2,'0');
    var sel=(s===qs&&e===qe);
    it.classList.toggle('sel',sel); el('.ck',it).textContent=sel?'✓':'';
  });
}
function attachCal(inputId, calId, lo, hi){
  const inp=$(inputId), cal=$(calId);
  let view=(inp.value||lo).slice(0,7); // YYYY-MM
  function draw(){
    var y=+view.slice(0,4), m=+view.slice(5,7);
    var first=new Date(y,m-1,1), startDow=first.getDay(), dim=lastDay(y,m);
    var sel=inp.value, todayISO=new Date().toISOString().slice(0,10);
    var h='<div class="caltop"><button class="navb" data-nav="-1">‹</button><b>'+y+'년 '+m+'월</b><button class="navb" data-nav="1">›</button></div>';
    h+='<div class="dow"><span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span></div><div class="days">';
    for(var i=0;i<startDow;i++) h+='<button class="out" disabled></button>';
    for(var d=1;d<=dim;d++){
      var iso=y+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0');
      var cls=''; if(iso===sel)cls+=' sel'; if(iso===todayISO)cls+=' today';
      var dis=(iso<lo||iso>hi)?' disabled':'';
      h+='<button class="'+cls.trim()+(dis?' out':'')+'"'+dis+' data-iso="'+iso+'">'+d+'</button>';
    }
    h+='</div>'; cal.innerHTML=h;
    cal.querySelectorAll('[data-nav]').forEach(function(b){b.onclick=function(ev){ev.stopPropagation();var yy=+view.slice(0,4),mm2=+view.slice(5,7)+(+b.dataset.nav);var nd=new Date(yy,mm2-1,1);view=nd.getFullYear()+'-'+String(nd.getMonth()+1).padStart(2,'0');draw();};});
    cal.querySelectorAll('[data-iso]').forEach(function(b){b.onclick=function(ev){ev.stopPropagation();var iso=b.dataset.iso;
      if(inputId==='dStart'){ if($('dEnd').value&&iso>$('dEnd').value) $('dEnd').value=iso; }
      else { if($('dStart').value&&iso<$('dStart').value) $('dStart').value=iso; }
      inp.value=iso; if(window.onRange)window.onRange(); syncDD(); cal.classList.remove('open');};});
  }
  inp.onclick=function(e){e.stopPropagation();var open=cal.classList.contains('open');closeMenus();if(!open){view=(inp.value||lo).slice(0,7);draw();cal.classList.add('open');}};
}

/* ===========================================================
   데이터 관리
   =========================================================== */
function readAsDataURL(file){return new Promise(function(res,rej){var fr=new FileReader();fr.onload=function(){res(fr.result);};fr.onerror=rej;fr.readAsDataURL(file);});}
function stageFiles(input, listEl, store){
  Array.prototype.forEach.call(input.files,function(f){store.push(f);});
  renderFileList(listEl,store);
}
function renderFileList(listEl, store){
  listEl.innerHTML=store.map(function(f,i){return '<div class="filerow">📄 '+f.name+' <span class="sub">('+Math.round(f.size/1024).toLocaleString()+' KB)</span><button class="rm" data-i="'+i+'">✕</button></div>';}).join('');
  listEl.querySelectorAll('.rm').forEach(function(b){b.onclick=function(){store.splice(+b.dataset.i,1);renderFileList(listEl,store);};});
}
function setupDrop(dropId, fileId, listEl, store){
  const drop=$(dropId), file=$(fileId);
  drop.onclick=function(){file.click();};
  file.onchange=function(){stageFiles(file,listEl,store);file.value='';};
  ['dragover','dragenter'].forEach(function(ev){drop.addEventListener(ev,function(e){e.preventDefault();drop.classList.add('hover');});});
  ['dragleave','drop'].forEach(function(ev){drop.addEventListener(ev,function(e){e.preventDefault();drop.classList.remove('hover');});});
  drop.addEventListener('drop',function(e){ if(e.dataTransfer&&e.dataTransfer.files){Array.prototype.forEach.call(e.dataTransfer.files,function(f){store.push(f);});renderFileList(listEl,store);} });
}
const upStore=[];
setupDrop('upDrop','upFile',$('upList'),upStore);
function showMsg(id,cls,html){var m=$(id);m.className='msg show '+cls;m.innerHTML=html;}
async function doUpload(applyIt){
  if(!upStore.length){showMsg('upMsg','err','파일을 먼저 선택하세요.');return;}
  const btn=applyIt?$('upApply'):$('upPreview'); const old=btn.innerHTML; btn.disabled=true; btn.innerHTML='<span class="spin"></span>'+(applyIt?'적용 중…':'검증 중…');
  try{
    const files=[];
    for(const f of upStore){ files.push({name:f.name, data:await readAsDataURL(f)}); }
    const res=await api('/api/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:files, apply:!!applyIt})});
    var det=res.detected?(' · 판별: 판매 '+(res.detected.sales||0)+' / 물류 '+(res.detected.logi||0)+' / 미상 '+(res.detected.unknown||0)):'';
    var stat='추가 '+res.added+' · 교체 '+res.replaced+' · 중복생략 '+res.skipped+' (블록 기준)';
    if(applyIt){ showMsg('upMsg','ok','✅ 통합 완료 — '+stat+det+'<br>기간: '+(res.range&&res.range[0]?res.range[0]+' ~ '+res.range[1]:'-')); upStore.length=0; renderFileList($('upList'),upStore); loadState(); dashLoaded=false; }
    else { showMsg('upMsg','info','🔍 미리보기 — '+stat+det+'<br>「통합에 적용」을 눌러 저장하세요.'); }
  }catch(e){}
  finally{ btn.disabled=false; btn.innerHTML=old; }
}
$('upPreview').onclick=function(){doUpload(false);};
$('upApply').onclick=function(){doUpload(true);};

async function loadState(){
  try{
    const st=await api('/api/state');
    $('sideVer').textContent='v'+st.version;
    var cells=[
      ['버전','v'+st.version],
      ['통합 기간', st.range&&st.range[0]?st.range[0]+' ~ '+st.range[1]:'—'],
      ['판매 행수', (st.salesRows||0).toLocaleString()],
      ['물류 행수', (st.logiRows||0).toLocaleString()],
    ];
    $('statGrid').innerHTML=cells.map(function(c){return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}).join('');
    var arch=st.archives||[];
    $('archBody').innerHTML=arch.length?arch.map(function(a){return '<tr><td>'+a.name+'</td><td class="num">'+Math.round(a.size/1024).toLocaleString()+' KB</td><td class="num"><button class="btn ghost" data-arch="'+a.name+'">열기 ⧉</button></td></tr>';}).join('')
      :'<tr><td colspan="3" style="text-align:center;color:var(--faint)">보관본 없음</td></tr>';
    $('archBody').querySelectorAll('[data-arch]').forEach(function(b){b.onclick=function(){window.open('/api/archive/'+encodeURIComponent(b.dataset.arch),'_blank');};});
  }catch(e){}
}
$('btnExportXlsx').onclick=function(){window.location='/api/export/dashboard.xlsx';};
$('btnArchive').onclick=async function(){
  if(!confirm('현재 통합본을 보관본으로 저장하고 통합본을 비웁니다. 진행할까요?'))return;
  try{ const r=await api('/api/archive',{method:'POST'}); showMsg('dataMsg','ok','📦 보관 완료: '+(r.archive||'')); loadState(); dashLoaded=false; }catch(e){}
};

/* ===========================================================
   판매 분석 · 기본 물류 지표 (쿠팡 프리미엄데이터 콘솔풍 리포트)
   — window.D 로 렌더 (dashboard.js/analytics.py 불변)
   =========================================================== */
async function ensureD(){
  if(window.D&&window.D.F) return window.D;
  const D=await api('/api/dashboard');
  if(!D||D.empty){ return null; }
  window.D=D; return D;
}
function pct2(x){return (x==null||isNaN(x))?'—':x.toFixed(2)+'%';}
function seedDates(a,b){var D=window.D;if(a&&!a.value){a.value=D.period[0];}if(b&&!b.value){b.value=D.period[1];}}

/* ---------- 공통: 카테고리/월/분기 셀렉트 ---------- */
function fillCatSel(id){$(id).innerHTML='<option value="">세부 카테고리 (전체)</option>'+window.D.CN.slice().sort().map(function(c){return '<option value="'+c.replace(/"/g,'&quot;')+'">'+c+'</option>';}).join('');}
function distinctMonths(){var s={};window.D.F.forEach(function(r){s[r[0].slice(0,7)]=1;});return Object.keys(s).sort().reverse();}
function distinctQuarters(){var s={};window.D.F.forEach(function(r){var d=r[0];s[d.slice(0,4)+'-Q'+(Math.floor((+d.slice(5,7)-1)/3)+1)]=1;});return Object.keys(s).sort().reverse();}
function fillMonthSel(id){$(id).innerHTML='<option value="">월별 보기</option>'+distinctMonths().map(function(ym){return '<option value="'+ym+'">'+(+ym.slice(0,4))+'년 '+(+ym.slice(5,7))+'월</option>';}).join('');}
function fillQSel(id){$(id).innerHTML='<option value="">분기별 보기</option>'+distinctQuarters().map(function(x){return '<option value="'+x+'">'+x+'</option>';}).join('');}
function monthRange(ym){var y=+ym.slice(0,4),m=+ym.slice(5,7),lo=window.D.period[0],hi=window.D.period[1];return [clamp(ym+'-01',lo,hi),clamp(ym+'-'+String(lastDay(y,m)).padStart(2,'0'),lo,hi)];}
function quarterRange(qk){var y=+qk.slice(0,4),q=+qk.slice(6),sm=(q-1)*3+1,em=sm+2,lo=window.D.period[0],hi=window.D.period[1];return [clamp(y+'-'+String(sm).padStart(2,'0')+'-01',lo,hi),clamp(y+'-'+String(em).padStart(2,'0')+'-'+String(lastDay(y,em)).padStart(2,'0'),lo,hi)];}
function skuCatMap(){var m={},D=window.D;D.F.forEach(function(r){var n=D.SN[r[2]];if(!(n in m))m[n]=D.CN[r[3]];});return m;}

/* ---------- 판매 분석 ---------- */
let salesSeeded=false;
async function showSales(){
  const D=await ensureD();
  if(!D){ $('saInfo').textContent='데이터 없음 — [데이터 관리]에서 업로드하세요'; return; }
  if(!salesSeeded){ seedDates($('saStart'),$('saEnd')); fillCatSel('saCat'); fillMonthSel('saMonth'); fillQSel('saQuarter'); salesSeeded=true; }
  renderSales();
}
function saAgg(){
  const D=window.D, q=$('saQ').value.trim().toLowerCase(), s=$('saStart').value, e=$('saEnd').value, unit=$('saUnit').value, cat=$('saCat').value;
  const m=new Map();
  D.F.forEach(function(r){var d=r[0]; if(s&&d<s)return; if(e&&d>e)return; if(cat&&D.CN[r[3]]!==cat)return;
    var key,name;
    if(unit==='date'){key=d;name=d;}
    else{var idx=unit==='item'?1:2, names=unit==='item'?D.VN:D.SN; key=r[idx]; name=names[r[idx]];}
    if(q&&String(name).toLowerCase().indexOf(q)<0)return;
    if(!m.has(key))m.set(key,{name:name,gmv:0,amv:0,units:0,ret:0,cogs:0,pv:0,ord:0});
    var a=m.get(key); a.gmv+=r[4];a.amv+=r[9];a.units+=r[5];a.ret+=r[6];a.cogs+=r[10];a.pv+=r[8];a.ord+=r[7];
  });
  var rows=Array.from(m.values());
  if(unit==='date') rows.sort(function(a,b){return a.name<b.name?-1:1;});
  else rows.sort(function(a,b){return b.gmv-a.gmv;});
  return rows;
}
function renderSales(){
  const rows=saAgg();
  const label=$('saUnit').value==='date'?'날짜':($('saUnit').value==='item'?'벤더아이템':'상품명');
  $('saHead').innerHTML='<tr><th rowspan="2">'+label+'</th>'
    +'<th class="num" colspan="5">기본 지표</th><th class="num" colspan="5">유입 지표</th></tr>'
    +'<tr><th class="num">매출액(GMV)</th><th class="num">조정매출(AMV)</th><th class="num">판매수량</th><th class="num">반품수량</th><th class="num">매입원가</th>'
    +'<th class="num">조회수(PV)</th><th class="num">주문건수</th><th class="num">구매전환율</th><th class="num">객단가</th><th class="num">평균판매가(ASP)</th></tr>';
  $('saBody').innerHTML=rows.map(function(o){
    var conv=o.pv?o.ord/o.pv*100:null, aov=o.ord?o.gmv/o.ord:0, asp=o.units?o.gmv/o.units:0;
    return '<tr><td>'+o.name+'</td>'
      +'<td class="num">'+fmtWon(o.gmv)+'</td><td class="num">'+fmtWon(o.amv)+'</td><td class="num">'+fmtWon(o.units)+'</td><td class="num">'+fmtWon(o.ret)+'</td><td class="num">'+fmtWon(o.cogs)+'</td>'
      +'<td class="num">'+fmtWon(o.pv)+'</td><td class="num">'+fmtWon(o.ord)+'</td><td class="num">'+pct2(conv)+'</td><td class="num">'+fmtWon(aov)+'</td><td class="num">'+fmtWon(asp)+'</td></tr>';
  }).join('')||'<tr><td colspan="11" style="text-align:center;color:var(--faint)">해당 조건의 데이터 없음</td></tr>';
  // 요약 카드
  var t={gmv:0,amv:0,units:0,ret:0,cogs:0,pv:0,ord:0}; rows.forEach(function(o){t.gmv+=o.gmv;t.amv+=o.amv;t.units+=o.units;t.ret+=o.ret;t.cogs+=o.cogs;t.pv+=o.pv;t.ord+=o.ord;});
  var conv=t.pv?t.ord/t.pv*100:0;
  var cards=[['매출액(GMV)',fmtWon(t.gmv)+'원'],['판매수량',fmtWon(t.units)+'개'],['반품수량',fmtWon(t.ret)+'개'],['주문건수',fmtWon(t.ord)+'건'],['구매전환율',conv.toFixed(2)+'%'],['매입원가',fmtWon(t.cogs)+'원']];
  $('saCards').innerHTML=cards.map(function(c){return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}).join('');
  $('saInfo').textContent=rows.length+'개 · '+($('saStart').value||'')+' ~ '+($('saEnd').value||'');
}
function saMonthPick(){var v=$('saMonth').value; if(v){var r=monthRange(v);$('saStart').value=r[0];$('saEnd').value=r[1];$('saQuarter').value='';} renderSales();}
function saQPick(){var v=$('saQuarter').value; if(v){var r=quarterRange(v);$('saStart').value=r[0];$('saEnd').value=r[1];$('saMonth').value='';} renderSales();}
$('saSearch').onclick=renderSales;
$('saUnit').onchange=renderSales; $('saCat').onchange=renderSales;
$('saMonth').onchange=saMonthPick; $('saQuarter').onchange=saQPick;
$('saStart').onchange=function(){$('saMonth').value='';$('saQuarter').value='';renderSales();};
$('saEnd').onchange=function(){$('saMonth').value='';$('saQuarter').value='';renderSales();};
$('saQ').addEventListener('keydown',function(e){if(e.key==='Enter')renderSales();});
$('saReset').onclick=function(){$('saQ').value='';$('saCat').value='';$('saMonth').value='';$('saQuarter').value='';$('saStart').value=window.D.period[0];$('saEnd').value=window.D.period[1];$('saUnit').value='sku';renderSales();};

/* ---------- 기본 물류 지표 ---------- */
let logiSeeded=false;
function fillFC(id){$(id).innerHTML='<option value="">전체</option>'+window.D.mtx.centers.map(function(c){return '<option value="'+c.replace(/"/g,'&quot;')+'">'+c+'</option>';}).join('');}
async function showLogi(){
  const D=await ensureD();
  if(!D){ $('loInfo').textContent='데이터 없음 — [데이터 관리]에서 업로드하세요'; return; }
  if(!D.mtx){ $('loBody').innerHTML='<tr><td style="padding:16px;color:var(--faint)">물류 데이터가 없습니다.</td></tr>'; return; }
  if(!logiSeeded){ seedDates($('loStart'),$('loEnd')); fillCatSel('loCat'); fillMonthSel('loMonth'); fillQSel('loQuarter'); fillFC('loFC'); logiSeeded=true; }
  $('loLd').textContent=D.ld||'';
  renderLogi();
}
function loAgg(){
  const D=window.D, q=$('loQ').value.trim().toLowerCase(), s=$('loStart').value, e=$('loEnd').value, cat=$('loCat').value, fc=$('loFC').value;
  const skus=D.mtx.skus, fcIdx=fc?D.mtx.centers.indexOf(fc):-1, sc=cat?skuCatMap():null, m=new Map();
  function pass(si){var nm=skus[si]; if(q&&nm.toLowerCase().indexOf(q)<0)return false; if(cat&&sc[nm]!==cat)return false; return true;}
  function ens(si){ if(!m.has(si))m.set(si,{name:skus[si],inb:0,outb:0,stk:0}); return m.get(si); }
  D.mtx.lf.forEach(function(r){var d=r[0]; if(s&&d<s)return; if(e&&d>e)return; if(fcIdx>=0&&r[2]!==fcIdx)return; if(!pass(r[1]))return; var a=ens(r[1]); a.outb+=r[3]; a.inb+=r[4];});
  D.mtx.stk.forEach(function(r){ if(fcIdx>=0&&r[1]!==fcIdx)return; if(!pass(r[0]))return; var a=ens(r[0]); a.stk+=r[2];});
  return Array.from(m.values()).filter(function(o){return o.inb||o.outb||o.stk;}).sort(function(a,b){return b.outb-a.outb;});
}
function renderLogi(){
  const rows=loAgg(), fc=$('loFC').value;
  $('loHead').innerHTML='<tr><th rowspan="2">상품명</th><th class="num" colspan="3">기본 지표</th><th rowspan="2">상태</th></tr>'
    +'<tr><th class="num">입고수량</th><th class="num">출고수량</th><th class="num">현재재고</th></tr>';
  $('loBody').innerHTML=rows.map(function(o){
    var st=o.stk<=0?'<span class="badge crit">품절</span>':'<span class="badge ok">정상</span>';
    return '<tr><td>'+o.name+'</td><td class="num">'+fmtWon(o.inb)+'</td><td class="num">'+fmtWon(o.outb)+'</td><td class="num">'+fmtWon(o.stk)+'</td><td>'+st+'</td></tr>';
  }).join('')||'<tr><td colspan="5" style="text-align:center;color:var(--faint)">해당 조건의 데이터 없음</td></tr>';
  var t={inb:0,outb:0,stk:0}; rows.forEach(function(o){t.inb+=o.inb;t.outb+=o.outb;t.stk+=o.stk;});
  var cards=[['총 입고',fmtWon(t.inb)+'개'],['총 출고',fmtWon(t.outb)+'개'],['현재 재고',fmtWon(t.stk)+'개'],['FC',fc||'전체']];
  $('loCards').innerHTML=cards.map(function(c){return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}).join('');
  $('loInfo').textContent=rows.length+'개 · '+(fc||'전 센터')+' · 입·출고 '+($('loStart').value||'')+' ~ '+($('loEnd').value||'')+' · 재고 기준일 '+(window.D.ld||'');
}
function loMonthPick(){var v=$('loMonth').value; if(v){var r=monthRange(v);$('loStart').value=r[0];$('loEnd').value=r[1];$('loQuarter').value='';} renderLogi();}
function loQPick(){var v=$('loQuarter').value; if(v){var r=quarterRange(v);$('loStart').value=r[0];$('loEnd').value=r[1];$('loMonth').value='';} renderLogi();}
$('loSearch').onclick=renderLogi;
$('loCat').onchange=renderLogi; $('loFC').onchange=renderLogi;
$('loMonth').onchange=loMonthPick; $('loQuarter').onchange=loQPick;
$('loStart').onchange=function(){$('loMonth').value='';$('loQuarter').value='';renderLogi();};
$('loEnd').onchange=function(){$('loMonth').value='';$('loQuarter').value='';renderLogi();};
$('loQ').addEventListener('keydown',function(e){if(e.key==='Enter')renderLogi();});
$('loReset').onclick=function(){$('loQ').value='';$('loCat').value='';$('loFC').value='';$('loMonth').value='';$('loQuarter').value='';$('loStart').value=window.D.period[0];$('loEnd').value=window.D.period[1];renderLogi();};

/* ---------- 구매 트렌드 (지표 막대 + 구매전환율 선) ---------- */
let trChartObj=null, trendSeeded=false;
function monLocal(iso){var p=iso.split('-');var dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));var wd=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-wd);return dt.toISOString().slice(0,10);}
async function showTrend(){
  const D=await ensureD();
  if(!D){ $('trInfo').textContent='데이터 없음 — [데이터 관리]에서 업로드하세요'; return; }
  if(!trendSeeded){ seedDates($('trStart'),$('trEnd')); trendSeeded=true; }
  renderTrend2();
}
function trAgg(){
  const D=window.D, mi=+$('trMetric').value, unit=$('trUnit').value, s=$('trStart').value, e=$('trEnd').value, q=$('trQ').value.trim().toLowerCase();
  const m={};
  D.F.forEach(function(r){var d=r[0]; if(s&&d<s)return; if(e&&d>e)return; if(q&&String(D.SN[r[2]]).toLowerCase().indexOf(q)<0)return;
    var k=unit==='month'?d.slice(0,7):(unit==='week'?monLocal(d):d);
    if(!m[k])m[k]={val:0,ord:0,pv:0}; m[k].val+=r[mi]; m[k].ord+=r[7]; m[k].pv+=r[8];});
  var keys=Object.keys(m).sort();
  return {keys:keys, vals:keys.map(function(k){return m[k].val;}), conv:keys.map(function(k){return m[k].pv?m[k].ord/m[k].pv*100:0;})};
}
function renderTrend2(){
  var a=trAgg(), lbl=$('trMetric').selectedOptions[0].textContent;
  if(trChartObj){trChartObj.destroy();trChartObj=null;}
  trChartObj=new Chart($('trChart'),{data:{labels:a.keys,datasets:[
    {type:'bar',label:lbl,data:a.vals,backgroundColor:'rgba(52,106,255,.5)',borderColor:'#346AFF',borderWidth:1,yAxisID:'y',order:2},
    {type:'line',label:'구매전환율(%)',data:a.conv,borderColor:'#F59E0B',backgroundColor:'rgba(245,158,11,.15)',tension:.35,pointRadius:2,yAxisID:'y1',order:1}
  ]},options:{responsive:true,interaction:{mode:'index',intersect:false},plugins:{legend:{display:true}},
    scales:{y:{position:'left',ticks:{callback:function(v){return Math.round(v).toLocaleString();}}},
            y1:{position:'right',grid:{drawOnChartArea:false},ticks:{callback:function(v){return v.toFixed(1)+'%';}}}}}});
  var pI=0,cI=0; a.vals.forEach(function(v,i){if(v>a.vals[pI])pI=i;}); a.conv.forEach(function(v,i){if(v>a.conv[cI])cI=i;});
  var tot=a.vals.reduce(function(x,y){return x+y;},0);
  $('trCards').innerHTML=[['합계 · '+lbl, Math.round(tot).toLocaleString()],['최고 '+lbl+' 구간', a.keys[pI]||'-'],['최고 전환율 구간', (a.keys[cI]||'-')+' · '+(a.conv[cI]||0).toFixed(1)+'%']]
    .map(function(c){return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}).join('');
  $('trInfo').textContent=a.keys.length+' 구간 · '+($('trStart').value||'')+' ~ '+($('trEnd').value||'');
}
$('trSearch').onclick=renderTrend2;
$('trMetric').onchange=renderTrend2; $('trUnit').onchange=renderTrend2;
$('trQ').addEventListener('keydown',function(e){if(e.key==='Enter')renderTrend2();});
$('trReset').onclick=function(){$('trQ').value='';$('trMetric').value='4';$('trUnit').value='day';$('trStart').value=window.D.period[0];$('trEnd').value=window.D.period[1];renderTrend2();};

/* ===========================================================
   발주 예측
   =========================================================== */
const fcStore=[];
setupDrop('fcDrop','fcFile',$('fcList'),fcStore);
$('fcRun').onclick=async function(){
  if(!fcStore.length){showMsg('fcMsg','err','주문현황 엑셀을 선택하세요.');return;}
  const btn=$('fcRun'); const old=btn.innerHTML; btn.disabled=true; btn.innerHTML='<span class="spin"></span>분석 중…';
  try{
    const files=[]; for(const f of fcStore){ files.push({name:f.name, data:await readAsDataURL(f)}); }
    const res=await api('/api/forecast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:files})});
    showMsg('fcMsg','ok','✅ 예측 완료 — 품목 '+res.prods+' · 거래처 '+res.vends+' · 기간 '+res.period+' <a class="link" href="/api/export/forecast.xlsx" target="_blank">엑셀 다운로드</a>');
    var f=document.createElement('iframe'); f.className='fc'; f.srcdoc=res.html; $('fcResult').innerHTML=''; $('fcResult').appendChild(f);
  }catch(e){}
  finally{ btn.disabled=false; btn.innerHTML=old; }
};

/* ===========================================================
   업데이트
   =========================================================== */
let updLatest=null;
async function updShow(){
  try{ const st=await api('/api/state'); $('updInfo').innerHTML='<div class="card sm"><div class="k">현재 버전</div><div class="v">v'+st.version+'</div></div>'+'<div class="card sm"><div class="k">모드</div><div class="v">'+(st.frozen?'배포(exe)':'개발(소스)')+'</div></div>'; }catch(e){}
}
$('updCheck').onclick=async function(){
  showMsg('updMsg','info','확인 중…');
  try{ const r=await api('/api/update/check');
    if(r.error){ showMsg('updMsg','err','확인 실패: '+r.error); return; }
    if(r.newer){ updLatest=r; $('updApply').style.display=''; showMsg('updMsg','ok','🎉 새 버전 v'+r.latest+' 있음 (현재 v'+r.current+')<br><span class="sub">'+(r.notes||'').replace(/</g,'&lt;').replace(/\n/g,'<br>')+'</span>'); }
    else { $('updApply').style.display='none'; showMsg('updMsg','ok','✅ 이미 최신 버전입니다 (v'+r.current+')'); }
  }catch(e){}
};
$('updApply').onclick=async function(){
  if(!confirm('최신 버전을 설치하고 프로그램을 재시작합니다. 진행할까요?'))return;
  showMsg('updMsg','info','<span class="spin"></span>다운로드·설치 중… 잠시 후 자동 재시작됩니다.');
  try{ await api('/api/update/apply',{method:'POST'}); showMsg('updMsg','ok','설치를 시작했습니다. 30초 후 자동으로 새로고침합니다.'); setTimeout(function(){location.reload();},30000); }catch(e){}
};

/* ---------- 초기 로드 ---------- */
applyTheme();
loadState();      // 사이드바 버전/현황
loadDash();       // 기본 화면
})();
