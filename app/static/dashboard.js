// dashboard.js — suzy_data 대시보드 렌더 로직 (원본 verbatim). window.D 세팅 후 initDashboard() 호출.
// [검증된 재무공식 — VATR/VATDIV/VATCOGS/met/ppmCell/marginData/PPM 은 절대 수정 금지]

/* ===== 실적확인·일자별마진 스켈레톤 (window.VATR/VATDIV/VATCOGS/renderPerf/renderDayMargin/setVat/setPmc 정의) ===== */
(function(){
  window.__vatMode='excl';
  window.VATR=function(){var el=document.getElementById('vatRate');var r=el?parseFloat(el.value):10;if(isNaN(r))r=0;return r/100;};
  window.VATDIV=function(){return (window.__vatMode==='excl')?(1+VATR()):1;};
  window.VATCOGS=function(c){return c*(1+VATR())/VATDIV();};  // COGS도 GMV와 같은 부가세 기준으로 → 마진율 불변
  window.__pmcOn=false;  // PPM에 판촉비(PMC) 반영 여부 (부가세처럼 on/off)
  window.setPmc=function(on){window.__pmcOn=on;var a=document.getElementById('pmcOn'),b=document.getElementById('pmcOff');if(a)a.className=on?'active':'';if(b)b.className=on?'':'active';if(window.renderAll)renderAll();};
  window.setVat=function(m){window.__vatMode=m;var a=document.getElementById('vatIncl'),b=document.getElementById('vatExcl');if(a)a.className=(m==='incl')?'active':'';if(b)b.className=(m==='excl')?'active':'';if(window.renderAll)renderAll();};
  window.onVat=function(){if(window.renderAll)renderAll();};
  function won2(v){return Math.round(v||0).toLocaleString('ko-KR');}
  function pct1(x){return (x==null)?'—':(x*100).toFixed(1)+'%';}
  function prange(){return [document.getElementById('dStart').value, document.getElementById('dEnd').value];}
  function inR(d,s,e){return (!s||d>=s)&&(!e||d<=e);}
  function planVal(){var el=document.getElementById('perfPlan');var v=el?parseFloat(el.value):28;if(isNaN(v))v=28;return v/100;}
  function maxDate(){var mx='';D.F.forEach(function(r){if(r[0]>mx)mx=r[0];});return mx;}
  function aggByDate(s,e){var mp={};D.F.forEach(function(r){var d=r[0];if(!inR(d,s,e))return;var k=r[2];if(!mp[k])mp[k]=[0,0,0,0];mp[k][0]+=r[4];mp[k][1]+=r[5];mp[k][2]+=r[10];mp[k][3]+=r[11];});return mp;}
  function met(a){var vd=VATDIV();var gmv=a[0]/vd,units=a[1],cogs=VATCOGS(a[2]),pmc=-(a[3]||0)/vd;var ppp=gmv-cogs;var ppm=gmv?(ppp+pmc)/gmv:null;var plan=planVal();var gap=(ppm==null)?null:ppm-plan;var gamt=(gap==null)?null:gap*gmv;return {gmv:gmv,ppp:ppp,units:units,pmc:pmc,ppm:ppm,gap:gap,gamt:gamt};}
  function cn(v){return '<td class="num">'+won2(v)+'</td>';}
  function cp(x){return '<td class="num">'+pct1(x)+'</td>';}
  function cg(x){var c=(x==null)?'':(x<0?'color:#ef4444;font-weight:600':'color:#10b981;font-weight:600');return '<td class="num" style="'+c+'">'+pct1(x)+'</td>';}
  function seg(m){return cn(m.gmv)+cn(m.ppp)+cn(m.units)+cn(m.pmc)+cp(m.ppm)+cg(m.gap)+cn(m.gamt);}
  function sumAgg(mp){var t=[0,0,0,0];Object.keys(mp).forEach(function(k){t[0]+=mp[k][0];t[1]+=mp[k][1];t[2]+=mp[k][2];t[3]+=(mp[k][3]||0);});return t;}
  window.perfReset=function(){var a=document.getElementById('perfStart'),b=document.getElementById('perfEnd');if(a)a.value=D.period[0];if(b)b.value=D.period[1];renderPerf();};
  window.renderPerf=function(){
    var head=document.getElementById('perfHead');if(!head)return;
    var a=document.getElementById('perfStart'),b=document.getElementById('perfEnd');
    if(a&&!a.value){a.min=D.period[0];a.max=D.period[1];a.value=D.period[0];}
    if(b&&!b.value){b.min=D.period[0];b.max=D.period[1];b.value=D.period[1];}
    var s=a?a.value:'',e=b?b.value:'';
    var day=document.getElementById('perfDay');if(day&&!day.value){day.min=D.period[0];day.max=D.period[1];day.value=maxDate();}
    var dv=day?day.value:'';var plan=planVal();
    document.getElementById('perfInfo').textContent='누적 '+(s||'')+'~'+(e||'')+' · 특정일 '+(dv||'-')+' · 목표 '+(plan*100).toFixed(0)+'%';
    var cum=aggByDate(s,e),spd=aggByDate(dv,dv);
    var hcols=['GMV','PPP','UNISOLD','PMC','PPM(PMC)','GAP','Gap Amt'];
    head.innerHTML='<tr><th rowspan="2">상품명</th><th rowspan="2" class="num">계약</th><th class="num" colspan="7" style="background:#eef2ff">누적('+(s||'')+'~'+(e||'')+')</th><th class="num" colspan="7" style="background:#ecfdf5">특정일('+(dv||'-')+')</th></tr><tr>'+hcols.concat(hcols).map(function(h){return '<th class="num">'+h+'</th>';}).join('')+'</tr>';
    var rows=Object.keys(cum).map(function(k){return {name:D.SN[k],c:met(cum[k]),d:met(spd[k]||[0,0,0])};}).filter(function(o){return o.c.gmv>0;}).sort(function(a,b){return b.c.gmv-a.c.gmv;});
    var pc='<td class="num">'+(plan*100).toFixed(0)+'%</td>';
    var tc=met(sumAgg(cum)),td=met(sumAgg(spd));
    var body='<tr style="font-weight:700;background:#eef2ff"><td>누계실적</td>'+pc+seg(tc)+seg(td)+'</tr>';
    body+=rows.map(function(o){return '<tr><td>'+o.name+'</td>'+pc+seg(o.c)+seg(o.d)+'</tr>';}).join('');
    document.getElementById('perfBody').innerHTML=body;
  };
  var dmUnit='day';
  function dmRange(){var a=document.getElementById('dmStart'),b=document.getElementById('dmEnd');return [a?a.value:'',b?b.value:''];}
  window.dmReset=function(){var a=document.getElementById('dmStart'),b=document.getElementById('dmEnd');if(a)a.value=D.period[0];if(b)b.value=D.period[1];renderDayMargin();};
  window.setDmUnit=function(u){dmUnit=u;var a=document.getElementById('dmDay'),b=document.getElementById('dmMon');if(a)a.className=(u==='day')?'active':'';if(b)b.className=(u==='month')?'active':'';renderDayMargin();};
  function dmKeys(s,e){var set={};D.F.forEach(function(r){var d=r[0];if(!inR(d,s,e))return;set[dmUnit==='month'?d.slice(0,7):d]=1;});return Object.keys(set).sort();}
  function dmData(){var rv=dmRange(),s=rv[0],e=rv[1];var keys=dmKeys(s,e),ki={};keys.forEach(function(k,i){ki[k]=i;});
    var bs={};D.F.forEach(function(r){var d=r[0];if(!inR(d,s,e))return;var k=dmUnit==='month'?d.slice(0,7):d;var si=r[2];if(!bs[si]){bs[si]={g:keys.map(function(){return 0;}),c:keys.map(function(){return 0;}),x:keys.map(function(){return 0;}),tot:0};}bs[si].g[ki[k]]+=r[4];bs[si].c[ki[k]]+=r[10];bs[si].x[ki[k]]+=r[11];bs[si].tot+=r[4];});
    var rows=Object.keys(bs).map(function(si){return {name:D.SN[si],o:bs[si]};}).filter(function(x){return x.o.tot>0;}).sort(function(a,b){return b.o.tot-a.o.tot;}).slice(0,100);
    return {keys:keys,rows:rows};}
  function ppmCell(g,c,x){if(!g)return '<td class="num z">·</td>';var vd=VATDIV();var gg=g/vd;var pmc=window.__pmcOn?(-(x||0)/vd):0;var ppm=(gg-VATCOGS(c)+pmc)/gg;var plan=planVal();var col=ppm>=plan?'#10b981':'#ef4444';return '<td class="num" style="color:'+col+';font-weight:600">'+(ppm*100).toFixed(1)+'%</td>';}
  function dmHead(keys){return '<tr><th>상품명</th><th class="num">계약</th>'+keys.map(function(k){return '<th class="num">'+(dmUnit==='month'?((+k.slice(0,4))+'.'+(+k.slice(5,7))):k.slice(5))+'</th>';}).join('')+'</tr>';}
  function dmBody(rows){var plan=planVal();var pc='<td class="num">'+(plan*100).toFixed(0)+'%</td>';return rows.map(function(x){var tds=x.o.g.map(function(g,i){return ppmCell(g,x.o.c[i],x.o.x[i]);}).join('');return '<tr><td>'+x.name+'</td>'+pc+tds+'</tr>';}).join('');}
  window.renderDayMargin=function(){var h=document.getElementById('dmHead');if(!h)return;
    var a=document.getElementById('dmStart'),b=document.getElementById('dmEnd');
    if(a&&!a.value){a.min=D.period[0];a.max=D.period[1];a.value=D.period[0];}
    if(b&&!b.value){b.min=D.period[0];b.max=D.period[1];b.value=D.period[1];}
    var d=dmData();h.innerHTML=dmHead(d.keys);document.getElementById('dmBody').innerHTML=dmBody(d.rows);
    var rv=dmRange(),inf=document.getElementById('dmInfo');if(inf)inf.textContent=(rv[0]||'')+' ~ '+(rv[1]||'')+' · '+d.rows.length+'품목';};
  window.openFullDayMargin=function(){var d=dmData();var rv=dmRange();openWindow('📅 상품별 일자별 마진(PPM) · '+(rv[0]||'')+'~'+(rv[1]||''),dmHead(d.keys),dmBody(d.rows));};
})();

