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