/* ===== 메인 대시보드 로직 ===== */
const won=v=>Math.round(v).toLocaleString('ko-KR');const PER=15;
let gran='day',rmode='item',margMode='item',rpage=1,mpage=1,rankSort={col:1,dir:-1},marginSort={col:1,dir:-1};
var RANK_COLS=[['상품명',0,''],['GMV',1,'num'],['수량',2,'num']];
var MARGIN_COLS=[['상품명',0,''],['Revenue(GMV)',1,'num'],['판매수량',2,'num'],['AMV',3,'num'],['PPP',4,'num'],['PMC',5,'num'],['PPM',6,'num']];
function sortRows(arr,col,dir){return arr.sort(function(a,b){var x=a[col],y=b[col];if(typeof x==='number'&&typeof y==='number')return (x-y)*dir;return String(x).localeCompare(String(y))*dir;});}
function headHTML(cols,st,fn){return '<tr><th>#</th>'+cols.map(function(c){var ar=st.col===c[1]?(st.dir<0?' ▼':' ▲'):'';return '<th class="'+(c[2]?'num ':'')+'sorth" onclick="'+fn+'('+c[1]+')">'+c[0]+ar+'</th>';}).join('')+'</tr>';}
function toggleSort(st,col){if(st.col===col)st.dir=-st.dir;else{st.col=col;st.dir=(col===0?1:-1);}}
function sortRank(c){toggleSort(rankSort,c);rpage=1;renderRank();}
function sortMargin(c){toggleSort(marginSort,c);mpage=1;renderMargin();}
document.addEventListener('click',function(ev){var th=ev.target&&ev.target.closest?ev.target.closest('th'):null;if(!th)return;var tbl=th.closest('table');if(!tbl||tbl.className.indexOf('sortable')<0)return;var hd=th.closest('thead');if(!hd)return;var ths=Array.prototype.slice.call(hd.querySelectorAll('th')),ci=ths.indexOf(th),body=tbl.querySelector('tbody');if(!body||ci<0)return;var rows=Array.prototype.slice.call(body.querySelectorAll('tr'));var dir=th.getAttribute('data-dir')==='1'?-1:1;ths.forEach(function(o){o.removeAttribute('data-dir');});th.setAttribute('data-dir',dir===1?'1':'0');rows.sort(function(a,b){var ax=a.children[ci],bx=b.children[ci];var x=ax?ax.textContent.trim():'',y=bx?bx.textContent.trim():'';var nx=parseFloat(x.replace(/[^0-9.-]/g,'')),ny=parseFloat(y.replace(/[^0-9.-]/g,''));var both=!isNaN(nx)&&!isNaN(ny)&&/[0-9]/.test(x)&&/[0-9]/.test(y);return both?(nx-ny)*dir:x.localeCompare(y)*dir;});var renum=ths[0]&&ths[0].textContent.trim()==='#';rows.forEach(function(r,i){if(renum&&r.children[0])r.children[0].textContent=(i+1);body.appendChild(r);});});
function rangeVals(){return [document.getElementById('dStart').value,document.getElementById('dEnd').value];}
function facts(){var rv=rangeVals(),s=rv[0],e=rv[1];return D.F.filter(function(x){var d=x[0];if(s&&d<s)return false;if(e&&d>e)return false;return true;});}
function sumKPI(f){var o={gmv:0,units:0,ord:0,pv:0,amv:0,cogs:0,cpex:0};f.forEach(function(r){o.gmv+=r[4];o.units+=r[5];o.ord+=r[7];o.pv+=r[8];o.amv+=r[9];o.cogs+=r[10];o.cpex+=r[11];});o.aov=o.ord?o.gmv/o.ord:0;o.conv=o.pv?o.ord/o.pv*100:0;o.margin=o.amv?(o.amv-o.cogs)/o.amv*100:0;return o;}
function inRangeFacts(s,e){return D.F.filter(function(r){var d=r[0];return (!s||d>=s)&&(!e||d<=e);});}
function daysBetween(a,b){var pa=a.split('-'),pb=b.split('-');return Math.round((Date.UTC(+pb[0],+pb[1]-1,+pb[2])-Date.UTC(+pa[0],+pa[1]-1,+pa[2]))/864e5);}
function deltaBadge(cur,prev,rate){if(prev==null)return '';var d,sg,co;
if(rate){d=cur-prev;sg=d>=0?'▲':'▼';co=d>=0?'#10b981':'#ef4444';return '<div class="dlt" style="color:'+co+'">전기간比 '+sg+' '+Math.abs(d).toFixed(1)+'%p</div>';}
if(!prev)return '<div class="dlt" style="color:#9ca3af">전기간比 —</div>';
d=(cur-prev)/prev*100;sg=d>=0?'▲':'▼';co=d>=0?'#10b981':'#ef4444';return '<div class="dlt" style="color:'+co+'">전기간比 '+sg+' '+Math.abs(d).toFixed(1)+'%</div>';}
function renderKPIs(){var cur=sumKPI(facts());var vd=VATDIV();
var rv=rangeVals(),s=rv[0],e=rv[1],P=null;
if(s&&e){var L=daysBetween(s,e)+1,pe=isoShift(s,-1,0,0),ps=isoShift(pe,-(L-1),0,0);if(pe>=D.period[0])P=sumKPI(inRangeFacts(ps,pe));}
var ppmK=cur.gmv?((cur.gmv/vd-VATCOGS(cur.cogs)+(window.__pmcOn?-cur.cpex/vd:0))/(cur.gmv/vd))*100:0;
var ppmP=(P&&P.gmv)?((P.gmv/vd-VATCOGS(P.cogs)+(window.__pmcOn?-P.cpex/vd:0))/(P.gmv/vd))*100:0;
var cards=[
['결제 금액',won(cur.gmv/vd)+'원',P?deltaBadge(cur.gmv,P.gmv,false):''],
['주문 건수',won(cur.ord)+'건',P?deltaBadge(cur.ord,P.ord,false):''],
['판매 수량',won(cur.units)+'개',P?deltaBadge(cur.units,P.units,false):''],
['구매 전환율',cur.conv.toFixed(2)+'%',P?deltaBadge(cur.conv,P.conv,true):''],
['객단가',won(cur.aov/vd)+'원',P?deltaBadge(cur.aov,P.aov,false):''],
['평균판매가(ASP)',won((cur.units?cur.gmv/cur.units:0)/vd)+'원',P?deltaBadge(cur.units?cur.gmv/cur.units:0,(P.units?P.gmv/P.units:0),false):''],
['마진율(PPM)',ppmK.toFixed(1)+'%',P?deltaBadge(ppmK,ppmP,true):'']];
document.getElementById('kpis').innerHTML=cards.map(function(c){return '<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div>'+(c[2]||'')+'</div>';}).join('');}
var lineChartObj=new Chart(document.getElementById('lineChart'),{type:'line',data:{labels:[],datasets:[
{label:'GMV',data:[],borderColor:'#4f46e5',backgroundColor:'rgba(79,70,229,.1)',fill:true,tension:.35,yAxisID:'y'},
{label:'주문건수',data:[],borderColor:'#f59e0b',tension:.35,yAxisID:'y1'},
{label:'판매수량',data:[],borderColor:'#10b981',tension:.35,yAxisID:'y1'}]},
options:{responsive:true,interaction:{mode:'index',intersect:false},scales:{y:{position:'left',ticks:{callback:function(v){return won(v);}}},y1:{position:'right',grid:{drawOnChartArea:false}}}}});
function renderTrend(){var m=new Map();
facts().forEach(function(r){var iso=r[0];var k=gran==='year'?iso.slice(0,4):gran==='month'?iso.slice(0,7):iso;if(!m.has(k))m.set(k,[0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[7];a[2]+=r[5];});
var keys=Array.from(m.keys()).sort();lineChartObj.data.labels=keys;
lineChartObj.data.datasets[0].data=keys.map(function(k){return m.get(k)[0];});
lineChartObj.data.datasets[1].data=keys.map(function(k){return m.get(k)[1];});
lineChartObj.data.datasets[2].data=keys.map(function(k){return m.get(k)[2];});
lineChartObj.update();}
function setGran(g){gran=g;['day','month','year'].forEach(function(x){var b=document.getElementById('g_'+x);if(b)b.className=(x===g)?'active':'';});renderTrend();}
function pagerEl(el,page,pages,cb){el.innerHTML='';
function mk(t,p,act,dis){var b=document.createElement('button');b.textContent=t;if(act)b.className='active';if(dis)b.disabled=true;b.onclick=function(){cb(p);};el.appendChild(b);}
function sp(){var x=document.createElement('span');x.textContent='…';x.style.padding='0 4px';el.appendChild(x);}
mk('‹',Math.max(1,page-1),false,page===1);var a=Math.max(1,page-3),e=Math.min(pages,page+3);
if(a>1)mk('1',1,page===1,false);if(a>2)sp();
for(var i=a;i<=e;i++)mk(String(i),i,i===page,false);
if(e<pages-1)sp();if(e<pages)mk(String(pages),pages,page===pages,false);
mk('›',Math.min(pages,page+1),false,page===pages);}
function rankData(){var idx=rmode==='sku'?2:1,names=rmode==='sku'?D.SN:D.VN,m=new Map();
facts().forEach(function(r){var k=r[idx];if(!m.has(k))m.set(k,[0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];});
return Array.from(m.entries()).map(function(en){return [names[en[0]],en[1][0],en[1][1],en[0]];}).sort(function(a,b){return b[1]-a[1];});}
function renderRank(){var data=sortRows(rankData(),rankSort.col,rankSort.dir),pages=Math.max(1,Math.ceil(data.length/PER));if(rpage>pages)rpage=pages;var st=(rpage-1)*PER;
document.getElementById('rankHead').innerHTML=headHTML(RANK_COLS,rankSort,'sortRank');
document.getElementById('rankBody').innerHTML=data.slice(st,st+PER).map(function(r,i){var nm=(rmode==='sku')?('<a class="link" onclick="showSkuItems('+r[3]+')">'+r[0]+'</a>'):r[0];return '<tr><td class="rk">'+(st+i+1)+'</td><td>'+nm+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}).join('');
document.getElementById('rankInfo').textContent='전체 '+data.length+'개 · '+rpage+'/'+pages+' 페이지';
pagerEl(document.getElementById('pager'),rpage,pages,function(p){rpage=p;renderRank();});}
function setMode(m){rmode=m;rpage=1;var bi=document.getElementById('btnItem'),bs=document.getElementById('btnSku');if(bi)bi.className=(m==='sku')?'':'active';if(bs)bs.className=(m==='sku')?'active':'';renderRank();}
function setMargMode(m){margMode=m;mpage=1;var bi=document.getElementById('btnMItem'),bs=document.getElementById('btnMSku');if(bi)bi.className=(m==='sku')?'':'active';if(bs)bs.className=(m==='sku')?'active':'';renderMargin();}
function openWindow(title,headHtml,bodyHtml){var w=window.open('','_blank','width=1280,height=820,scrollbars=yes');if(!w){alert('팝업이 차단되었습니다. 팝업을 허용한 뒤 다시 시도하세요.');return;}
w.document.write('<!doctype html><html><head><meta charset="utf-8"><title>'+title+'</title><style>html,body{height:100%}body{font-family:\'Malgun Gothic\',sans-serif;margin:0;background:#eef2f7;color:#1f2937;word-break:keep-all;display:flex;flex-direction:column}.hd{padding:16px 18px 4px;flex:0 0 auto}h2{font-size:16px;border-left:4px solid #4f46e5;padding-left:10px;color:#111827;margin:0}.tip{color:#9ca3af;font-size:12px;margin:6px 0 0}.scroller{flex:1 1 auto;margin:12px 14px;background:#fff;border-radius:14px;box-shadow:0 1px 4px rgba(15,23,42,.07);overflow:auto}table{border-collapse:collapse;font-size:13px;width:max-content;min-width:100%}th,td{padding:7px 10px;border-bottom:1px solid #eef0f3;text-align:left;white-space:nowrap}th{color:#6b7280;position:sticky;top:0;background:#fff;cursor:pointer;user-select:none;z-index:1}th:hover{color:#4f46e5}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.rk{color:#4f46e5;font-weight:700;width:46px}.mbw{background:#eef2f7;border-radius:6px;height:14px;overflow:hidden;min-width:140px}.mb{height:100%;background:#4f46e5;border-radius:6px}</style></head><body><div class="hd"><h2>'+title+'</h2><div class="tip">컬럼 헤더를 클릭하면 정렬됩니다.</div></div><div class="scroller"><table><thead>'+headHtml+'</thead><tbody>'+bodyHtml+'</tbody></table></div></body></html>');w.document.close();
var tb=w.document.querySelector('table'),ths=tb.querySelectorAll('thead th');
ths.forEach(function(th,ci){if(ci===0)return;th.onclick=function(){var body=tb.querySelector('tbody'),rows=Array.prototype.slice.call(body.querySelectorAll('tr')),dir=th.getAttribute('data-dir')==='1'?-1:1;ths.forEach(function(o){o.removeAttribute('data-dir');});th.setAttribute('data-dir',dir===1?'1':'0');rows.sort(function(a,b){var x=a.children[ci].textContent.trim(),y=b.children[ci].textContent.trim(),nx=parseFloat(x.replace(/[^0-9.-]/g,'')),ny=parseFloat(y.replace(/[^0-9.-]/g,'')),both=!isNaN(nx)&&!isNaN(ny)&&/[0-9]/.test(x)&&/[0-9]/.test(y);return both?(nx-ny)*dir:x.localeCompare(y)*dir;});var renum=ths[0]&&ths[0].textContent.trim()==='#';rows.forEach(function(r,i){if(renum&&r.children[0])r.children[0].textContent=(i+1);body.appendChild(r);});};});}
function openFullRank(){var data=sortRows(rankData(),rankSort.col,rankSort.dir);
var head='<tr><th>#</th><th>상품명</th><th class="num">GMV</th><th class="num">수량</th></tr>';
var body=data.map(function(r,i){return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}).join('');
openWindow('🏆 제품 순위 ('+(rmode==='sku'?'상품별':'벤더아이템별')+') — 전체 '+data.length+'개 · '+rangeVals()[0]+'~'+rangeVals()[1],head,body);}
function openFullMargin(){var data=sortRows(marginData(),marginSort.col,marginSort.dir);
var head='<tr><th>#</th><th>상품명</th><th class="num">Revenue(GMV)</th><th class="num">판매수량</th><th class="num">AMV</th><th class="num">PPP(판촉비차감전)</th><th class="num">PMC</th><th class="num">PPM</th></tr>';
var body=data.map(function(r,i){var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}).join('');
openWindow('💰 상품별 마진·순위 ('+(margMode==='sku'?'상품별':'벤더아이템별')+') — 전체 '+data.length+'개 · '+rangeVals()[0]+'~'+rangeVals()[1],head,body);}
function renderCat(){}
function marginData(){var idx=margMode==='sku'?2:1,names=margMode==='sku'?D.SN:D.VN,vd=VATDIV(),m=new Map();facts().forEach(function(r){var k=r[idx];if(!m.has(k))m.set(k,[0,0,0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];a[2]+=r[9];a[3]+=r[10];a[4]+=r[11];});
return Array.from(m.entries()).map(function(en){var gmv=en[1][0]/vd,units=en[1][1],amv=en[1][2]/vd,pmc=-en[1][4]/vd,ppp=gmv-VATCOGS(en[1][3]),ppm=gmv?(ppp+(window.__pmcOn?pmc:0))/gmv*100:0;return [names[en[0]],gmv,units,amv,ppp,pmc,ppm,en[0]];}).sort(function(a,b){return b[1]-a[1];});}
function showSkuMargin(si){var f=facts().filter(function(r){return r[2]===si;}),vd=VATDIV(),m=new Map();
f.forEach(function(r){var k=r[1];if(!m.has(k))m.set(k,[0,0,0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];a[2]+=r[9];a[3]+=r[10];a[4]+=r[11];});
var rows=Array.from(m.entries()).map(function(en){var gmv=en[1][0]/vd,units=en[1][1],amv=en[1][2]/vd,pmc=-en[1][4]/vd,ppp=gmv-VATCOGS(en[1][3]),ppm=gmv?(ppp+(window.__pmcOn?pmc:0))/gmv*100:0;return [D.VN[en[0]],gmv,units,amv,ppp,pmc,ppm];}).sort(function(a,b){return b[1]-a[1];});
document.getElementById('modalHead').innerHTML='<tr><th>벤더아이템</th><th class="num">GMV</th><th class="num">판매수량</th><th class="num">AMV</th><th class="num">PPP</th><th class="num">PMC</th><th class="num">PPM</th></tr>';
document.getElementById('modalBody').innerHTML=rows.map(function(r){var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}).join('');
document.getElementById('modalTitle').textContent=D.SN[si]+' — 벤더아이템별 마진 ('+rangeVals()[0]+'~'+rangeVals()[1]+')';
document.getElementById('modal').classList.add('open');}
function renderMargin(){var gmv=0,units=0,amv=0,cogs=0,cpex=0;facts().forEach(function(r){gmv+=r[4];units+=r[5];amv+=r[9];cogs+=r[10];cpex+=r[11];});var vd=VATDIV();var pmc=-cpex/vd,ppp=gmv/vd-VATCOGS(cogs),ppm=(gmv/vd)?(ppp+(window.__pmcOn?pmc:0))/(gmv/vd)*100:0;gmv=gmv/vd;amv=amv/vd;
var cards=[['Revenue(GMV)',won(gmv)+'원'],['판매수량',won(units)+'개'],['조정매출(AMV)',won(amv)+'원'],['PPP(매출총이익)',won(ppp)+'원'],['PMC',won(pmc)+'원'],['PPM',ppm.toFixed(1)+'%']];
document.getElementById('marginKpis').innerHTML=cards.map(function(c){return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}).join('');
var data=sortRows(marginData(),marginSort.col,marginSort.dir),pages=Math.max(1,Math.ceil(data.length/PER));if(mpage>pages)mpage=pages;var st=(mpage-1)*PER;
document.getElementById('marginHead').innerHTML=headHTML(MARGIN_COLS,marginSort,'sortMargin');
document.getElementById('marginBody').innerHTML=data.slice(st,st+PER).map(function(r,i){var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';var nm=(margMode==='sku')?('<a class="link" onclick="showSkuMargin('+r[7]+')">'+r[0]+'</a>'):r[0];return '<tr><td class="rk">'+(st+i+1)+'</td><td>'+nm+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}).join('');
document.getElementById('marginInfo').textContent='전체 '+data.length+'개';
pagerEl(document.getElementById('marginPager'),mpage,pages,function(p){mpage=p;renderMargin();});}
function centerTotalsRange(s,e){if(!D.mtx||!D.mtx.lf)return null;var t=D.mtx.centers.map(function(){return 0;});D.mtx.lf.forEach(function(r){var d=r[0];if((!s||d>=s)&&(!e||d<=e))t[r[2]]+=r[3];});return t;}
var grState={unit:'month',buckets:[],idx:0};
function growthBuckets(unit){if(!D.mtx||!D.mtx.lf)return [];var dd={};D.mtx.lf.forEach(function(r){dd[r[0]]=1;});var ds=Object.keys(dd).sort();if(!ds.length)return [];var lo=ds[0],hi=ds[ds.length-1],seen={},keys=[];
if(unit==='month'){ds.forEach(function(d){var k=d.slice(0,7);if(!seen[k]){seen[k]=1;keys.push(k);}});keys.sort();return keys.map(function(k,i){var s=k+'-01',e=isoShift(k+'-01',-1,1,0);if(s<lo)s=lo;if(e>hi)e=hi;var pv=i>0?keys[i-1]:null,ps=pv?pv+'-01':null,pe=pv?isoShift(pv+'-01',-1,1,0):null;if(ps&&ps<lo)ps=lo;if(pe&&pe>hi)pe=hi;return {label:(+k.slice(0,4))+'년 '+(+k.slice(5,7))+'월',s:s,e:e,ps:ps,pe:pe};});}
ds.forEach(function(d){var m=mondayOf(d);if(!seen[m]){seen[m]=1;keys.push(m);}});keys.sort();return keys.map(function(m,i){var s=m,e=isoShift(m,6,0,0);if(s<lo)s=lo;if(e>hi)e=hi;var pv=i>0?keys[i-1]:null,ps=pv,pe=pv?isoShift(pv,6,0,0):null;if(ps&&ps<lo)ps=lo;if(pe&&pe>hi)pe=hi;var wk=isoWeek(m);return {label:wk[0]+'년 '+wk[1]+'주차 ('+s.slice(5)+'~'+e.slice(5)+')',s:s,e:e,ps:ps,pe:pe};});}
function growthRows(){if(!D.mtx||!D.mtx.lf)return {rows:[],prev:false,label:''};var b=grState.buckets[grState.idx];if(!b)return {rows:[],prev:false,label:''};
var cur=centerTotalsRange(b.s,b.e),prev=b.ps?centerTotalsRange(b.ps,b.pe):null;var cs=D.mtx.centers;
var rows=cs.map(function(c,i){return [c,cur[i],prev?prev[i]:null];}).filter(function(r){return r[1]>0||(r[2]&&r[2]>0);}).sort(function(a,b){return b[1]-a[1];});return {rows:rows,prev:!!prev,label:b.label};}
function dcell(cur,prev){if(prev==null)return '<td class="num" style="color:#9ca3af">—</td>';var d=prev?((cur-prev)/prev*100):(cur>0?100:0),sg=d>=0?'▲':'▼',co=d>=0?'#10b981':'#ef4444';return '<td class="num" style="color:'+co+';font-weight:600">'+sg+' '+Math.abs(d).toFixed(1)+'%</td>';}
function gbodyHTML(g){return g.rows.map(function(r,i){return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+(r[2]==null?'—':won(r[2]))+'</td>'+dcell(r[1],r[2])+'</tr>';}).join('');}
function renderGrowth(){var gb=document.getElementById('grBody');if(!gb)return;var g=growthRows();gb.innerHTML=gbodyHTML(g);var gi=document.getElementById('grInfo');if(gi)gi.textContent=(g.label||'')+(g.prev?' · 직전 기간 대비 · 출고 기준':' · 직전 기간 없음 · 출고 기준');}
function onGrowthUnit(){grState.unit=document.getElementById('grUnit').value;grState.buckets=growthBuckets(grState.unit);grState.idx=Math.max(0,grState.buckets.length-1);var pick=document.getElementById('grPick');if(pick){pick.innerHTML=grState.buckets.map(function(b,i){return '<option value="'+i+'">'+b.label+'</option>';}).join('');pick.value=String(grState.idx);}renderGrowth();}
function onGrowthPick(){grState.idx=+document.getElementById('grPick').value;renderGrowth();}
function openFullGrowth(){var g=growthRows();var head='<tr><th>#</th><th>센터</th><th class="num">이번 기간</th><th class="num">직전 기간</th><th class="num">증감률</th></tr>';
openWindow('🏭 센터별 성장 — '+(g.label||'')+(g.prev?' (직전 기간 대비)':''),head,gbodyHTML(g));}
function renderAll(){renderKPIs();renderTrend();renderMargin();renderByCenter();renderMatrix(mtxMetric);renderSkuTime();if(window.renderPerf)renderPerf();if(window.renderDayMargin)renderDayMargin();updateRangeInfo();}
function onRange(){rpage=1;mpage=1;renderAll();}
function setFull(){document.getElementById('dStart').value=D.period[0];document.getElementById('dEnd').value=D.period[1];onRange();}
function isoShift(iso,days,months,years){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));if(years)dt.setUTCFullYear(dt.getUTCFullYear()+years);if(months)dt.setUTCMonth(dt.getUTCMonth()+months);if(days)dt.setUTCDate(dt.getUTCDate()+days);return dt.toISOString().slice(0,10);}
function mondayOf(iso){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),wd=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-wd);return dt.toISOString().slice(0,10);}
function isoWeek(iso){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),day=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-day+3);var y=dt.getUTCFullYear(),ft=new Date(Date.UTC(y,0,4)),fd=(ft.getUTCDay()+6)%7;ft.setUTCDate(ft.getUTCDate()-fd+3);return [y,1+Math.round((dt-ft)/6048e5)];}
function uniqueDates(){var s={};D.F.forEach(function(r){s[r[0]]=1;});return Object.keys(s).sort();}
function buckets(unit){var ds=uniqueDates();if(!ds.length)return [];var lo=ds[0],hi=ds[ds.length-1],seen={},out=[];
if(unit==='month'){ds.forEach(function(d){var k=d.slice(0,7);if(!seen[k]){seen[k]=1;var s=k+'-01',e=isoShift(k+'-01',-1,1,0);if(s<lo)s=lo;if(e>hi)e=hi;out.push({label:(+k.slice(0,4))+'년 '+(+k.slice(5,7))+'월',start:s,end:e});}});}
else if(unit==='year'){ds.forEach(function(d){var k=d.slice(0,4);if(!seen[k]){seen[k]=1;var s=k+'-01-01',e=k+'-12-31';if(s<lo)s=lo;if(e>hi)e=hi;out.push({label:k+'년',start:s,end:e});}});}
else if(unit==='week'){var keys=[];ds.forEach(function(d){var m=mondayOf(d);if(!seen[m]){seen[m]=1;keys.push(m);}});keys.sort();keys.forEach(function(m){var s=m,e=isoShift(m,6,0,0);if(s<lo)s=lo;if(e>hi)e=hi;var wk=isoWeek(m);out.push({label:wk[0]+'년 '+wk[1]+'주차 ('+s.slice(5)+'~'+e.slice(5)+')',start:s,end:e});});}
return out;}
var BK=[];
function onUnit(){var u=document.getElementById('pUnit').value,pick=document.getElementById('pPick');
if(u==='all'){pick.style.display='none';pick.innerHTML='';setFull();return;}
pick.style.display='';BK=buckets(u);
pick.innerHTML=BK.map(function(b,i){return '<option value="'+i+'">'+b.label+'</option>';}).join('');
pick.value=String(BK.length-1);applyBucket(BK.length-1);}
function onPick(){applyBucket(+document.getElementById('pPick').value);}
function applyBucket(i){var b=BK[i];if(!b)return;document.getElementById('dStart').value=b.start;document.getElementById('dEnd').value=b.end;rpage=1;mpage=1;renderAll();}
function updateRangeInfo(){var rv=rangeVals();document.getElementById('rangeInfo').textContent=rv[0]+' ~ '+rv[1];}
function showDetail(sid,name){var rows=(D.sd[sid]||[]);var tb=document.getElementById('modalBody');tb.innerHTML='';
document.getElementById('modalHead').innerHTML='<tr><th>센터</th><th class="num">재고</th><th>상태</th></tr>';
rows.forEach(function(r){var cls=r[2]==='품절'?' style="color:#ef4444;font-weight:600"':'';tb.insertAdjacentHTML('beforeend','<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td'+cls+'>'+r[2]+'</td></tr>');});
document.getElementById('modalTitle').textContent=name+' — 센터별 재고 (기준일 '+D.ld+')';
document.getElementById('modal').classList.add('open');}
function showSkuItems(si){var f=facts().filter(function(r){return r[2]===si;}),m=new Map();
f.forEach(function(r){var k=r[1];if(!m.has(k))m.set(k,[0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];});
var rows=Array.from(m.entries()).map(function(en){return [D.VN[en[0]],en[1][0],en[1][1]];}).sort(function(a,b){return b[1]-a[1];});
document.getElementById('modalHead').innerHTML='<tr><th>벤더아이템</th><th class="num">GMV</th><th class="num">수량</th></tr>';
document.getElementById('modalBody').innerHTML=rows.map(function(r){return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}).join('');
document.getElementById('modalTitle').textContent=D.SN[si]+' — 벤더아이템별 ('+rangeVals()[0]+'~'+rangeVals()[1]+')';
document.getElementById('modal').classList.add('open');}
function closeModal(){document.getElementById('modal').classList.remove('open');}
var mtxMetric='o',skuMetric='o';
function hcell(v,mx){if(!v)return '<td class="num z">·</td>';var a=mx>0?Math.min(0.85,v/mx*0.85):0;return '<td class="num" style="background:rgba(79,70,229,'+a.toFixed(3)+');color:'+(a>0.45?'#fff':'#1f2937')+'">'+won(v)+'</td>';}
function lfAgg(metric){var cs=D.mtx.centers,nc=cs.length,perc=[],bySku={};for(var i=0;i<nc;i++)perc.push(0);
if(metric==='s'){D.mtx.stk.forEach(function(r){var si=r[0],ci=r[1],v=r[2];if(!bySku[si]){bySku[si]=[];for(var j=0;j<nc;j++)bySku[si].push(0);}bySku[si][ci]+=v;perc[ci]+=v;});}
else{var rv=rangeVals(),s=rv[0],e=rv[1],mi=metric==='i'?4:3;D.mtx.lf.forEach(function(r){var d=r[0];if((s&&d<s)||(e&&d>e))return;var si=r[1],ci=r[2],v=r[mi];if(!bySku[si]){bySku[si]=[];for(var j=0;j<nc;j++)bySku[si].push(0);}bySku[si][ci]+=v;perc[ci]+=v;});}
return {perc:perc,bySku:bySku};}
function mtxTop3(perc){var rk={};perc.map(function(t,i){return [i,t];}).sort(function(a,b){return b[1]-a[1];}).slice(0,3).forEach(function(p,k){if(p[1]>0)rk[p[0]]=k+1;});return rk;}
function mtxHeadHTML(cs,rk){var med=['🥇','🥈','🥉'];return '<tr><th>상품명</th><th class="num">합계</th>'+cs.map(function(c,ci){var m=rk[ci]?(med[rk[ci]-1]+' '):'';var st=rk[ci]?' style="background:#eef2ff"':'';return '<th class="num"'+st+'>'+m+c+'</th>';}).join('')+'</tr>';}
function mtxRows(ag){return Object.keys(ag.bySku).map(function(si){var arr=ag.bySku[si],tot=0;arr.forEach(function(v){tot+=v;});return {name:D.mtx.skus[si],arr:arr,tot:tot};}).filter(function(o){return o.tot>0;}).sort(function(a,b){return b.tot-a.tot;}).slice(0,100);}
function mtxBodyHTML(rows){return rows.map(function(o){var mx=0;o.arr.forEach(function(v){if(v>mx)mx=v;});var tds=o.arr.map(function(v){return hcell(v,mx);}).join('');return '<tr><td>'+o.name+'</td><td class="num" style="font-weight:700">'+won(o.tot)+'</td>'+tds+'</tr>';}).join('');}
function renderMatrix(metric){if(!D.mtx)return;mtxMetric=metric;var ag=lfAgg(metric);document.getElementById('mtxHead').innerHTML=mtxHeadHTML(D.mtx.centers,mtxTop3(ag.perc));document.getElementById('mtxBody').innerHTML=mtxBodyHTML(mtxRows(ag));}
function setMtx(m){['o','i','s'].forEach(function(x){var b=document.getElementById('mtx'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';});renderMatrix(m);}
function openFullMatrix(){if(!D.mtx)return;var ag=lfAgg(mtxMetric);openWindow('🗺️ 품목 × 센터 매트릭스 — '+({o:'출고',i:'입고',s:'재고(현재)'}[mtxMetric])+' · '+rangeVals()[0]+'~'+rangeVals()[1],mtxHeadHTML(D.mtx.centers,mtxTop3(ag.perc)),mtxBodyHTML(mtxRows(ag)));}
function skuCenters(si,metric){var cs=D.mtx.centers,arr=[];for(var i=0;i<cs.length;i++)arr.push(0);
if(metric==='s'){D.mtx.stk.forEach(function(r){if(r[0]===si)arr[r[1]]+=r[2];});}
else{var rv=rangeVals(),s=rv[0],e=rv[1],mi=metric==='i'?4:3;D.mtx.lf.forEach(function(r){if(r[1]!==si)return;var d=r[0];if((s&&d<s)||(e&&d>e))return;arr[r[2]]+=r[mi];});}
return arr;}
function skuPairs(si,metric){var cs=D.mtx.centers,arr=skuCenters(si,metric);return cs.map(function(c,i){return [c,arr[i]];}).sort(function(a,b){return b[1]-a[1];});}
function skuRowsHTML(pairs){var mx=1;pairs.forEach(function(p){if(p[1]>mx)mx=p[1];});var tot=pairs.reduce(function(a,p){return a+p[1];},0);return pairs.map(function(p,i){var pct=Math.round(p[1]/mx*100),sh=tot?Math.round(p[1]/tot*100):0;return '<tr><td class="rk">'+(i+1)+'</td><td>'+p[0]+'</td><td class="num">'+won(p[1])+'</td><td><div class="mbw"><div class="mb" style="width:'+pct+'%"></div></div></td><td class="num">'+sh+'%</td></tr>';}).join('');}
function renderSku(){if(!D.mtx)return;var si=+document.getElementById('skuPick').value;document.getElementById('skuBody').innerHTML=skuRowsHTML(skuPairs(si,skuMetric));}
function setSkuMetric(m){skuMetric=m;['o','i','s'].forEach(function(x){var b=document.getElementById('sku'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';});renderSku();}
function openFullSku(){if(!D.mtx)return;var si=+document.getElementById('skuPick').value;var head='<tr><th>#</th><th>센터</th><th class="num">수량</th><th>비중</th><th class="num">점유</th></tr>';openWindow('📦 '+D.mtx.skus[si]+' — 센터별 '+({o:'출고',i:'입고',s:'재고'}[skuMetric])+' · '+rangeVals()[0]+'~'+rangeVals()[1],head,skuRowsHTML(skuPairs(si,skuMetric)));}
function renderByCenter(){if(!D.mtx)return;var rv=rangeVals(),s=rv[0],e=rv[1],cs=D.mtx.centers,inb=[],outb=[];for(var i=0;i<cs.length;i++){inb.push(0);outb.push(0);}
D.mtx.lf.forEach(function(r){var d=r[0];if((s&&d<s)||(e&&d>e))return;outb[r[2]]+=r[3];inb[r[2]]+=r[4];});
var rows=cs.map(function(c,i){return [c,inb[i],outb[i]];}).sort(function(a,b){return b[2]-a[2];});
var tb=document.getElementById('bcBody');if(tb)tb.innerHTML=rows.map(function(r){return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td></tr>';}).join('');
var ti=0,to=0;inb.forEach(function(v){ti+=v;});outb.forEach(function(v){to+=v;});var ei=document.getElementById('logiInb'),eo=document.getElementById('logiOutb');if(ei)ei.textContent=won(ti)+'개';if(eo)eo.textContent=won(to)+'개';}
var stMetric='o',stUnit='day';
function stRange(){var s=document.getElementById('stStart'),e=document.getElementById('stEnd');return [s?s.value:'', e?e.value:''];}
function dateKeys(unit,s,e){var set={};D.mtx.lf.forEach(function(r){var d=r[0];if((s&&d<s)||(e&&d>e))return;var k=unit==='month'?d.slice(0,7):d;set[k]=1;});return Object.keys(set).sort();}
function colLabel(k,unit){return unit==='month'?((+k.slice(0,4))+'.'+(+k.slice(5,7))):k.slice(5);}
function timeMtxHead(keys,unit,firstCol){return '<tr><th>'+firstCol+'</th>'+keys.map(function(k){return '<th class="num">'+colLabel(k,unit)+'</th>';}).join('')+'<th class="num">합계</th></tr>';}
function timeMtxBody(rows){return rows.map(function(o){var mx=0;o.arr.forEach(function(v){if(v>mx)mx=v;});var tds=o.arr.map(function(v){return hcell(v,mx);}).join('');return '<tr><td>'+o.name+'</td>'+tds+'<td class="num" style="font-weight:700">'+won(o.tot)+'</td></tr>';}).join('');}
function skuTimeAgg(metric,unit){var rv=stRange(),s=rv[0],e=rv[1];
var src,ki,vi,names;
if(metric==='s'){src=D.F;ki=2;vi=5;names=D.SN;}   // 판매수량: 판매데이터 D.F (r[2]=SKU명, r[5]=판매수량)
else{if(!D.mtx)return {keys:[],rows:[]};src=D.mtx.lf;ki=1;vi=(metric==='i'?4:3);names=D.mtx.skus;}  // 출고/입고: 물류 lf
var seen={};src.forEach(function(r){var d=r[0];if((s&&d<s)||(e&&d>e))return;seen[unit==='month'?d.slice(0,7):d]=1;});
var keys=Object.keys(seen).sort(),kidx={};keys.forEach(function(k,i){kidx[k]=i;});
var bySku={};src.forEach(function(r){var d=r[0];if((s&&d<s)||(e&&d>e))return;var k=unit==='month'?d.slice(0,7):d;var si=r[ki];if(!bySku[si])bySku[si]=keys.map(function(){return 0;});bySku[si][kidx[k]]+=r[vi];});
var rows=Object.keys(bySku).map(function(si){var arr=bySku[si],tot=0;arr.forEach(function(v){tot+=v;});return {name:names[si],arr:arr,tot:tot};}).filter(function(o){return o.tot>0;}).sort(function(a,b){return b.tot-a.tot;}).slice(0,100);return {keys:keys,rows:rows};}
function renderSkuTime(){if(!D.mtx)return;var h=document.getElementById('stHead');if(!h)return;var ag=skuTimeAgg(stMetric,stUnit);h.innerHTML=timeMtxHead(ag.keys,stUnit,'상품명');document.getElementById('stBody').innerHTML=timeMtxBody(ag.rows);var rv=stRange(),info=document.getElementById('stInfo');if(info)info.textContent=(rv[0]||'')+' ~ '+(rv[1]||'')+' · '+ag.rows.length+'품목';}
function stReset(){var lo=D.period[0],hi=D.period[1];var s=document.getElementById('stStart'),e=document.getElementById('stEnd');if(s)s.value=lo;if(e)e.value=hi;renderSkuTime();}
function setSkuTime(m){['o','i','s'].forEach(function(x){var b=document.getElementById('st'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';});stMetric=m;renderSkuTime();}
function setStUnit(u){['day','month'].forEach(function(x){var b=document.getElementById('st'+(x==='day'?'Day':'Mon'));if(b)b.className=(x===u)?'active':'';});stUnit=u;renderSkuTime();}
function openFullSkuTime(){var ag=skuTimeAgg(stMetric,stUnit);var rv=stRange();openWindow('📦 상품 × '+(stUnit==='month'?'월':'일자')+' — '+({o:'출고',i:'입고',s:'판매수량'}[stMetric])+' · '+(rv[0]||'')+'~'+(rv[1]||''),timeMtxHead(ag.keys,stUnit,'상품명'),timeMtxBody(ag.rows));}
function initDashboard(){var ds=document.getElementById('dStart'),de=document.getElementById('dEnd');var lo=D.period[0],hi=D.period[1];ds.min=lo;ds.max=hi;ds.value=lo;de.min=lo;de.max=hi;de.value=hi;if(D.mtx){var sp=document.getElementById('skuPick');if(sp)sp.innerHTML=D.mtx.skus.map(function(n,i){return '<option value="'+i+'">'+n+'</option>';}).join('');var ss=document.getElementById('stStart'),se2=document.getElementById('stEnd');if(ss){ss.min=lo;ss.max=hi;ss.value=lo;}if(se2){se2.min=lo;se2.max=hi;se2.value=hi;}}renderAll();if(D.mtx&&D.mtx.lf&&document.getElementById('grUnit'))onGrowthUnit();}
window.initDashboard=initDashboard;
