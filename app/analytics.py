# -*- coding: utf-8 -*-
"""
판매/물류 대시보드 생성기 (GUI 실행파일)
==========================================
파일(CSV 또는 엑셀)을 선택하면 자동으로 판매/물류 데이터를 판별해
HTML 대시보드 + 엑셀 대시보드를 생성하고 브라우저로 열어줍니다.
"""
import os, sys, csv, json, datetime, threading, webbrowser, base64
from collections import defaultdict

def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

def get_logo_b64():
    """푸르밀 로고를 base64로 반환 (없으면 빈 문자열)."""
    try:
        from _logo import LOGO_B64
        return LOGO_B64
    except Exception:
        pass
    for d in (getattr(sys, "_MEIPASS", None),
              os.path.dirname(os.path.abspath(sys.argv[0])), os.getcwd()):
        if not d:
            continue
        p = os.path.join(d, "purmil.png")
        if os.path.exists(p):
            try:
                return base64.b64encode(open(p, "rb").read()).decode()
            except Exception:
                pass
    return ""

# ===================================================================
#  데이터 처리 (CSV / XLSX 공통)
# ===================================================================
def num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return 0.0

def norm(s):
    return str(s).replace(" ", "")

def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def ci(header, name, exact=False):
    n = norm(name)
    if exact:
        for i, h in enumerate(header):
            if norm(h) == n:
                return i
    for i, h in enumerate(header):
        if n in norm(h):
            return i
    return -1

def fdate(d):
    s = str(d).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if len(s) == 8 and s.isdigit():
        return f"{s[4:6]}-{s[6:8]}"
    return s

def _ym(d):
    """날짜를 'YYYY-MM'(월)로. 인식 실패 시 빈 문자열."""
    s = str(d).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}"
    if len(s) >= 7 and s[4:5] == "-":
        return s[:7]
    return ""

# 쿠팡 리포트 포맷 변경 대응: 신규 헤더 이름 → 표준(기존) 이름으로 정규화.
# (물류 헤더는 신규=기존 동일이라 매핑 불필요. 판매만 열 이름이 바뀜.)
_HEADER_ALIAS = {
    "상품 ID": "Product ID",
    "SKU명": "SKU 명",
    "판매 수량 (SKU ID)": "판매수량(Units Sold)",
    "반품 수량": "반품수량(Return Units)",
    "조회수": "PV",
    "구매전환율 (%)": "구매전환율",
    "프로모션 발생 매출액": "프로모션발생매출액(GMV)",
    "프로모션 발생 판매 수량": "프로모션발생판매수량(Units Sold)",
    "평균 판매 금액": "평균판매금액(ASP)",
}

def _iso_date(v):
    """날짜를 ISO 'YYYY-MM-DD'로 통일. '20260701'·'2026-07-01'·'2026/07/01 00:00:00' 등 모두 처리."""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if len(s) >= 10 and s[4] in "-/." and s[7] in "-/.":
        return s[:4] + "-" + s[5:7] + "-" + s[8:10]
    if len(s) == 8 and s.isdigit():
        return s[:4] + "-" + s[4:6] + "-" + s[6:8]
    return s

def _norm_table(header, rows):
    """헤더 이름을 표준화하고, '날짜' 열 값을 ISO로 통일 (구/신 포맷 정합)."""
    header = [_HEADER_ALIAS.get(str(c).strip(), c) for c in header]
    di = next((i for i, h in enumerate(header) if str(h).strip() == "날짜"), -1)
    if di >= 0:
        for r in rows:
            if di < len(r):
                r[di] = _iso_date(r[di])
    return header, rows

def read_table(path):
    """CSV 또는 XLSX 파일을 (header, rows) 로 읽는다. 헤더·날짜를 표준 형식으로 정규화."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        data = [[cell(c) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
        if not data:
            return [], []
        return _norm_table(data[0], data[1:])
    # CSV
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            return _norm_table(rows[0], rows[1:]) if rows else ([], [])
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 인식할 수 없습니다: " + os.path.basename(path))

def classify(header):
    """헤더를 보고 'sales' / 'logi' / None 판별."""
    joined = norm("".join(header))
    if "현재재고수량" in joined or "품절여부" in joined:
        return "logi"
    if "구매전환율" in joined or ("주문건수" in joined and "매출액" in joined):
        return "sales"
    return None

# ---------- 판매 집계 ----------
def analyze_sales(header, data):
    c = dict(
        date=ci(header, "날짜", True), sku=ci(header, "SKU명", True),
        cat=ci(header, "세부카테고리", True), gmv=ci(header, "매출액"),
        units=ci(header, "판매수량"), ret=ci(header, "반품수량"),
        orders=ci(header, "주문건수", True), cust=ci(header, "주문고객수", True),
        pv=ci(header, "PV", True), conv=ci(header, "구매전환율"),
        vid=ci(header, "벤더아이템ID", True), vname=ci(header, "벤더아이템명", True),
        amv=ci(header, "AMV", True), cogs=ci(header, "매입원가"),
        skuid=ci(header, "SKU ID", True),
        cpex=ci(header, "쿠팡 추가 할인가", True),   # PMC 원천(정확 일치 — '쿠폰 할인가(쿠팡 추가 할인가 제외)'와 혼동 방지)
    )
    if c['skuid'] < 0: c['skuid'] = ci(header, "SKUID", True)
    if c['pv'] < 0: c['pv'] = ci(header, "조회수", True)   # 신규 포맷: PV → 조회수 (정규화 누락 대비)
    tot = dict(gmv=0.0, units=0.0, ret=0.0, orders=0.0, cust=0.0, pv=0.0, amv=0.0, cogs=0.0)
    by_date = defaultdict(lambda: [0.0, 0.0, 0.0])
    by_item = defaultdict(lambda: [0.0, 0.0, "", 0.0, 0.0])  # gmv, units, 이름, amv, cogs
    by_sku  = defaultdict(lambda: [0.0, 0.0])      # SKU 명 기준(상품별)
    by_cat = defaultdict(float)
    by_month_sku = defaultdict(lambda: [0.0, 0.0, "", 0.0])  # (월,SKUID) -> gmv, units, SKU명, COGS
    facts = []   # 날짜별 원본(HTML 기간필터용): (date,vdisp,sku,cat,gmv,units,ret,ord,pv,amv,cogs)
    mx = max(v for v in c.values() if v >= 0)
    for r in data:
        if len(r) <= mx:
            continue
        g=num(r[c['gmv']]); u=num(r[c['units']]); rt=num(r[c['ret']])
        o=num(r[c['orders']]); cu=num(r[c['cust']]); pv=num(r[c['pv']])
        amv=num(r[c['amv']]) if c['amv']>=0 else 0.0
        cogs=num(r[c['cogs']]) if c['cogs']>=0 else 0.0
        cpex=num(r[c['cpex']]) if c['cpex']>=0 else 0.0   # 쿠팡 추가 할인가(부가세 포함)
        amv=amv if amv!=0 else g   # AMV 미적용(0)이면 GMV로 대체 → 마진 왜곡 방지
        tot['gmv']+=g; tot['units']+=u; tot['ret']+=rt
        tot['orders']+=o; tot['cust']+=cu; tot['pv']+=pv
        tot['amv']+=amv; tot['cogs']+=cogs
        d=r[c['date']]
        by_date[d][0]+=g; by_date[d][1]+=o; by_date[d][2]+=u
        skun = r[c['sku']] if c['sku']>=0 else ""
        vn   = r[c['vname']] if c['vname']>=0 else ""
        vdisp = vn if vn else skun
        catn = r[c['cat']] if c['cat']>=0 else ""
        key = r[c['vid']] if c['vid']>=0 else skun   # 벤더아이템 단위
        it = by_item[key]; it[0]+=g; it[1]+=u; it[3]+=amv; it[4]+=cogs
        if not it[2]:
            it[2] = vdisp
        by_sku[skun][0]+=g; by_sku[skun][1]+=u
        by_cat[catn]+=g
        facts.append((d, vdisp, skun, catn, g, u, rt, o, pv, amv, cogs, cpex))
        sid = cell(r[c['skuid']]) if c['skuid']>=0 else skun
        ms = by_month_sku[(_ym(d), sid)]; ms[0]+=g; ms[1]+=u; ms[3]+=cogs
        if not ms[2]: ms[2]=skun
    tot['aov']  = tot['gmv']/tot['orders'] if tot['orders'] else 0
    tot['asp']  = tot['gmv']/tot['units'] if tot['units'] else 0
    tot['conv'] = tot['orders']/tot['pv']*100 if tot['pv'] else 0
    tot['margin'] = (tot['amv']-tot['cogs'])/tot['amv']*100 if tot['amv'] else 0
    dates = sorted(by_date)
    if not dates:
        return None
    ranking_item=sorted(((v[2], (v[0], v[1])) for v in by_item.values()),
                        key=lambda x:-x[1][0])
    ranking_sku=sorted(by_sku.items(), key=lambda x:-x[1][0])
    margin_item=sorted(   # 상품별 마진: 이름, AMV, COGS, 마진액, 마진율(%)
        ((v[2], v[3], v[4], v[3]-v[4], ((v[3]-v[4])/v[3]*100 if v[3] else 0)) for v in by_item.values()),
        key=lambda x:-x[1])
    return dict(tot=tot,
                daily=[(d, *by_date[d]) for d in dates],
                top=ranking_item[:10], ranking=ranking_item,
                ranking_item=ranking_item, ranking_sku=ranking_sku,
                margin_item=margin_item, facts=facts,
                cats=sorted(by_cat.items(), key=lambda x:-x[1]),
                month_sku={k: v for k, v in by_month_sku.items()},
                period=(fdate(dates[0]), fdate(dates[-1])))

# ---------- 물류 집계 ----------
def analyze_logi(header, data):
    c = dict(
        date=ci(header,"날짜",True), center=ci(header,"센터",True),
        cat=ci(header,"세부카테고리",True), inb=ci(header,"입고수량",True),
        outb=ci(header,"출고수량",True), stock=ci(header,"현재재고수량",True),
        sold=ci(header,"품절여부",True), skuid=ci(header,"SKUID",True),
        name=ci(header,"SKU명",True),
    )
    tot=dict(inb=0.0, outb=0.0)
    dates=[r[c['date']] for r in data if len(r)>c['date']]
    last=max(dates) if dates else None
    stock_last=0.0; total=set()
    by_center=defaultdict(lambda:[0.0,0.0])
    skuagg=defaultdict(lambda:{"name":"","sold":0,"tot":0,"stock":0.0})  # 기준일 SKU별
    cdetail=defaultdict(lambda:defaultdict(lambda:{"stock":0.0,"sold":0}))  # [SKU][센터] 기준일
    mtx_out=defaultdict(lambda:defaultdict(float))  # [SKU명][센터] 출고 합
    mtx_inb=defaultdict(lambda:defaultdict(float))  # [SKU명][센터] 입고 합
    mtx_stk=defaultdict(lambda:defaultdict(float))  # [SKU명][센터] 기준일 재고
    lf_agg=defaultdict(lambda:[0.0,0.0])  # (날짜,SKU명,센터) -> [출고,입고] (기간필터용)
    mx=max(v for v in c.values() if v>=0)
    for r in data:
        if len(r)<=mx:
            continue
        ov=num(r[c['outb']]); iv=num(r[c['inb']])
        tot['inb']+=iv; tot['outb']+=ov
        by_center[r[c['center']]][0]+=iv
        by_center[r[c['center']]][1]+=ov
        nm = r[c['name']] if c['name']>=0 else ""
        cn = r[c['center']]
        mtx_out[nm][cn]+=ov; mtx_inb[nm][cn]+=iv
        la=lf_agg[(r[c['date']], nm, cn)]; la[0]+=ov; la[1]+=iv
        if r[c['date']]==last:
            stock_last+=num(r[c['stock']])
            mtx_stk[nm][cn]+=num(r[c['stock']])
            sid=r[c['skuid']] if c['skuid']>=0 else r[c['cat']]
            total.add(sid)
            a=skuagg[sid]
            a["name"]=(r[c['name']] if c['name']>=0 else sid) or sid
            a["tot"]+=1; a["stock"]+=num(r[c['stock']])
            if r[c['sold']].strip().upper()=="YES":
                a["sold"]+=1
            cd=cdetail[sid][r[c['center']]]; cd["stock"]+=num(r[c['stock']])
            if r[c['sold']].strip().upper()=="YES": cd["sold"]+=1
    # 품절 상품 전체 리스트 (한 센터라도 품절이면 포함), 품절센터 많은 순
    soldout_list=sorted(
        [(v["name"], sid, v["sold"], v["tot"], v["stock"])
         for sid,v in skuagg.items() if v["sold"]>0],
        key=lambda t:(-t[2], -t[4]))
    soldout=len(soldout_list)
    detail_map={}
    for nm,sid,sc,tc,stk in soldout_list:
        centers=cdetail.get(sid,{})
        detail_map[sid]=sorted(
            [(cn, v["stock"], "품절" if v["sold"]>0 else "정상") for cn,v in centers.items()],
            key=lambda t:(0 if t[2]=="품절" else 1, t[1]))
    # 품목 × 센터 매트릭스 (출고/입고/재고), 센터·품목 출고 많은 순
    cen_tot=defaultdict(float)
    for _nm,_cd in mtx_out.items():
        for _cn,_v in _cd.items(): cen_tot[_cn]+=_v
    centers=sorted(cen_tot, key=lambda x:-cen_tot[x])
    skus=[nm for nm,_ in sorted(((nm,sum(cd.values())) for nm,cd in mtx_out.items()), key=lambda x:-x[1])]
    cidx={cn:i for i,cn in enumerate(centers)}
    sidx={nm:i for i,nm in enumerate(skus)}
    LF=[[d, sidx[nm], cidx[cn], o, ib] for (d,nm,cn),(o,ib) in lf_agg.items() if nm in sidx and cn in cidx]
    STK=[[sidx[nm], cidx[cn], v] for nm,cd in mtx_stk.items() for cn,v in cd.items() if nm in sidx and cn in cidx and v]
    matrix=dict(centers=centers, skus=skus, lf=LF, stk=STK)
    return dict(tot=tot, last_date=fdate(last), stock_last=stock_last,
                soldout=soldout, total_skus=len(total),
                soldout_rate=(soldout/len(total)*100 if total else 0),
                by_center=sorted(by_center.items(), key=lambda x:-x[1][1]),
                soldout_list=soldout_list, soldout_detail=detail_map, matrix=matrix)

# ---------- 수익성(매출총이익·목표 대비): 통합데이터만으로 전부 자동 ----------
PLAN_TARGET = 0.28   # 월 목표 이익률(28%). 목표가 바뀌면 이 값만 고치면 전체 반영됨.
# 부가세 처리는 클라이언트(JS) VATDIV()가 담당 — 부가세 %·적용/제외 토글에 따라 실시간 반영.

_PROFIT_SKELETON = r'''
<h2>💰 실적확인 <span class="sub">누적·특정일 · GMV·PPP·UNISOLD·PMC 자동 · PMC=−쿠팡추가할인가 · PPM(PMC)=(PPP+PMC)÷GMV · GAP=PPM−목표 · 상단 부가세 설정 반영</span></h2>
<div class="panel" id="perfWrap"><div class="trendctl">
<label>📅 누적기간 <input type="date" id="perfStart" onchange="renderPerf()"> ~ <input type="date" id="perfEnd" onchange="renderPerf()"></label>
<button class="resetbtn" onclick="perfReset()">전체</button>
<label>🎯 목표 <input type="number" id="perfPlan" value="__PLAN__" min="0" max="100" step="0.5" style="width:66px;padding:5px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px" oninput="renderPerf();renderDayMargin()"> %</label>
<label>📌 특정일 <input type="date" id="perfDay" onchange="renderPerf()"></label>
<span class="sub" id="perfInfo"></span></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="perfHead"></thead><tbody id="perfBody"></tbody></table></div></div>
<h2>📅 상품별 일자별 마진(PPM) <span class="sub">셀=그날 마진율((GMV−COGS+PMC)÷GMV) · 판촉비(PMC)·부가세 반영은 상단 토글 · 계약마진 이상 초록/미만 빨강 · 상위 100품목</span><button class="fullbtn" onclick="openFullDayMargin()">전체보기 ⧉</button></h2>
<div class="panel"><div class="trendctl" style="margin-bottom:8px"><strong style="font-size:12px">📅 이 표 기간</strong><label><input type="date" id="dmStart" onchange="renderDayMargin()"> ~ <input type="date" id="dmEnd" onchange="renderDayMargin()"></label><button class="resetbtn" onclick="dmReset()">전체</button><span class="sub" id="dmInfo"></span></div>
<div class="toggle"><button id="dmDay" class="active" onclick="setDmUnit('day')">일별</button><button id="dmMon" onclick="setDmUnit('month')">월별</button></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="dmHead"></thead><tbody id="dmBody"></tbody></table></div></div>
<script>
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
</script>'''

def _profit_panel_html(s):
    """실적확인(누적·특정일) + 상품별 일자별 마진(PPM) 패널. 계산은 클라이언트(JS·D.F 기반)."""
    if not s.get('month_sku'):
        return ""
    return _PROFIT_SKELETON.replace("__PLAN__", f'{PLAN_TARGET*100:.0f}')

# ---------- 엑셀 생성 ----------
def build_excel(s, l, out_path):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.chart import LineChart, PieChart, BarChart, Reference
    wb=openpyxl.Workbook()
    blue=Font(color="FFFFFF", bold=True); hdr=PatternFill("solid", fgColor="2563EB")
    big=Font(size=20, bold=True, color="2563EB")
    def head(ws,row,n):
        for i in range(1,n+1):
            cc=ws.cell(row=row,column=i); cc.font=blue; cc.fill=hdr
            cc.alignment=Alignment(horizontal="center")

    ws=wb.active; ws.title="핵심지표"
    ws["A1"]="📊 핵심 지표"; ws["A1"].font=Font(size=16,bold=True)
    ws["A2"]=f"기간: {s['period'][0]} ~ {s['period'][1]}"
    kpis=[("결제 금액(GMV)",s['tot']['gmv'],"원"),("판매 수량",s['tot']['units'],"개"),
          ("반품 수량",s['tot']['ret'],"개"),("주문 건수",s['tot']['orders'],"건"),
          ("PV(조회수)",s['tot']['pv'],""),("구매 전환율",s['tot']['conv'],"%"),
          ("객단가(주문당)",s['tot']['aov'],"원"),
          ("마진율",s['tot'].get('margin',0),"%")]
    r=4
    for nm,val,u in kpis:
        ws.cell(r,1,nm).font=Font(bold=True)
        cc=ws.cell(r,2,round(val,2)); cc.font=big
        cc.number_format='#,##0.00' if u=="%" else '#,##0'
        ws.cell(r,3,u); r+=1
    ws.column_dimensions["A"].width=18; ws.column_dimensions["B"].width=18

    ws=wb.create_sheet("일자별추이")
    ws.append(["날짜","GMV","주문건수","판매수량"]); head(ws,1,4)
    for d,g,o,u in s['daily']:
        ws.append([d,round(g),round(o),round(u)])
    for row in ws.iter_rows(min_row=2,min_col=2,max_col=4):
        for cc in row: cc.number_format='#,##0'
    n=len(s['daily']); ch=LineChart(); ch.title="일자별 GMV 추이"; ch.height=8; ch.width=18
    ch.add_data(Reference(ws,min_col=2,min_row=1,max_row=1+n),titles_from_data=True)
    ch.set_categories(Reference(ws,min_col=1,min_row=2,max_row=1+n)); ws.add_chart(ch,"F2")
    ws.column_dimensions["A"].width=12

    for title, rk in [("제품순위(벤더아이템)", s.get('ranking_item', s['ranking'])),
                      ("제품순위(상품별)",   s.get('ranking_sku', []))]:
        ws=wb.create_sheet(title)
        ws.append(["순위","상품명","GMV","판매수량"]); head(ws,1,4)
        for i,(nm,(g,u)) in enumerate(rk,1):   # 전체 표시
            ws.append([i,nm,round(g),round(u)])
        for row in ws.iter_rows(min_row=2,min_col=3,max_col=4):
            for cc in row: cc.number_format='#,##0'
        ws.column_dimensions["B"].width=60; ws.column_dimensions["C"].width=14
        top_n=min(10,len(rk))
        if top_n:
            bc=BarChart(); bc.type="bar"; bc.title="TOP 10 (GMV)"; bc.height=10; bc.width=18
            bc.add_data(Reference(ws,min_col=3,min_row=1,max_row=1+top_n),titles_from_data=True)
            bc.set_categories(Reference(ws,min_col=2,min_row=2,max_row=1+top_n)); ws.add_chart(bc,"F2")

    ws=wb.create_sheet("카테고리")
    ws.append(["세부카테고리","GMV"]); head(ws,1,2)
    for cat,g in s['cats']:
        ws.append([cat,round(g)])
    for row in ws.iter_rows(min_row=2,min_col=2,max_col=2):
        for cc in row: cc.number_format='#,##0'
    ws.column_dimensions["A"].width=22; ws.column_dimensions["B"].width=14
    nc=len(s['cats']); pie=PieChart(); pie.title="카테고리별 GMV 비중"; pie.height=10; pie.width=14
    pie.add_data(Reference(ws,min_col=2,min_row=1,max_row=1+nc),titles_from_data=True)
    pie.set_categories(Reference(ws,min_col=1,min_row=2,max_row=1+nc)); ws.add_chart(pie,"D2")

    # 마진구조 (상품별, 벤더아이템 기준)
    ws=wb.create_sheet("마진구조")
    ws["A1"]="💰 전체 마진"; ws["A1"].font=Font(size=14,bold=True)
    amv_t=s['tot'].get('amv',0); cogs_t=s['tot'].get('cogs',0)
    ws["A2"]=f"조정매출(AMV) {amv_t:,.0f} / 매입원가 {cogs_t:,.0f} / 마진율 {s['tot'].get('margin',0):.1f}%"
    ws.append([]) ; ws.append(["순위","상품명","조정매출(AMV)","매입원가","마진액","마진율(%)"]); head(ws,4,6)
    for i,(nm,amv,cogs,mg,rate) in enumerate(s.get('margin_item',[]),1):
        ws.append([i,nm,round(amv),round(cogs),round(mg),round(rate,1)])
    for row in ws.iter_rows(min_row=5,min_col=3,max_col=5):
        for cc in row: cc.number_format='#,##0'
    ws.column_dimensions["A"].width=6; ws.column_dimensions["B"].width=46
    ws.column_dimensions["C"].width=15; ws.column_dimensions["D"].width=14
    ws.column_dimensions["E"].width=14; ws.column_dimensions["F"].width=10

    if l:
        ws=wb.create_sheet("물류지표")
        ws["A1"]="🚚 물류/재고 지표"; ws["A1"].font=Font(size=16,bold=True)
        ws["A2"]=f"재고 기준일: {l['last_date']}"
        rows=[("총 입고수량",l['tot']['inb'],"개"),("총 출고수량",l['tot']['outb'],"개"),
              ("현재 재고수량",l['stock_last'],"개"),("품절 SKU 수",l['soldout'],f"/ {l['total_skus']}"),
              ("품절율",l['soldout_rate'],"%")]
        r=4
        for nm,val,u in rows:
            ws.cell(r,1,nm).font=Font(bold=True)
            cc=ws.cell(r,2,round(val,2)); cc.font=big
            cc.number_format='#,##0.00' if u=="%" else '#,##0'; ws.cell(r,3,u); r+=1
        r+=1
        for i,t in enumerate(["센터","입고","출고"],1):
            cc=ws.cell(r,i,t); cc.font=blue; cc.fill=hdr
        r+=1
        for center,(ib,ob) in l['by_center']:
            ws.cell(r,1,center); ws.cell(r,2,round(ib)).number_format='#,##0'
            ws.cell(r,3,round(ob)).number_format='#,##0'; r+=1
        ws.column_dimensions["A"].width=18; ws.column_dimensions["B"].width=14
        ws.column_dimensions["C"].width=14

        # 품절상품 탭 (전체 리스트)
        sl=l.get('soldout_list',[])
        ws=wb.create_sheet("품절상품")
        ws.append(["상품명","SKU ID","품절센터수","전체센터수","현재재고"]); head(ws,1,5)
        for nm,sid,sc,tc,stk in sl:
            ws.append([nm,sid,sc,tc,round(stk)])
        for row in ws.iter_rows(min_row=2,min_col=3,max_col=5):
            for cc in row: cc.number_format='#,##0'
        ws.column_dimensions["A"].width=50; ws.column_dimensions["B"].width=14
        ws.column_dimensions["C"].width=11; ws.column_dimensions["D"].width=11
        ws.column_dimensions["E"].width=12
    wb.save(out_path)

# ---------- HTML 생성 ----------
def build_html(s, l, out_path):
    won=lambda x:f"{x:,.0f}"
    profit_html=_profit_panel_html(s)
    _logo=get_logo_b64()
    logo_html=f'<img class="logo" src="data:image/png;base64,{_logo}" alt="logo">' if _logo else ''
    esc=lambda t:str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    _sd=({sid:[[esc(cn), round(stk), st] for cn,stk,st in lst]
          for sid,lst in l['soldout_detail'].items()}
         if l and l.get('soldout_detail') else {})
    isod=lambda d:(f"{str(d)[:4]}-{str(d)[4:6]}-{str(d)[6:8]}" if len(str(d))==8 and str(d).isdigit() else str(d))
    VN={}; SN={}; CN={}
    def gi(dct,k):
        i=dct.get(k)
        if i is None: i=len(dct); dct[k]=i
        return i
    F=[]
    for (dd,vd,sk,cn,g,u,rt,o,pv,amv,cogs,cpex) in s['facts']:
        F.append([isod(dd), gi(VN,vd), gi(SN,sk), gi(CN,cn),
                  round(g), round(u), round(rt), round(o), round(pv), round(amv), round(cogs), round(cpex)])
    def _names(dct):
        arr=[""]*len(dct)
        for k,i in dct.items(): arr[i]=esc(k)
        return arr
    _mtx=None
    if l and l.get('matrix') and l['matrix'].get('lf'):
        mm=l['matrix']
        _mtx=dict(centers=[esc(c) for c in mm['centers']],
                  skus=[esc(c) for c in mm['skus']],
                  lf=[[isod(d), si, ci, round(o), round(ib)] for d,si,ci,o,ib in mm['lf']],
                  stk=[[si, ci, round(v)] for si,ci,v in mm['stk']])
    payload=dict(F=F, VN=_names(VN), SN=_names(SN), CN=_names(CN),
                 period=[isod(s['daily'][0][0]), isod(s['daily'][-1][0])],
                 ld=(l['last_date'] if l else ''), sd=_sd, mtx=_mtx)
    logi=""
    if l:
        lch=('<div class="card sm"><div class="k">총 입고</div><div class="v" id="logiInb">'+won(l['tot']['inb'])+'개</div></div>'
             +'<div class="card sm"><div class="k">총 출고</div><div class="v" id="logiOutb">'+won(l['tot']['outb'])+'개</div></div>'
             +'<div class="card sm"><div class="k">현재 재고</div><div class="v">'+won(l['stock_last'])+'개</div></div>'
             +'<div class="card sm"><div class="k">품절 SKU</div><div class="v">'+str(l['soldout'])+' / '+str(l['total_skus'])+'</div></div>'
             +'<div class="card sm"><div class="k">품절율</div><div class="v">'+f"{l['soldout_rate']:.1f}"+'%</div></div>')
        sl=l.get('soldout_list',[])
        soldout_rows="".join(f'<tr><td><a class="link" onclick="showDetail(&#39;{sid}&#39;,this.textContent)">{esc(nm)}</a></td><td class="num">{sc}/{tc}</td><td class="num">{won(stk)}</td></tr>'
                             for nm,sid,sc,tc,stk in sl)
        if not soldout_rows:
            soldout_rows='<tr><td colspan="3" style="text-align:center;color:#9ca3af">품절 상품 없음</td></tr>'
        mtx_panel = ('''
<div class="panel" style="margin-top:16px"><h2 style="margin-top:0">🗺️ 품목 × 센터 매트릭스 <span class="sub">전체 한눈에 · 출고 많은 순 · 상위 100품목</span><button class="fullbtn" onclick="openFullMatrix()">전체보기 ⧉</button></h2>
<div class="toggle"><button id="mtxO" class="active" onclick="setMtx('o')">출고</button><button id="mtxI" onclick="setMtx('i')">입고</button><button id="mtxS" onclick="setMtx('s')">재고(현재)</button></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="mtxHead"></thead><tbody id="mtxBody"></tbody></table></div></div>
<div class="panel" style="margin-top:16px"><h2 style="margin-top:0">📦 상품 × 일자/월 매트릭스 <span class="sub">상품의 날짜별 출고·입고(전 센터 합산, 물류) / 판매수량(고객 결제 기준, 판매) · 상위 100품목 · 이 표는 아래 자체 기간 사용(상단 기간 무시)</span><button class="fullbtn" onclick="openFullSkuTime()">전체보기 ⧉</button></h2>
<div class="trendctl" style="margin-bottom:10px"><strong style="font-size:12px">📅 이 표 기간</strong><label><input type="date" id="stStart" onchange="renderSkuTime()"> ~ <input type="date" id="stEnd" onchange="renderSkuTime()"></label><button class="resetbtn" onclick="stReset()">전체</button><span class="sub" id="stInfo"></span></div>
<div class="toggle"><button id="stO" class="active" onclick="setSkuTime('o')">출고</button><button id="stI" onclick="setSkuTime('i')">입고</button><button id="stS" onclick="setSkuTime('s')">판매수량</button></div>
<div class="toggle" style="margin-left:8px"><button id="stDay" class="active" onclick="setStUnit('day')">일별</button><button id="stMon" onclick="setStUnit('month')">월별</button></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="stHead"></thead><tbody id="stBody"></tbody></table></div></div>''' if _mtx else '')
        logi=f'''<h2>🚚 물류 / 재고 지표 <span class="sub">기준일: {l["last_date"]}</span></h2>
<div class="cards">{lch}</div>
<div class="grid">
<div class="panel"><h2 style="margin-top:0">🏭 센터별 성장 <span class="sub" id="grInfo"></span><button class="fullbtn" onclick="openFullGrowth()">전체보기 ⧉</button></h2>
<div class="trendctl"><select class="psel" id="grUnit" onchange="onGrowthUnit()"><option value="month">월</option><option value="week">주</option></select><select class="psel" id="grPick" onchange="onGrowthPick()"></select></div>
<div class="scrollbox"><table class="sortable"><thead><tr><th>#</th><th>센터</th><th class="num">이번 기간</th><th class="num">직전 기간</th><th class="num">증감률</th></tr></thead><tbody id="grBody"></tbody></table></div></div>
<div class="panel"><h2 style="margin-top:0">⛔ 품절 상품 <span class="sub">{len(sl)}건 · 품절센터 많은 순</span></h2>
<div class="scrollbox"><table class="sortable"><thead><tr><th>상품명</th><th class="num">품절센터</th><th class="num">재고</th></tr></thead><tbody>{soldout_rows}</tbody></table></div></div>
</div>
{mtx_panel}'''
    gen=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html=f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>판매 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script><style>
*{{box-sizing:border-box}}body{{font-family:'Malgun Gothic','Segoe UI',sans-serif;margin:0;background:#eef2f7;color:#1f2937;word-break:keep-all;overflow-wrap:anywhere}}
.wrap{{max-width:1240px;margin:0 auto;padding:24px}}
.topbar{{display:flex;align-items:center;gap:14px;margin-bottom:2px}}.logo{{height:40px;width:auto}}
h1{{font-size:22px;margin:0;color:#111827}}
.period{{color:#6b7280;font-size:13px;margin-bottom:16px}}
h2{{font-size:15px;margin:26px 0 12px;padding-left:10px;border-left:4px solid #4f46e5;line-height:1.2;color:#111827}}
.sub{{font-weight:400;color:#9ca3af;font-size:12px;border:0;padding:0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:6px}}
.card{{background:#fff;border-radius:14px;padding:14px 16px;box-shadow:0 1px 4px rgba(15,23,42,.07);border-top:3px solid #4f46e5}}
.card .k{{color:#6b7280;font-size:12px;margin-bottom:6px}}.card .v{{font-size:17px;font-weight:700;color:#111827;white-space:nowrap;font-variant-numeric:tabular-nums}}.dlt{{font-size:11px;margin-top:4px;font-weight:600}}
.grid{{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-top:8px}}
.panel{{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 1px 4px rgba(15,23,42,.07)}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px 6px;border-bottom:1px solid #eef0f3;text-align:left}}
th{{color:#6b7280;font-weight:600}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
td.rk{{width:28px;color:#4f46e5;font-weight:700}}.foot{{color:#9ca3af;font-size:12px;margin-top:24px;text-align:center}}
.pager{{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px;justify-content:center;align-items:center}}
.pager button{{min-width:30px;padding:4px 8px;border:1px solid #d1d5db;background:#fff;border-radius:8px;cursor:pointer;font-size:12px}}
.pager button.active{{background:#4f46e5;color:#fff;border-color:#4f46e5}}.pager button:disabled{{opacity:.4;cursor:default}}
.toggle{{display:flex;gap:6px;margin-bottom:10px}}.toggle button{{padding:5px 12px;border:1px solid #d1d5db;background:#fff;border-radius:8px;cursor:pointer;font-size:12px;color:#6b7280}}
.toggle button.active{{background:#4f46e5;color:#fff;border-color:#4f46e5}}
.bar{{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#fff;border-radius:14px;padding:12px 16px;box-shadow:0 2px 10px rgba(15,23,42,.10);margin-bottom:16px;border:1px solid #e7e9f0}}
.fullbtn{{float:right;border:1px solid #d1d5db;background:#fff;color:#4f46e5;border-radius:7px;padding:2px 10px;font-size:11px;cursor:pointer;font-weight:400}}.fullbtn:hover{{background:#eef2ff;border-color:#4f46e5}}
.trendctl{{display:flex;flex-wrap:wrap;gap:12px;align-items:center}}.trendctl label{{font-size:12px;color:#6b7280}}
.trendctl input[type=date]{{padding:5px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px}}.trendctl input[type=date]:hover{{border-color:#4f46e5}}
.resetbtn{{padding:6px 12px;border:1px solid #4f46e5;background:#4f46e5;color:#fff;border-radius:8px;cursor:pointer;font-size:12px}}
.psel{{padding:5px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px;background:#fff;color:#1f2937;cursor:pointer}}.psel:hover{{border-color:#4f46e5}}
th.sorth,table.sortable thead th{{cursor:pointer;user-select:none}}th.sorth:hover,table.sortable thead th:hover{{color:#4f46e5}}
.scrollbox{{max-height:380px;overflow:auto}}.scrollbox table thead th{{position:sticky;top:0;background:#fff}}
.mtxbox{{max-height:460px}}.mtx th,.mtx td{{white-space:nowrap}}.mtx td:first-child,.mtx th:first-child{{position:sticky;left:0;background:#fff;z-index:2;box-shadow:1px 0 0 #eef0f3}}.mtx thead th:first-child{{z-index:3}}.mtx td.z{{color:#cbd5e1}}
.mbw{{background:#eef2f7;border-radius:6px;height:14px;overflow:hidden;min-width:80px}}.mb{{height:100%;background:#4f46e5;border-radius:6px}}
.link{{color:#4f46e5;cursor:pointer;text-decoration:underline}}
.modal{{display:none;position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:50;align-items:center;justify-content:center}}
.modal.open{{display:flex}}.modalbox{{background:#fff;border-radius:14px;max-width:840px;width:92%;max-height:80vh;display:flex;flex-direction:column;padding:18px 20px;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.modalbox table th,.modalbox table td{{white-space:nowrap}}.modalbox .scrollbox{{overflow:auto}}
.modalhead{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}}.modalhead .t{{font-weight:700;font-size:14px}}
.modalhead button{{border:none;background:#eef2ff;color:#4f46e5;border-radius:8px;cursor:pointer;padding:4px 10px}}
@media(max-width:820px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><div class="wrap">
<div class="topbar">{logo_html}<div><h1>📊 쿠팡 통합 대시보드</h1>
<div class="period">데이터 기간: {s['period'][0]} ~ {s['period'][1]}</div></div></div>
<div class="bar"><strong style="font-size:13px">📅 기간 선택</strong>
<label><input type="date" id="dStart" onchange="onRange()"> ~ <input type="date" id="dEnd" onchange="onRange()"></label>
<select class="psel" id="pUnit" onchange="onUnit()"><option value="all">전체 기간</option><option value="year">년</option><option value="month">월</option><option value="week">주</option></select><select class="psel" id="pPick" onchange="onPick()" style="display:none"></select><span class="sub" id="rangeInfo"></span>
<strong style="font-size:13px;margin-left:12px">🧾 부가세</strong><input type="number" id="vatRate" value="10" min="0" max="30" step="1" style="width:52px;padding:5px 6px;border:1px solid #d1d5db;border-radius:8px;font-size:12px" oninput="onVat()"> %<div class="toggle"><button id="vatIncl" onclick="setVat('incl')">적용(포함)</button><button id="vatExcl" class="active" onclick="setVat('excl')">제외</button></div><strong style="font-size:13px;margin-left:8px">🏷️ 판촉비(PMC)</strong><div class="toggle"><button id="pmcOn" onclick="setPmc(true)">반영</button><button id="pmcOff" class="active" onclick="setPmc(false)">미반영</button></div></div>
<div id="kpis" class="cards"></div>
<h2>📈 추이</h2><div class="panel">
<div class="trendctl"><div class="toggle"><button id="g_day" class="active" onclick="setGran('day')">일별</button><button id="g_month" onclick="setGran('month')">월별</button><button id="g_year" onclick="setGran('year')">년별</button></div></div>
<canvas id="lineChart" height="90"></canvas></div>
<h2>💰 상품별 마진 <span class="sub">GMV·판매수량·AMV·PMC 자동 · PPP = GMV − 매입원가 · PPM = (PPP+PMC)÷GMV · 판촉비(PMC)·부가세 반영은 상단 토글로 on/off · 상품별(SKU) 클릭 시 벤더아이템</span></h2>
<div class="panel" style="margin-bottom:16px"><h2 style="margin-top:0">전체</h2><div id="marginKpis" class="cards"></div></div>
<div class="panel"><h2 style="margin-top:0">상품별 마진·순위 <span class="sub" id="marginInfo"></span><button class="fullbtn" onclick="openFullMargin()">전체보기 ⧉</button></h2>
<div class="toggle"><button id="btnMItem" class="active" onclick="setMargMode('item')">벤더아이템별</button><button id="btnMSku" onclick="setMargMode('sku')">상품별(SKU)</button></div>
<div class="scrollbox"><table><thead id="marginHead"><tr><th>#</th><th>상품명</th><th class="num">Revenue(GMV)</th><th class="num">판매수량</th><th class="num">AMV</th><th class="num">PPP</th><th class="num">PMC</th><th class="num">PPM</th></tr></thead><tbody id="marginBody"></tbody></table></div>
<div class="pager" id="marginPager"></div></div>
{profit_html}
{logi}
<div id="modal" class="modal" onclick="if(event.target===this)closeModal()"><div class="modalbox"><div class="modalhead"><span class="t" id="modalTitle"></span><button onclick="closeModal()">✕</button></div><div class="scrollbox"><table class="sortable"><thead id="modalHead"><tr><th>센터</th><th class="num">재고</th><th>상태</th></tr></thead><tbody id="modalBody"></tbody></table></div></div></div>
<div class="foot">생성: {gen} · 판매 대시보드 생성기</div></div>
<script>const D={json.dumps(payload,ensure_ascii=False)};
const won=v=>Math.round(v).toLocaleString('ko-KR');const PER=15;
let gran='day',rmode='item',margMode='item',rpage=1,mpage=1,rankSort={{col:1,dir:-1}},marginSort={{col:1,dir:-1}};
var RANK_COLS=[['상품명',0,''],['GMV',1,'num'],['수량',2,'num']];
var MARGIN_COLS=[['상품명',0,''],['Revenue(GMV)',1,'num'],['판매수량',2,'num'],['AMV',3,'num'],['PPP',4,'num'],['PMC',5,'num'],['PPM',6,'num']];
function sortRows(arr,col,dir){{return arr.sort(function(a,b){{var x=a[col],y=b[col];if(typeof x==='number'&&typeof y==='number')return (x-y)*dir;return String(x).localeCompare(String(y))*dir;}});}}
function headHTML(cols,st,fn){{return '<tr><th>#</th>'+cols.map(function(c){{var ar=st.col===c[1]?(st.dir<0?' ▼':' ▲'):'';return '<th class="'+(c[2]?'num ':'')+'sorth" onclick="'+fn+'('+c[1]+')">'+c[0]+ar+'</th>';}}).join('')+'</tr>';}}
function toggleSort(st,col){{if(st.col===col)st.dir=-st.dir;else{{st.col=col;st.dir=(col===0?1:-1);}}}}
function sortRank(c){{toggleSort(rankSort,c);rpage=1;renderRank();}}
function sortMargin(c){{toggleSort(marginSort,c);mpage=1;renderMargin();}}
document.addEventListener('click',function(ev){{var th=ev.target&&ev.target.closest?ev.target.closest('th'):null;if(!th)return;var tbl=th.closest('table');if(!tbl||tbl.className.indexOf('sortable')<0)return;var hd=th.closest('thead');if(!hd)return;var ths=Array.prototype.slice.call(hd.querySelectorAll('th')),ci=ths.indexOf(th),body=tbl.querySelector('tbody');if(!body||ci<0)return;var rows=Array.prototype.slice.call(body.querySelectorAll('tr'));var dir=th.getAttribute('data-dir')==='1'?-1:1;ths.forEach(function(o){{o.removeAttribute('data-dir');}});th.setAttribute('data-dir',dir===1?'1':'0');rows.sort(function(a,b){{var ax=a.children[ci],bx=b.children[ci];var x=ax?ax.textContent.trim():'',y=bx?bx.textContent.trim():'';var nx=parseFloat(x.replace(/[^0-9.-]/g,'')),ny=parseFloat(y.replace(/[^0-9.-]/g,''));var both=!isNaN(nx)&&!isNaN(ny)&&/[0-9]/.test(x)&&/[0-9]/.test(y);return both?(nx-ny)*dir:x.localeCompare(y)*dir;}});var renum=ths[0]&&ths[0].textContent.trim()==='#';rows.forEach(function(r,i){{if(renum&&r.children[0])r.children[0].textContent=(i+1);body.appendChild(r);}});}});
function rangeVals(){{return [document.getElementById('dStart').value,document.getElementById('dEnd').value];}}
function facts(){{var rv=rangeVals(),s=rv[0],e=rv[1];return D.F.filter(function(x){{var d=x[0];if(s&&d<s)return false;if(e&&d>e)return false;return true;}});}}
function sumKPI(f){{var o={{gmv:0,units:0,ord:0,pv:0,amv:0,cogs:0,cpex:0}};f.forEach(function(r){{o.gmv+=r[4];o.units+=r[5];o.ord+=r[7];o.pv+=r[8];o.amv+=r[9];o.cogs+=r[10];o.cpex+=r[11];}});o.aov=o.ord?o.gmv/o.ord:0;o.conv=o.pv?o.ord/o.pv*100:0;o.margin=o.amv?(o.amv-o.cogs)/o.amv*100:0;return o;}}
function inRangeFacts(s,e){{return D.F.filter(function(r){{var d=r[0];return (!s||d>=s)&&(!e||d<=e);}});}}
function daysBetween(a,b){{var pa=a.split('-'),pb=b.split('-');return Math.round((Date.UTC(+pb[0],+pb[1]-1,+pb[2])-Date.UTC(+pa[0],+pa[1]-1,+pa[2]))/864e5);}}
function deltaBadge(cur,prev,rate){{if(prev==null)return '';var d,sg,co;
if(rate){{d=cur-prev;sg=d>=0?'▲':'▼';co=d>=0?'#10b981':'#ef4444';return '<div class="dlt" style="color:'+co+'">전기간比 '+sg+' '+Math.abs(d).toFixed(1)+'%p</div>';}}
if(!prev)return '<div class="dlt" style="color:#9ca3af">전기간比 —</div>';
d=(cur-prev)/prev*100;sg=d>=0?'▲':'▼';co=d>=0?'#10b981':'#ef4444';return '<div class="dlt" style="color:'+co+'">전기간比 '+sg+' '+Math.abs(d).toFixed(1)+'%</div>';}}
function renderKPIs(){{var cur=sumKPI(facts());var vd=VATDIV();
var rv=rangeVals(),s=rv[0],e=rv[1],P=null;
if(s&&e){{var L=daysBetween(s,e)+1,pe=isoShift(s,-1,0,0),ps=isoShift(pe,-(L-1),0,0);if(pe>=D.period[0])P=sumKPI(inRangeFacts(ps,pe));}}
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
document.getElementById('kpis').innerHTML=cards.map(function(c){{return '<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div>'+(c[2]||'')+'</div>';}}).join('');}}
var lineChartObj=new Chart(document.getElementById('lineChart'),{{type:'line',data:{{labels:[],datasets:[
{{label:'GMV',data:[],borderColor:'#4f46e5',backgroundColor:'rgba(79,70,229,.1)',fill:true,tension:.35,yAxisID:'y'}},
{{label:'주문건수',data:[],borderColor:'#f59e0b',tension:.35,yAxisID:'y1'}},
{{label:'판매수량',data:[],borderColor:'#10b981',tension:.35,yAxisID:'y1'}}]}},
options:{{responsive:true,interaction:{{mode:'index',intersect:false}},scales:{{y:{{position:'left',ticks:{{callback:function(v){{return won(v);}}}}}},y1:{{position:'right',grid:{{drawOnChartArea:false}}}}}}}}}});
function renderTrend(){{var m=new Map();
facts().forEach(function(r){{var iso=r[0];var k=gran==='year'?iso.slice(0,4):gran==='month'?iso.slice(0,7):iso;if(!m.has(k))m.set(k,[0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[7];a[2]+=r[5];}});
var keys=Array.from(m.keys()).sort();lineChartObj.data.labels=keys;
lineChartObj.data.datasets[0].data=keys.map(function(k){{return m.get(k)[0];}});
lineChartObj.data.datasets[1].data=keys.map(function(k){{return m.get(k)[1];}});
lineChartObj.data.datasets[2].data=keys.map(function(k){{return m.get(k)[2];}});
lineChartObj.update();}}
function setGran(g){{gran=g;['day','month','year'].forEach(function(x){{var b=document.getElementById('g_'+x);if(b)b.className=(x===g)?'active':'';}});renderTrend();}}
function pagerEl(el,page,pages,cb){{el.innerHTML='';
function mk(t,p,act,dis){{var b=document.createElement('button');b.textContent=t;if(act)b.className='active';if(dis)b.disabled=true;b.onclick=function(){{cb(p);}};el.appendChild(b);}}
function sp(){{var x=document.createElement('span');x.textContent='…';x.style.padding='0 4px';el.appendChild(x);}}
mk('‹',Math.max(1,page-1),false,page===1);var a=Math.max(1,page-3),e=Math.min(pages,page+3);
if(a>1)mk('1',1,page===1,false);if(a>2)sp();
for(var i=a;i<=e;i++)mk(String(i),i,i===page,false);
if(e<pages-1)sp();if(e<pages)mk(String(pages),pages,page===pages,false);
mk('›',Math.min(pages,page+1),false,page===pages);}}
function rankData(){{var idx=rmode==='sku'?2:1,names=rmode==='sku'?D.SN:D.VN,m=new Map();
facts().forEach(function(r){{var k=r[idx];if(!m.has(k))m.set(k,[0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];}});
return Array.from(m.entries()).map(function(en){{return [names[en[0]],en[1][0],en[1][1],en[0]];}}).sort(function(a,b){{return b[1]-a[1];}});}}
function renderRank(){{var data=sortRows(rankData(),rankSort.col,rankSort.dir),pages=Math.max(1,Math.ceil(data.length/PER));if(rpage>pages)rpage=pages;var st=(rpage-1)*PER;
document.getElementById('rankHead').innerHTML=headHTML(RANK_COLS,rankSort,'sortRank');
document.getElementById('rankBody').innerHTML=data.slice(st,st+PER).map(function(r,i){{var nm=(rmode==='sku')?('<a class="link" onclick="showSkuItems('+r[3]+')">'+r[0]+'</a>'):r[0];return '<tr><td class="rk">'+(st+i+1)+'</td><td>'+nm+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}}).join('');
document.getElementById('rankInfo').textContent='전체 '+data.length+'개 · '+rpage+'/'+pages+' 페이지';
pagerEl(document.getElementById('pager'),rpage,pages,function(p){{rpage=p;renderRank();}});}}
function setMode(m){{rmode=m;rpage=1;var bi=document.getElementById('btnItem'),bs=document.getElementById('btnSku');if(bi)bi.className=(m==='sku')?'':'active';if(bs)bs.className=(m==='sku')?'active':'';renderRank();}}
function setMargMode(m){{margMode=m;mpage=1;var bi=document.getElementById('btnMItem'),bs=document.getElementById('btnMSku');if(bi)bi.className=(m==='sku')?'':'active';if(bs)bs.className=(m==='sku')?'active':'';renderMargin();}}
function openWindow(title,headHtml,bodyHtml){{var w=window.open('','_blank','width=1280,height=820,scrollbars=yes');if(!w){{alert('팝업이 차단되었습니다. 팝업을 허용한 뒤 다시 시도하세요.');return;}}
w.document.write('<!doctype html><html><head><meta charset="utf-8"><title>'+title+'</title><style>html,body{{height:100%}}body{{font-family:\\'Malgun Gothic\\',sans-serif;margin:0;background:#eef2f7;color:#1f2937;word-break:keep-all;display:flex;flex-direction:column}}.hd{{padding:16px 18px 4px;flex:0 0 auto}}h2{{font-size:16px;border-left:4px solid #4f46e5;padding-left:10px;color:#111827;margin:0}}.tip{{color:#9ca3af;font-size:12px;margin:6px 0 0}}.scroller{{flex:1 1 auto;margin:12px 14px;background:#fff;border-radius:14px;box-shadow:0 1px 4px rgba(15,23,42,.07);overflow:auto}}table{{border-collapse:collapse;font-size:13px;width:max-content;min-width:100%}}th,td{{padding:7px 10px;border-bottom:1px solid #eef0f3;text-align:left;white-space:nowrap}}th{{color:#6b7280;position:sticky;top:0;background:#fff;cursor:pointer;user-select:none;z-index:1}}th:hover{{color:#4f46e5}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}td.rk{{color:#4f46e5;font-weight:700;width:46px}}.mbw{{background:#eef2f7;border-radius:6px;height:14px;overflow:hidden;min-width:140px}}.mb{{height:100%;background:#4f46e5;border-radius:6px}}</style></head><body><div class="hd"><h2>'+title+'</h2><div class="tip">컬럼 헤더를 클릭하면 정렬됩니다.</div></div><div class="scroller"><table><thead>'+headHtml+'</thead><tbody>'+bodyHtml+'</tbody></table></div></body></html>');w.document.close();
var tb=w.document.querySelector('table'),ths=tb.querySelectorAll('thead th');
ths.forEach(function(th,ci){{if(ci===0)return;th.onclick=function(){{var body=tb.querySelector('tbody'),rows=Array.prototype.slice.call(body.querySelectorAll('tr')),dir=th.getAttribute('data-dir')==='1'?-1:1;ths.forEach(function(o){{o.removeAttribute('data-dir');}});th.setAttribute('data-dir',dir===1?'1':'0');rows.sort(function(a,b){{var x=a.children[ci].textContent.trim(),y=b.children[ci].textContent.trim(),nx=parseFloat(x.replace(/[^0-9.-]/g,'')),ny=parseFloat(y.replace(/[^0-9.-]/g,'')),both=!isNaN(nx)&&!isNaN(ny)&&/[0-9]/.test(x)&&/[0-9]/.test(y);return both?(nx-ny)*dir:x.localeCompare(y)*dir;}});var renum=ths[0]&&ths[0].textContent.trim()==='#';rows.forEach(function(r,i){{if(renum&&r.children[0])r.children[0].textContent=(i+1);body.appendChild(r);}});}};}});}}
function openFullRank(){{var data=sortRows(rankData(),rankSort.col,rankSort.dir);
var head='<tr><th>#</th><th>상품명</th><th class="num">GMV</th><th class="num">수량</th></tr>';
var body=data.map(function(r,i){{return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}}).join('');
openWindow('🏆 제품 순위 ('+(rmode==='sku'?'상품별':'벤더아이템별')+') — 전체 '+data.length+'개 · '+rangeVals()[0]+'~'+rangeVals()[1],head,body);}}
function openFullMargin(){{var data=sortRows(marginData(),marginSort.col,marginSort.dir);
var head='<tr><th>#</th><th>상품명</th><th class="num">Revenue(GMV)</th><th class="num">판매수량</th><th class="num">AMV</th><th class="num">PPP(판촉비차감전)</th><th class="num">PMC</th><th class="num">PPM</th></tr>';
var body=data.map(function(r,i){{var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}}).join('');
openWindow('💰 상품별 마진·순위 ('+(margMode==='sku'?'상품별':'벤더아이템별')+') — 전체 '+data.length+'개 · '+rangeVals()[0]+'~'+rangeVals()[1],head,body);}}
function renderCat(){{}}
function marginData(){{var idx=margMode==='sku'?2:1,names=margMode==='sku'?D.SN:D.VN,vd=VATDIV(),m=new Map();facts().forEach(function(r){{var k=r[idx];if(!m.has(k))m.set(k,[0,0,0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];a[2]+=r[9];a[3]+=r[10];a[4]+=r[11];}});
return Array.from(m.entries()).map(function(en){{var gmv=en[1][0]/vd,units=en[1][1],amv=en[1][2]/vd,pmc=-en[1][4]/vd,ppp=gmv-VATCOGS(en[1][3]),ppm=gmv?(ppp+(window.__pmcOn?pmc:0))/gmv*100:0;return [names[en[0]],gmv,units,amv,ppp,pmc,ppm,en[0]];}}).sort(function(a,b){{return b[1]-a[1];}});}}
function showSkuMargin(si){{var f=facts().filter(function(r){{return r[2]===si;}}),vd=VATDIV(),m=new Map();
f.forEach(function(r){{var k=r[1];if(!m.has(k))m.set(k,[0,0,0,0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];a[2]+=r[9];a[3]+=r[10];a[4]+=r[11];}});
var rows=Array.from(m.entries()).map(function(en){{var gmv=en[1][0]/vd,units=en[1][1],amv=en[1][2]/vd,pmc=-en[1][4]/vd,ppp=gmv-VATCOGS(en[1][3]),ppm=gmv?(ppp+(window.__pmcOn?pmc:0))/gmv*100:0;return [D.VN[en[0]],gmv,units,amv,ppp,pmc,ppm];}}).sort(function(a,b){{return b[1]-a[1];}});
document.getElementById('modalHead').innerHTML='<tr><th>벤더아이템</th><th class="num">GMV</th><th class="num">판매수량</th><th class="num">AMV</th><th class="num">PPP</th><th class="num">PMC</th><th class="num">PPM</th></tr>';
document.getElementById('modalBody').innerHTML=rows.map(function(r){{var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}}).join('');
document.getElementById('modalTitle').textContent=D.SN[si]+' — 벤더아이템별 마진 ('+rangeVals()[0]+'~'+rangeVals()[1]+')';
document.getElementById('modal').classList.add('open');}}
function renderMargin(){{var gmv=0,units=0,amv=0,cogs=0,cpex=0;facts().forEach(function(r){{gmv+=r[4];units+=r[5];amv+=r[9];cogs+=r[10];cpex+=r[11];}});var vd=VATDIV();var pmc=-cpex/vd,ppp=gmv/vd-VATCOGS(cogs),ppm=(gmv/vd)?(ppp+(window.__pmcOn?pmc:0))/(gmv/vd)*100:0;gmv=gmv/vd;amv=amv/vd;
var cards=[['Revenue(GMV)',won(gmv)+'원'],['판매수량',won(units)+'개'],['조정매출(AMV)',won(amv)+'원'],['PPP(매출총이익)',won(ppp)+'원'],['PMC',won(pmc)+'원'],['PPM',ppm.toFixed(1)+'%']];
document.getElementById('marginKpis').innerHTML=cards.map(function(c){{return '<div class="card sm"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';}}).join('');
var data=sortRows(marginData(),marginSort.col,marginSort.dir),pages=Math.max(1,Math.ceil(data.length/PER));if(mpage>pages)mpage=pages;var st=(mpage-1)*PER;
document.getElementById('marginHead').innerHTML=headHTML(MARGIN_COLS,marginSort,'sortMargin');
document.getElementById('marginBody').innerHTML=data.slice(st,st+PER).map(function(r,i){{var rc=r[6]<0?' style="color:#ef4444;font-weight:600"':'';var nm=(margMode==='sku')?('<a class="link" onclick="showSkuMargin('+r[7]+')">'+r[0]+'</a>'):r[0];return '<tr><td class="rk">'+(st+i+1)+'</td><td>'+nm+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td><td class="num">'+won(r[3])+'</td><td class="num">'+won(r[4])+'</td><td class="num">'+won(r[5])+'</td><td class="num"'+rc+'>'+r[6].toFixed(1)+'%</td></tr>';}}).join('');
document.getElementById('marginInfo').textContent='전체 '+data.length+'개';
pagerEl(document.getElementById('marginPager'),mpage,pages,function(p){{mpage=p;renderMargin();}});}}
function centerTotalsRange(s,e){{if(!D.mtx||!D.mtx.lf)return null;var t=D.mtx.centers.map(function(){{return 0;}});D.mtx.lf.forEach(function(r){{var d=r[0];if((!s||d>=s)&&(!e||d<=e))t[r[2]]+=r[3];}});return t;}}
var grState={{unit:'month',buckets:[],idx:0}};
function growthBuckets(unit){{if(!D.mtx||!D.mtx.lf)return [];var dd={{}};D.mtx.lf.forEach(function(r){{dd[r[0]]=1;}});var ds=Object.keys(dd).sort();if(!ds.length)return [];var lo=ds[0],hi=ds[ds.length-1],seen={{}},keys=[];
if(unit==='month'){{ds.forEach(function(d){{var k=d.slice(0,7);if(!seen[k]){{seen[k]=1;keys.push(k);}}}});keys.sort();return keys.map(function(k,i){{var s=k+'-01',e=isoShift(k+'-01',-1,1,0);if(s<lo)s=lo;if(e>hi)e=hi;var pv=i>0?keys[i-1]:null,ps=pv?pv+'-01':null,pe=pv?isoShift(pv+'-01',-1,1,0):null;if(ps&&ps<lo)ps=lo;if(pe&&pe>hi)pe=hi;return {{label:(+k.slice(0,4))+'년 '+(+k.slice(5,7))+'월',s:s,e:e,ps:ps,pe:pe}};}});}}
ds.forEach(function(d){{var m=mondayOf(d);if(!seen[m]){{seen[m]=1;keys.push(m);}}}});keys.sort();return keys.map(function(m,i){{var s=m,e=isoShift(m,6,0,0);if(s<lo)s=lo;if(e>hi)e=hi;var pv=i>0?keys[i-1]:null,ps=pv,pe=pv?isoShift(pv,6,0,0):null;if(ps&&ps<lo)ps=lo;if(pe&&pe>hi)pe=hi;var wk=isoWeek(m);return {{label:wk[0]+'년 '+wk[1]+'주차 ('+s.slice(5)+'~'+e.slice(5)+')',s:s,e:e,ps:ps,pe:pe}};}});}}
function growthRows(){{if(!D.mtx||!D.mtx.lf)return {{rows:[],prev:false,label:''}};var b=grState.buckets[grState.idx];if(!b)return {{rows:[],prev:false,label:''}};
var cur=centerTotalsRange(b.s,b.e),prev=b.ps?centerTotalsRange(b.ps,b.pe):null;var cs=D.mtx.centers;
var rows=cs.map(function(c,i){{return [c,cur[i],prev?prev[i]:null];}}).filter(function(r){{return r[1]>0||(r[2]&&r[2]>0);}}).sort(function(a,b){{return b[1]-a[1];}});return {{rows:rows,prev:!!prev,label:b.label}};}}
function dcell(cur,prev){{if(prev==null)return '<td class="num" style="color:#9ca3af">—</td>';var d=prev?((cur-prev)/prev*100):(cur>0?100:0),sg=d>=0?'▲':'▼',co=d>=0?'#10b981':'#ef4444';return '<td class="num" style="color:'+co+';font-weight:600">'+sg+' '+Math.abs(d).toFixed(1)+'%</td>';}}
function gbodyHTML(g){{return g.rows.map(function(r,i){{return '<tr><td class="rk">'+(i+1)+'</td><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+(r[2]==null?'—':won(r[2]))+'</td>'+dcell(r[1],r[2])+'</tr>';}}).join('');}}
function renderGrowth(){{var gb=document.getElementById('grBody');if(!gb)return;var g=growthRows();gb.innerHTML=gbodyHTML(g);var gi=document.getElementById('grInfo');if(gi)gi.textContent=(g.label||'')+(g.prev?' · 직전 기간 대비 · 출고 기준':' · 직전 기간 없음 · 출고 기준');}}
function onGrowthUnit(){{grState.unit=document.getElementById('grUnit').value;grState.buckets=growthBuckets(grState.unit);grState.idx=Math.max(0,grState.buckets.length-1);var pick=document.getElementById('grPick');if(pick){{pick.innerHTML=grState.buckets.map(function(b,i){{return '<option value="'+i+'">'+b.label+'</option>';}}).join('');pick.value=String(grState.idx);}}renderGrowth();}}
function onGrowthPick(){{grState.idx=+document.getElementById('grPick').value;renderGrowth();}}
function openFullGrowth(){{var g=growthRows();var head='<tr><th>#</th><th>센터</th><th class="num">이번 기간</th><th class="num">직전 기간</th><th class="num">증감률</th></tr>';
openWindow('🏭 센터별 성장 — '+(g.label||'')+(g.prev?' (직전 기간 대비)':''),head,gbodyHTML(g));}}
function renderAll(){{renderKPIs();renderTrend();renderMargin();renderByCenter();renderMatrix(mtxMetric);renderSkuTime();if(window.renderPerf)renderPerf();if(window.renderDayMargin)renderDayMargin();updateRangeInfo();}}
function onRange(){{rpage=1;mpage=1;renderAll();}}
function setFull(){{document.getElementById('dStart').value=D.period[0];document.getElementById('dEnd').value=D.period[1];onRange();}}
function isoShift(iso,days,months,years){{var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));if(years)dt.setUTCFullYear(dt.getUTCFullYear()+years);if(months)dt.setUTCMonth(dt.getUTCMonth()+months);if(days)dt.setUTCDate(dt.getUTCDate()+days);return dt.toISOString().slice(0,10);}}
function mondayOf(iso){{var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),wd=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-wd);return dt.toISOString().slice(0,10);}}
function isoWeek(iso){{var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),day=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-day+3);var y=dt.getUTCFullYear(),ft=new Date(Date.UTC(y,0,4)),fd=(ft.getUTCDay()+6)%7;ft.setUTCDate(ft.getUTCDate()-fd+3);return [y,1+Math.round((dt-ft)/6048e5)];}}
function uniqueDates(){{var s={{}};D.F.forEach(function(r){{s[r[0]]=1;}});return Object.keys(s).sort();}}
function buckets(unit){{var ds=uniqueDates();if(!ds.length)return [];var lo=ds[0],hi=ds[ds.length-1],seen={{}},out=[];
if(unit==='month'){{ds.forEach(function(d){{var k=d.slice(0,7);if(!seen[k]){{seen[k]=1;var s=k+'-01',e=isoShift(k+'-01',-1,1,0);if(s<lo)s=lo;if(e>hi)e=hi;out.push({{label:(+k.slice(0,4))+'년 '+(+k.slice(5,7))+'월',start:s,end:e}});}}}});}}
else if(unit==='year'){{ds.forEach(function(d){{var k=d.slice(0,4);if(!seen[k]){{seen[k]=1;var s=k+'-01-01',e=k+'-12-31';if(s<lo)s=lo;if(e>hi)e=hi;out.push({{label:k+'년',start:s,end:e}});}}}});}}
else if(unit==='week'){{var keys=[];ds.forEach(function(d){{var m=mondayOf(d);if(!seen[m]){{seen[m]=1;keys.push(m);}}}});keys.sort();keys.forEach(function(m){{var s=m,e=isoShift(m,6,0,0);if(s<lo)s=lo;if(e>hi)e=hi;var wk=isoWeek(m);out.push({{label:wk[0]+'년 '+wk[1]+'주차 ('+s.slice(5)+'~'+e.slice(5)+')',start:s,end:e}});}});}}
return out;}}
var BK=[];
function onUnit(){{var u=document.getElementById('pUnit').value,pick=document.getElementById('pPick');
if(u==='all'){{pick.style.display='none';pick.innerHTML='';setFull();return;}}
pick.style.display='';BK=buckets(u);
pick.innerHTML=BK.map(function(b,i){{return '<option value="'+i+'">'+b.label+'</option>';}}).join('');
pick.value=String(BK.length-1);applyBucket(BK.length-1);}}
function onPick(){{applyBucket(+document.getElementById('pPick').value);}}
function applyBucket(i){{var b=BK[i];if(!b)return;document.getElementById('dStart').value=b.start;document.getElementById('dEnd').value=b.end;rpage=1;mpage=1;renderAll();}}
function updateRangeInfo(){{var rv=rangeVals();document.getElementById('rangeInfo').textContent=rv[0]+' ~ '+rv[1];}}
function showDetail(sid,name){{var rows=(D.sd[sid]||[]);var tb=document.getElementById('modalBody');tb.innerHTML='';
document.getElementById('modalHead').innerHTML='<tr><th>센터</th><th class="num">재고</th><th>상태</th></tr>';
rows.forEach(function(r){{var cls=r[2]==='품절'?' style="color:#ef4444;font-weight:600"':'';tb.insertAdjacentHTML('beforeend','<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td'+cls+'>'+r[2]+'</td></tr>');}});
document.getElementById('modalTitle').textContent=name+' — 센터별 재고 (기준일 '+D.ld+')';
document.getElementById('modal').classList.add('open');}}
function showSkuItems(si){{var f=facts().filter(function(r){{return r[2]===si;}}),m=new Map();
f.forEach(function(r){{var k=r[1];if(!m.has(k))m.set(k,[0,0]);var a=m.get(k);a[0]+=r[4];a[1]+=r[5];}});
var rows=Array.from(m.entries()).map(function(en){{return [D.VN[en[0]],en[1][0],en[1][1]];}}).sort(function(a,b){{return b[1]-a[1];}});
document.getElementById('modalHead').innerHTML='<tr><th>벤더아이템</th><th class="num">GMV</th><th class="num">수량</th></tr>';
document.getElementById('modalBody').innerHTML=rows.map(function(r){{return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'원</td><td class="num">'+won(r[2])+'개</td></tr>';}}).join('');
document.getElementById('modalTitle').textContent=D.SN[si]+' — 벤더아이템별 ('+rangeVals()[0]+'~'+rangeVals()[1]+')';
document.getElementById('modal').classList.add('open');}}
function closeModal(){{document.getElementById('modal').classList.remove('open');}}
var mtxMetric='o',skuMetric='o';
function hcell(v,mx){{if(!v)return '<td class="num z">·</td>';var a=mx>0?Math.min(0.85,v/mx*0.85):0;return '<td class="num" style="background:rgba(79,70,229,'+a.toFixed(3)+');color:'+(a>0.45?'#fff':'#1f2937')+'">'+won(v)+'</td>';}}
function lfAgg(metric){{var cs=D.mtx.centers,nc=cs.length,perc=[],bySku={{}};for(var i=0;i<nc;i++)perc.push(0);
if(metric==='s'){{D.mtx.stk.forEach(function(r){{var si=r[0],ci=r[1],v=r[2];if(!bySku[si]){{bySku[si]=[];for(var j=0;j<nc;j++)bySku[si].push(0);}}bySku[si][ci]+=v;perc[ci]+=v;}});}}
else{{var rv=rangeVals(),s=rv[0],e=rv[1],mi=metric==='i'?4:3;D.mtx.lf.forEach(function(r){{var d=r[0];if((s&&d<s)||(e&&d>e))return;var si=r[1],ci=r[2],v=r[mi];if(!bySku[si]){{bySku[si]=[];for(var j=0;j<nc;j++)bySku[si].push(0);}}bySku[si][ci]+=v;perc[ci]+=v;}});}}
return {{perc:perc,bySku:bySku}};}}
function mtxTop3(perc){{var rk={{}};perc.map(function(t,i){{return [i,t];}}).sort(function(a,b){{return b[1]-a[1];}}).slice(0,3).forEach(function(p,k){{if(p[1]>0)rk[p[0]]=k+1;}});return rk;}}
function mtxHeadHTML(cs,rk){{var med=['🥇','🥈','🥉'];return '<tr><th>상품명</th><th class="num">합계</th>'+cs.map(function(c,ci){{var m=rk[ci]?(med[rk[ci]-1]+' '):'';var st=rk[ci]?' style="background:#eef2ff"':'';return '<th class="num"'+st+'>'+m+c+'</th>';}}).join('')+'</tr>';}}
function mtxRows(ag){{return Object.keys(ag.bySku).map(function(si){{var arr=ag.bySku[si],tot=0;arr.forEach(function(v){{tot+=v;}});return {{name:D.mtx.skus[si],arr:arr,tot:tot}};}}).filter(function(o){{return o.tot>0;}}).sort(function(a,b){{return b.tot-a.tot;}}).slice(0,100);}}
function mtxBodyHTML(rows){{return rows.map(function(o){{var mx=0;o.arr.forEach(function(v){{if(v>mx)mx=v;}});var tds=o.arr.map(function(v){{return hcell(v,mx);}}).join('');return '<tr><td>'+o.name+'</td><td class="num" style="font-weight:700">'+won(o.tot)+'</td>'+tds+'</tr>';}}).join('');}}
function renderMatrix(metric){{if(!D.mtx)return;mtxMetric=metric;var ag=lfAgg(metric);document.getElementById('mtxHead').innerHTML=mtxHeadHTML(D.mtx.centers,mtxTop3(ag.perc));document.getElementById('mtxBody').innerHTML=mtxBodyHTML(mtxRows(ag));}}
function setMtx(m){{['o','i','s'].forEach(function(x){{var b=document.getElementById('mtx'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';}});renderMatrix(m);}}
function openFullMatrix(){{if(!D.mtx)return;var ag=lfAgg(mtxMetric);openWindow('🗺️ 품목 × 센터 매트릭스 — '+({{o:'출고',i:'입고',s:'재고(현재)'}}[mtxMetric])+' · '+rangeVals()[0]+'~'+rangeVals()[1],mtxHeadHTML(D.mtx.centers,mtxTop3(ag.perc)),mtxBodyHTML(mtxRows(ag)));}}
function skuCenters(si,metric){{var cs=D.mtx.centers,arr=[];for(var i=0;i<cs.length;i++)arr.push(0);
if(metric==='s'){{D.mtx.stk.forEach(function(r){{if(r[0]===si)arr[r[1]]+=r[2];}});}}
else{{var rv=rangeVals(),s=rv[0],e=rv[1],mi=metric==='i'?4:3;D.mtx.lf.forEach(function(r){{if(r[1]!==si)return;var d=r[0];if((s&&d<s)||(e&&d>e))return;arr[r[2]]+=r[mi];}});}}
return arr;}}
function skuPairs(si,metric){{var cs=D.mtx.centers,arr=skuCenters(si,metric);return cs.map(function(c,i){{return [c,arr[i]];}}).sort(function(a,b){{return b[1]-a[1];}});}}
function skuRowsHTML(pairs){{var mx=1;pairs.forEach(function(p){{if(p[1]>mx)mx=p[1];}});var tot=pairs.reduce(function(a,p){{return a+p[1];}},0);return pairs.map(function(p,i){{var pct=Math.round(p[1]/mx*100),sh=tot?Math.round(p[1]/tot*100):0;return '<tr><td class="rk">'+(i+1)+'</td><td>'+p[0]+'</td><td class="num">'+won(p[1])+'</td><td><div class="mbw"><div class="mb" style="width:'+pct+'%"></div></div></td><td class="num">'+sh+'%</td></tr>';}}).join('');}}
function renderSku(){{if(!D.mtx)return;var si=+document.getElementById('skuPick').value;document.getElementById('skuBody').innerHTML=skuRowsHTML(skuPairs(si,skuMetric));}}
function setSkuMetric(m){{skuMetric=m;['o','i','s'].forEach(function(x){{var b=document.getElementById('sku'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';}});renderSku();}}
function openFullSku(){{if(!D.mtx)return;var si=+document.getElementById('skuPick').value;var head='<tr><th>#</th><th>센터</th><th class="num">수량</th><th>비중</th><th class="num">점유</th></tr>';openWindow('📦 '+D.mtx.skus[si]+' — 센터별 '+({{o:'출고',i:'입고',s:'재고'}}[skuMetric])+' · '+rangeVals()[0]+'~'+rangeVals()[1],head,skuRowsHTML(skuPairs(si,skuMetric)));}}
function renderByCenter(){{if(!D.mtx)return;var rv=rangeVals(),s=rv[0],e=rv[1],cs=D.mtx.centers,inb=[],outb=[];for(var i=0;i<cs.length;i++){{inb.push(0);outb.push(0);}}
D.mtx.lf.forEach(function(r){{var d=r[0];if((s&&d<s)||(e&&d>e))return;outb[r[2]]+=r[3];inb[r[2]]+=r[4];}});
var rows=cs.map(function(c,i){{return [c,inb[i],outb[i]];}}).sort(function(a,b){{return b[2]-a[2];}});
var tb=document.getElementById('bcBody');if(tb)tb.innerHTML=rows.map(function(r){{return '<tr><td>'+r[0]+'</td><td class="num">'+won(r[1])+'</td><td class="num">'+won(r[2])+'</td></tr>';}}).join('');
var ti=0,to=0;inb.forEach(function(v){{ti+=v;}});outb.forEach(function(v){{to+=v;}});var ei=document.getElementById('logiInb'),eo=document.getElementById('logiOutb');if(ei)ei.textContent=won(ti)+'개';if(eo)eo.textContent=won(to)+'개';}}
var stMetric='o',stUnit='day';
function stRange(){{var s=document.getElementById('stStart'),e=document.getElementById('stEnd');return [s?s.value:'', e?e.value:''];}}
function dateKeys(unit,s,e){{var set={{}};D.mtx.lf.forEach(function(r){{var d=r[0];if((s&&d<s)||(e&&d>e))return;var k=unit==='month'?d.slice(0,7):d;set[k]=1;}});return Object.keys(set).sort();}}
function colLabel(k,unit){{return unit==='month'?((+k.slice(0,4))+'.'+(+k.slice(5,7))):k.slice(5);}}
function timeMtxHead(keys,unit,firstCol){{return '<tr><th>'+firstCol+'</th>'+keys.map(function(k){{return '<th class="num">'+colLabel(k,unit)+'</th>';}}).join('')+'<th class="num">합계</th></tr>';}}
function timeMtxBody(rows){{return rows.map(function(o){{var mx=0;o.arr.forEach(function(v){{if(v>mx)mx=v;}});var tds=o.arr.map(function(v){{return hcell(v,mx);}}).join('');return '<tr><td>'+o.name+'</td>'+tds+'<td class="num" style="font-weight:700">'+won(o.tot)+'</td></tr>';}}).join('');}}
function skuTimeAgg(metric,unit){{var rv=stRange(),s=rv[0],e=rv[1];
var src,ki,vi,names;
if(metric==='s'){{src=D.F;ki=2;vi=5;names=D.SN;}}   // 판매수량: 판매데이터 D.F (r[2]=SKU명, r[5]=판매수량)
else{{if(!D.mtx)return {{keys:[],rows:[]}};src=D.mtx.lf;ki=1;vi=(metric==='i'?4:3);names=D.mtx.skus;}}  // 출고/입고: 물류 lf
var seen={{}};src.forEach(function(r){{var d=r[0];if((s&&d<s)||(e&&d>e))return;seen[unit==='month'?d.slice(0,7):d]=1;}});
var keys=Object.keys(seen).sort(),kidx={{}};keys.forEach(function(k,i){{kidx[k]=i;}});
var bySku={{}};src.forEach(function(r){{var d=r[0];if((s&&d<s)||(e&&d>e))return;var k=unit==='month'?d.slice(0,7):d;var si=r[ki];if(!bySku[si])bySku[si]=keys.map(function(){{return 0;}});bySku[si][kidx[k]]+=r[vi];}});
var rows=Object.keys(bySku).map(function(si){{var arr=bySku[si],tot=0;arr.forEach(function(v){{tot+=v;}});return {{name:names[si],arr:arr,tot:tot}};}}).filter(function(o){{return o.tot>0;}}).sort(function(a,b){{return b.tot-a.tot;}}).slice(0,100);return {{keys:keys,rows:rows}};}}
function renderSkuTime(){{if(!D.mtx)return;var h=document.getElementById('stHead');if(!h)return;var ag=skuTimeAgg(stMetric,stUnit);h.innerHTML=timeMtxHead(ag.keys,stUnit,'상품명');document.getElementById('stBody').innerHTML=timeMtxBody(ag.rows);var rv=stRange(),info=document.getElementById('stInfo');if(info)info.textContent=(rv[0]||'')+' ~ '+(rv[1]||'')+' · '+ag.rows.length+'품목';}}
function stReset(){{var lo=D.period[0],hi=D.period[1];var s=document.getElementById('stStart'),e=document.getElementById('stEnd');if(s)s.value=lo;if(e)e.value=hi;renderSkuTime();}}
function setSkuTime(m){{['o','i','s'].forEach(function(x){{var b=document.getElementById('st'+x.toUpperCase());if(b)b.className=(x===m)?'active':'';}});stMetric=m;renderSkuTime();}}
function setStUnit(u){{['day','month'].forEach(function(x){{var b=document.getElementById('st'+(x==='day'?'Day':'Mon'));if(b)b.className=(x===u)?'active':'';}});stUnit=u;renderSkuTime();}}
function openFullSkuTime(){{var ag=skuTimeAgg(stMetric,stUnit);var rv=stRange();openWindow('📦 상품 × '+(stUnit==='month'?'월':'일자')+' — '+({{o:'출고',i:'입고',s:'판매수량'}}[stMetric])+' · '+(rv[0]||'')+'~'+(rv[1]||''),timeMtxHead(ag.keys,stUnit,'상품명'),timeMtxBody(ag.rows));}}
(function(){{var ds=document.getElementById('dStart'),de=document.getElementById('dEnd');var lo=D.period[0],hi=D.period[1];ds.min=lo;ds.max=hi;ds.value=lo;de.min=lo;de.max=hi;de.value=hi;if(D.mtx){{var sp=document.getElementById('skuPick');if(sp)sp.innerHTML=D.mtx.skus.map(function(n,i){{return '<option value="'+i+'">'+n+'</option>';}}).join('');var ss=document.getElementById('stStart'),se2=document.getElementById('stEnd');if(ss){{ss.min=lo;ss.max=hi;ss.value=lo;}}if(se2){{se2.min=lo;se2.max=hi;se2.value=hi;}}}}renderAll();if(D.mtx&&D.mtx.lf&&document.getElementById('grUnit'))onGrowthUnit();}})();
</script></body></html>'''
    with open(out_path,"w",encoding="utf-8") as f:
        f.write(html)

# ---------- 오케스트레이션 ----------
def generate(file_paths, out_dir):
    sales=None; logi=None; detected=[]
    for p in file_paths:
        header, rows = read_table(p)
        kind = classify(header)
        detected.append((os.path.basename(p), kind))
        if kind=="sales":
            sales=analyze_sales(header, rows)
        elif kind=="logi":
            logi=analyze_logi(header, rows)
    if not sales:
        raise RuntimeError("판매 데이터(일간종합성과지표)를 찾지 못했습니다.\n"
                           "선택한 파일: " + ", ".join(f"{n}({k})" for n,k in detected))
    xlsx=os.path.join(out_dir,"dashboard.xlsx")
    html=os.path.join(out_dir,"dashboard.html")
    build_excel(sales, logi, xlsx)
    build_html(sales, logi, html)
    return html, xlsx, sales, detected

# ===================================================================
#  통합(누적) 엑셀 시스템
# ===================================================================
MASTER_NAME = "통합데이터.xlsx"
SHEET_SALES = "판매"
SHEET_LOGI  = "물류"

def _align_rows(canon_header, up_header, up_rows):
    """업로드 행을 통합 헤더의 컬럼 순서에 맞춰 재배열."""
    if list(up_header) == list(canon_header):
        return up_rows
    pos = {h: i for i, h in enumerate(up_header)}
    idxs = [pos.get(h, -1) for h in canon_header]
    return [[(r[i] if 0 <= i < len(r) else "") for i in idxs] for r in up_rows]

def merge_block(cur_header, cur_rows, up_header, up_rows):
    """날짜 블록 단위 병합. 같은 날짜·같은 내용이면 무시, 다르면 교체. 반환 (header, rows, stats)."""
    from collections import OrderedDict
    if not cur_header:
        cur_header = list(up_header); cur_rows = []
    up2 = _align_rows(cur_header, up_header, up_rows)
    di = ci(cur_header, "날짜", True)
    if di < 0: di = 0
    cur_by = OrderedDict()
    for r in cur_rows:
        cur_by.setdefault(r[di] if di < len(r) else "", []).append(r)
    up_by = OrderedDict()
    for r in up2:
        up_by.setdefault(r[di] if di < len(r) else "", []).append(r)
    added=[]; replaced=[]; skipped=[]
    for d, block in up_by.items():
        old = cur_by.get(d)
        if old is not None and len(old)==len(block) and sorted(map(tuple,old))==sorted(map(tuple,block)):
            skipped.append(d); continue
        cur_by[d] = block
        (replaced if old is not None else added).append(d)
    rows = []
    for d in sorted(cur_by.keys()):
        rows.extend(cur_by[d])
    return cur_header, rows, dict(added=sorted(set(added)), replaced=sorted(set(replaced)), skipped=sorted(set(skipped)))

def _master_paths(folder):
    return (os.path.join(folder, "통합_판매.csv"), os.path.join(folder, "통합_물류.csv"))

def load_master(folder):
    """작업 폴더의 통합 CSV(판매/물류)를 {key:(header,rows)}로 빠르게 읽음."""
    res = {"sales": ([], []), "logi": ([], [])}
    sp, lp = _master_paths(folder)
    for key, p in (("sales", sp), ("logi", lp)):
        if os.path.exists(p):
            try:
                res[key] = read_table(p)
            except Exception:
                pass
    return res

def save_master(folder, sales, logi):
    """판매/물류를 통합 CSV로 빠르게 저장(일일 누적에 적합)."""
    sp, lp = _master_paths(folder)
    for (hdr, rows), p in ((sales, sp), (logi, lp)):
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if hdr:
                w.writerow(list(hdr)); w.writerows(rows)

def save_master_xlsx(path, sales, logi):
    """통합 데이터를 단일 엑셀(2시트: 판매/물류)로 저장 — 마감 보관용."""
    import openpyxl
    wb = openpyxl.Workbook(write_only=True)
    for sheet, (hdr, rows) in ((SHEET_SALES, sales), (SHEET_LOGI, logi)):
        ws = wb.create_sheet(sheet)
        if hdr:
            ws.append(list(hdr))
            for r in rows: ws.append(list(r))
    wb.save(path)

def load_xlsx_master(path):
    """보관된 통합 엑셀(2시트)을 {key:(header,rows)}로 읽음."""
    res = {"sales": ([], []), "logi": ([], [])}
    if not path or not os.path.exists(path):
        return res
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for sheet, key in ((SHEET_SALES, "sales"), (SHEET_LOGI, "logi")):
        if sheet in wb.sheetnames:
            data = [[cell(c) for c in row] for row in wb[sheet].iter_rows(values_only=True)]
            if data:
                res[key] = _norm_table(data[0], data[1:])
    wb.close()
    return res

def master_range(master):
    ds=[]
    for key in ("sales","logi"):
        hdr, rows = master[key]; di = ci(hdr, "날짜", True)
        if di>=0: ds += [r[di] for r in rows if len(r)>di and r[di]]
    return (min(ds), max(ds)) if ds else (None, None)

def merge_files_into_master(master, file_paths):
    """파일들을 분류·파싱해 master(dict)에 병합. 반환 stats."""
    out=dict(sales=None, logi=None, detected=[])
    for p in file_paths:
        hdr, rows = read_table(p)
        kind = classify(hdr)
        out["detected"].append((os.path.basename(p), kind, len(rows)))
        if kind not in ("sales","logi"): continue
        cur_h, cur_r = master[kind]
        nh, nr, st = merge_block(cur_h, cur_r, hdr, rows)
        master[kind] = (nh, nr)
        if out[kind] is None:
            out[kind] = dict(added=[], replaced=[], skipped=[])
        for kk in ('added','replaced','skipped'):
            out[kind][kk] += st[kk]
    return out

def generate_from_master(master, out_dir):
    """통합본으로 대시보드(html/xlsx) 생성."""
    sh, sr = master["sales"]
    if not sr:
        raise RuntimeError("통합 데이터에 판매 데이터가 없습니다. 먼저 파일을 병합하세요.")
    sales = analyze_sales(sh, sr)
    lh, lr = master["logi"]
    logi = analyze_logi(lh, lr) if lr else None
    xlsx=os.path.join(out_dir,"dashboard.xlsx"); html=os.path.join(out_dir,"dashboard.html")
    build_excel(sales, logi, xlsx); build_html(sales, logi, html)
    return html, xlsx, sales

def archive_and_reset(folder, master):
    """현재 통합본을 '통합_시작_끝.xlsx'로 보관하고 작업 통합본(CSV)을 비움. 반환 보관경로."""
    lo, hi = master_range(master)
    name = (f"통합_{lo}_{hi}.xlsx" if lo else "통합_empty.xlsx")
    arch = os.path.join(folder, name)
    save_master_xlsx(arch, master["sales"], master["logi"])
    save_master(folder, ([],[]), ([],[]))   # 작업 통합본(CSV) 비우기
    return arch

# ===================================================================
#  발주 예측 (거래처별·품목별 주문현황 → 품목별 예상 발주량)
# ===================================================================
import re as _re

def _date_iso(v):
    """헤더 셀이 날짜면 'YYYY-MM-DD'로, 아니면 None."""
    s = str(v).strip()
    m = _re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None

def analyze_order_forecast(file_paths):
    """
    '거래처별·품목별 주문현황' 와이드 포맷 파싱.
      - 고정 열: …제품명…거래처명… (좌측)
      - 날짜 열: 우측으로 계속 추가되는 일자별 주문수량
    제품(품목) 단위 일자 매트릭스 + 거래처 단위 상세(드릴다운용)를 만든다.
    여러 파일을 주면 (제품×거래처×날짜) 기준으로 합산 병합한다.
    """
    by_pv = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # 제품 -> 거래처 -> iso -> 수량
    prod_tot = defaultdict(float); vend_tot = defaultdict(float)
    date_set = set()
    detected = []
    for path in file_paths:
        header, rows = read_table(path)
        pi = ci(header, "제품명", True)
        if pi < 0: pi = ci(header, "품목명", True)
        if pi < 0: pi = ci(header, "제품명")
        if pi < 0: pi = ci(header, "품목명")
        vi = ci(header, "거래처명", True)
        if vi < 0: vi = ci(header, "거래처명")
        if vi < 0: vi = ci(header, "거래명")
        dcols = [(i, iso) for i, h in enumerate(header)
                 if (iso := _date_iso(h)) is not None]
        if pi < 0 or not dcols:
            detected.append((os.path.basename(path), "skip", 0)); continue
        date_set.update(iso for _, iso in dcols)
        cnt = 0
        for r in rows:
            if pi >= len(r):
                continue
            pn = str(r[pi]).strip()
            if not pn:
                continue
            vn = (str(r[vi]).strip() if 0 <= vi < len(r) and r[vi] is not None else "")
            if not vn: vn = "(미지정)"
            cnt += 1
            dv = by_pv[pn][vn]
            for i, iso in dcols:
                if i < len(r):
                    v = num(r[i])
                    if v:
                        dv[iso] += v; prod_tot[pn] += v; vend_tot[vn] += v
        detected.append((os.path.basename(path), "order", cnt))
    if not by_pv or not date_set:
        raise RuntimeError(
            "주문현황 데이터(제품명 + 날짜 열)를 찾지 못했습니다.\n"
            "선택한 파일: " + ", ".join(f"{n}({k})" for n, k, _ in detected))
    dates = sorted(date_set)
    prods = sorted(by_pv.keys(), key=lambda p: -prod_tot[p])
    vends = sorted(vend_tot.keys(), key=lambda v: -vend_tot[v])
    pidx = {p: i for i, p in enumerate(prods)}
    vidx = {v: i for i, v in enumerate(vends)}
    didx = {d: i for i, d in enumerate(dates)}
    matf = [[0.0] * len(dates) for _ in prods]
    vf = []                                   # 희소 사실: [제품i, 거래처i, 날짜i, 수량]
    for pn, vmap in by_pv.items():
        p = pidx[pn]
        for vn, dmap in vmap.items():
            v = vidx[vn]
            for iso, q in dmap.items():
                di = didx[iso]; matf[p][di] += q
                qr = round(q)
                if qr:
                    vf.append([p, v, di, qr])
    mat = [[round(x) for x in r] for r in matf]
    wd = [datetime.date(int(d[:4]), int(d[5:7]), int(d[8:10])).weekday() for d in dates]
    comp = [sum(mat[p][j] for p in range(len(prods))) for j in range(len(dates))]
    return dict(prods=prods, vends=vends, dates=dates, wd=wd,
                mat=mat, comp=comp, vf=vf, detected=detected)

def _forecast_ctx(parsed):
    """예측 계산에 필요한 상수 묶음(파이썬·자바스크립트 동일 공식)."""
    dates = parsed['dates']; comp = parsed['comp']; wd = parsed['wd']
    business = [i for i, c in enumerate(comp) if c > 0]
    weeks = (len(dates) / 7) or 1
    nBW = len({wd[i] for i in business}) or 1
    return dict(dates=dates, wd=wd, business=business, nBD=len(business),
                bdPerWeek=len(business) / weeks, nBW=nBW, lastIdx=len(dates) - 1)

def _forecast_one(row, ctx, method):
    """단일 시계열(row)에 대한 (일간, 주간, 월간) 예상 발주량."""
    import math
    if method == 'bday':
        s = sum(row[i] for i in ctx['business'])
        daily = s / ctx['nBD'] if ctx['nBD'] else 0
        weekly = daily * ctx['bdPerWeek']
        span = len(ctx['dates'])
        monthly = daily * (ctx['nBD'] / span if span else 0) * 30.44
    else:
        sumW = [0.0] * 7; wgt = [0.0] * 7
        for i, v in enumerate(row):
            w = math.exp(-(ctx['lastIdx'] - i) / 14) if method == 'recent' else 1.0
            sumW[ctx['wd'][i]] += v * w; wgt[ctx['wd'][i]] += w
        avgW = [(sumW[k] / wgt[k] if wgt[k] else 0) for k in range(7)]
        weekly = sum(avgW); daily = weekly / ctx['nBW']; monthly = weekly * 30.44 / 7
    return daily, weekly, monthly

def build_forecast_html(parsed, out_path):
    """예상 발주량 대시보드(HTML). 방식·기간 전환은 클라이언트(JS)에서 즉시 처리."""
    _logo = get_logo_b64()
    logo_html = (f'<img class="logo" src="data:image/png;base64,{_logo}" alt="logo">'
                 if _logo else '')
    payload = dict(prods=parsed['prods'], vends=parsed['vends'], dates=parsed['dates'],
                   wd=parsed['wd'], mat=parsed['mat'], comp=parsed['comp'], vf=parsed['vf'])
    gen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = (FORECAST_TPL
            .replace("__LOGO__", logo_html)
            .replace("__GEN__", gen)
            .replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False)))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

def build_forecast_excel(parsed, out_path):
    """예측 결과 엑셀: 방식별 시트(요일별/영업일/최근가중) + 요일 패턴."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.chart import BarChart, Reference
    dates = parsed['dates']; wd = parsed['wd']; comp = parsed['comp']
    prods = parsed['prods']; mat = parsed['mat']
    ctx = _forecast_ctx(parsed)
    blue = Font(color="FFFFFF", bold=True); hdr = PatternFill("solid", fgColor="4F46E5")
    wb = openpyxl.Workbook(); first = True
    for label, m in (("요일별평균", "wday"), ("영업일평균", "bday"), ("최근가중", "recent")):
        ws = wb.active if first else wb.create_sheet(); first = False
        ws.title = f"예상발주_{label}"
        ws["A1"] = f"📦 제품별 예상 발주량 — {label}"; ws["A1"].font = Font(size=14, bold=True)
        ws["A2"] = f"분석기간 {dates[0]} ~ {dates[-1]} ({len(dates)}일 · 영업일 {ctx['nBD']}일)"
        ws.append([]); ws.append(["순위", "제품명", "일간", "주간", "월간"])
        for c in range(1, 6):
            cc = ws.cell(4, c); cc.font = blue; cc.fill = hdr; cc.alignment = Alignment(horizontal="center")
        rows = []
        for p, row in enumerate(mat):
            d, w, mo = _forecast_one(row, ctx, m)
            rows.append((prods[p], d, w, mo))
        rows.sort(key=lambda r: -r[2])
        for i, (nm, d, w, mo) in enumerate(rows, 1):
            ws.append([i, nm, round(d), round(w), round(mo)])
        for r in ws.iter_rows(min_row=5, min_col=3, max_col=5):
            for cc in r: cc.number_format = '#,##0'
        ws.column_dimensions["B"].width = 44
        for col in ("C", "D", "E"): ws.column_dimensions[col].width = 12
        n = min(15, len(rows))
        if n:
            bc = BarChart(); bc.type = "bar"; bc.title = f"TOP {n} (주간)"; bc.height = 11; bc.width = 18
            bc.add_data(Reference(ws, min_col=4, min_row=4, max_row=4 + n), titles_from_data=True)
            bc.set_categories(Reference(ws, min_col=2, min_row=5, max_row=4 + n)); ws.add_chart(bc, "G4")
    ws = wb.create_sheet("요일별패턴")
    ws.append(["요일", "평균 발주(개)"])
    for c in range(1, 3):
        cc = ws.cell(1, c); cc.font = blue; cc.fill = hdr
    WD_KO = ['월', '화', '수', '목', '금', '토', '일']
    s = [0.0] * 7; c2 = [0] * 7
    for i in range(len(dates)): s[wd[i]] += comp[i]; c2[wd[i]] += 1
    for k in range(7):
        ws.append([WD_KO[k], round(s[k] / c2[k]) if c2[k] else 0])
    ws.column_dimensions["A"].width = 8; ws.column_dimensions["B"].width = 14
    wb.save(out_path)

def generate_forecast(file_paths, out_dir):
    parsed = analyze_order_forecast(file_paths)
    html = os.path.join(out_dir, "발주예측.html")
    xlsx = os.path.join(out_dir, "발주예측.xlsx")
    build_forecast_html(parsed, html)
    build_forecast_excel(parsed, xlsx)
    return html, xlsx, parsed

# ---- 발주 예측 HTML 템플릿 (브레이스 충돌 방지 위해 .replace 방식) ----
FORECAST_TPL = r'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>발주 예측</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script><style>
*{box-sizing:border-box}body{font-family:'Malgun Gothic','Segoe UI',sans-serif;margin:0;background:#eef2f7;color:#1f2937;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:1240px;margin:0 auto;padding:24px}
.topbar{display:flex;align-items:center;gap:14px;margin-bottom:2px}.logo{height:40px;width:auto}
h1{font-size:22px;margin:0;color:#111827}
.period{color:#6b7280;font-size:13px;margin-bottom:16px}
h2{font-size:15px;margin:26px 0 12px;padding-left:10px;border-left:4px solid #4f46e5;line-height:1.2;color:#111827}
.sub{font-weight:400;color:#9ca3af;font-size:12px;border:0;padding:0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:6px}
.card{background:#fff;border-radius:14px;padding:14px 16px;box-shadow:0 1px 4px rgba(15,23,42,.07);border-top:3px solid #4f46e5}
.card .k{color:#6b7280;font-size:12px;margin-bottom:6px}.card .v{font-size:20px;font-weight:700;color:#111827}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px}
.panel{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 1px 4px rgba(15,23,42,.07)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px 6px;border-bottom:1px solid #eef0f3;text-align:left}
th{color:#6b7280;font-weight:600}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.rk{width:28px;color:#4f46e5;font-weight:700}.foot{color:#9ca3af;font-size:12px;margin-top:24px;text-align:center}
td.hl,th.hl{background:#eef2ff}
.pager{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px;justify-content:center;align-items:center}
.pager button{min-width:30px;padding:4px 8px;border:1px solid #d1d5db;background:#fff;border-radius:8px;cursor:pointer;font-size:12px}
.pager button.active{background:#4f46e5;color:#fff;border-color:#4f46e5}.pager button:disabled{opacity:.4;cursor:default}
.toggle{display:inline-flex;gap:6px}.toggle button{padding:5px 12px;border:1px solid #d1d5db;background:#fff;border-radius:8px;cursor:pointer;font-size:12px;color:#6b7280}
.toggle button.active{background:#4f46e5;color:#fff;border-color:#4f46e5}
.bar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#fff;border-radius:14px;padding:12px 16px;box-shadow:0 2px 10px rgba(15,23,42,.10);margin-bottom:12px;border:1px solid #e7e9f0}
.bar label{font-size:12px;color:#6b7280}
.bar input[type=date]{padding:5px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px}.bar input[type=date]:hover{border-color:#4f46e5}
.psel{padding:5px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:12px;background:#fff;color:#1f2937;cursor:pointer}.psel:hover{border-color:#4f46e5}
.resetbtn{padding:6px 12px;border:1px solid #4f46e5;background:#4f46e5;color:#fff;border-radius:8px;cursor:pointer;font-size:12px}
.fullbtn{float:right;border:1px solid #d1d5db;background:#fff;color:#4f46e5;border-radius:7px;padding:2px 10px;font-size:11px;cursor:pointer;font-weight:400}.fullbtn:hover{background:#eef2ff;border-color:#4f46e5}
th.sorth,table.sortable thead th{cursor:pointer;user-select:none}table.sortable thead th:hover{color:#4f46e5}
.scrollbox{max-height:460px;overflow:auto}.scrollbox table thead th{position:sticky;top:0;background:#fff;z-index:1}
.link{color:#4f46e5;cursor:pointer;text-decoration:underline}
.modal{display:none;position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:50;align-items:center;justify-content:center}
.modal.open{display:flex}.modalbox{background:#fff;border-radius:14px;max-width:620px;width:90%;max-height:80vh;display:flex;flex-direction:column;padding:18px 20px;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.modalhead{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}.modalhead .t{font-weight:700;font-size:14px}
.modalhead button{border:none;background:#eef2ff;color:#4f46e5;border-radius:8px;cursor:pointer;padding:4px 10px}
@media(max-width:820px){.grid{grid-template-columns:1fr}}</style></head><body><div class="wrap">
<div class="topbar">__LOGO__<div><h1>📦 푸르밀 발주 예측</h1>
<div class="period" id="periodInfo"></div></div></div>
<div class="bar"><strong style="font-size:13px">📅 분석 기간</strong>
<label><input type="date" id="dStart" onchange="onRange()"> ~ <input type="date" id="dEnd" onchange="onRange()"></label>
<select class="psel" id="pUnit" onchange="onUnit()"><option value="all">전체 기간</option><option value="year">년</option><option value="month">월</option><option value="week">주</option></select>
<select class="psel" id="pPick" onchange="onPick()" style="display:none"></select>
<button class="resetbtn" onclick="resetRange()">전체</button><span class="sub" id="rangeInfo"></span></div>
<div class="bar"><strong style="font-size:13px">🔮 예측 방식</strong>
<div class="toggle"><button id="m_wday" class="active" onclick="setMethod('wday')">요일별 평균</button><button id="m_bday" onclick="setMethod('bday')">영업일 평균</button><button id="m_recent" onclick="setMethod('recent')">최근 가중</button></div>
<strong style="font-size:13px;margin-left:10px">🎯 예측 단위</strong>
<div class="toggle"><button id="p_daily" onclick="setPeriod('daily')">일간</button><button id="p_weekly" class="active" onclick="setPeriod('weekly')">주간</button><button id="p_monthly" onclick="setPeriod('monthly')">월간</button></div>
<span class="sub" id="methodInfo"></span></div>
<div id="kpis" class="cards"></div>
<div class="grid">
<div class="panel"><h2 style="margin-top:0">📊 제품별 예상 발주량 TOP 15 <span class="sub" id="chartInfo"></span></h2><canvas id="barChart" height="150"></canvas></div>
<div class="panel"><h2 style="margin-top:0">📅 요일별 발주 패턴 <span class="sub">전체 합계 · 요일 평균(개)</span></h2><canvas id="wdChart" height="150"></canvas></div>
</div>
<div class="panel" style="margin-top:16px"><h2 style="margin-top:0">📋 제품별 예상 발주량 <span class="sub" id="tableInfo"></span><button class="fullbtn" onclick="openFull()">전체보기 ⧉</button></h2>
<div class="scrollbox"><table class="sortable"><thead id="tHead"></thead><tbody id="tBody"></tbody></table></div>
<div class="pager" id="pager"></div></div>
<div id="modal" class="modal" onclick="if(event.target===this)closeModal()"><div class="modalbox"><div class="modalhead"><span class="t" id="modalTitle"></span><button onclick="closeModal()">✕</button></div><div class="scrollbox"><table class="sortable"><thead><tr><th>거래처</th><th class="num">일간</th><th class="num">주간</th><th class="num">월간</th></tr></thead><tbody id="modalBody"></tbody></table></div></div></div>
<div class="foot">생성: __GEN__ · 발주 예측 생성기 · 제품명을 클릭하면 거래처별 분해 · 예측은 과거 주문 패턴 기반 추정치입니다</div></div>
<script>
const FD=__PAYLOAD__;
const won=v=>Math.round(v).toLocaleString('ko-KR');
const WD_KO=['월','화','수','목','금','토','일'];
const WPM=30.44/7;                         // 월 평균 주(週) 수
// 선택한 '분석 기간'에 따라 다시 계산되는 파생값들 (통합 대시보드의 기간선택과 동일 동작)
let actIdx=[], businessIdx=[], spanDays=0, weeks=1, nBD=0, bdPerWeek=0, nBW=1, lastIdx=0;
function rangeVals(){return [document.getElementById('dStart').value, document.getElementById('dEnd').value];}
function recompute(){
  const rv=rangeVals(), s=rv[0], e=rv[1];
  actIdx=[]; for(let i=0;i<FD.dates.length;i++){ const d=FD.dates[i]; if((!s||d>=s)&&(!e||d<=e)) actIdx.push(i); }
  spanDays=actIdx.length; weeks=spanDays/7||1;
  businessIdx=actIdx.filter(function(i){return FD.comp[i]>0;});
  nBD=businessIdx.length; bdPerWeek=nBD/weeks;
  const wdA=new Array(7).fill(0); businessIdx.forEach(function(i){wdA[FD.wd[i]]=1;});
  nBW=wdA.reduce(function(a,b){return a+b;},0)||1;
  lastIdx=actIdx.length? actIdx[actIdx.length-1]:(FD.dates.length-1);
}
let method='wday', period='weekly', page=1, sortKey='weekly', sortDir=-1;
const PER=15;
const PLABEL={daily:'일간(영업일 1일)',weekly:'주간',monthly:'월간'};
const MLABEL={wday:'요일별 평균 — 같은 요일끼리 평균내 주말·요일 편차 반영',
              bday:'영업일 평균 — 주문이 있는 날(영업일)만 평균',
              recent:'최근 가중 — 최근 2주에 가중치(반감기 14일)·요일 패턴 반영'};

function forecastRow(row){
  let daily=0,weekly=0,monthly=0;
  if(method==='bday'){
    let s=0; for(const i of businessIdx) s+=row[i];
    daily=nBD? s/nBD:0; weekly=daily*bdPerWeek; monthly=daily*(spanDays? nBD/spanDays:0)*30.44;
  } else {
    const sumW=new Array(7).fill(0), wgt=new Array(7).fill(0);
    for(const i of actIdx){
      let w=1; if(method==='recent') w=Math.exp(-(lastIdx-i)/14);
      sumW[FD.wd[i]]+=row[i]*w; wgt[FD.wd[i]]+=w;
    }
    const avgW=sumW.map((s,w)=> wgt[w]? s/wgt[w]:0);
    weekly=avgW.reduce((a,b)=>a+b,0); daily=weekly/nBW; monthly=weekly*WPM;
  }
  return {daily:daily, weekly:weekly, monthly:monthly};
}
function forecastAll(){
  const out=[];
  for(let p=0;p<FD.prods.length;p++){
    const fc=forecastRow(FD.mat[p]);
    out.push({name:FD.prods[p], idx:p, daily:fc.daily, weekly:fc.weekly, monthly:fc.monthly});
  }
  return out;
}
function vendorForecast(p){
  const byV={};
  for(let k=0;k<FD.vf.length;k++){ const f=FD.vf[k]; if(f[0]!==p) continue;
    if(!byV[f[1]]) byV[f[1]]=new Array(FD.dates.length).fill(0); byV[f[1]][f[2]]+=f[3]; }
  const res=[];
  for(const v in byV){ const fc=forecastRow(byV[v]); res.push({name:FD.vends[v], daily:fc.daily, weekly:fc.weekly, monthly:fc.monthly}); }
  return res;
}
function showVendors(p){
  const rows=vendorForecast(p).sort(function(a,b){return b[period]-a[period];});
  const body=rows.map(function(o){return '<tr><td>'+o.name+'</td><td class="num">'+won(o.daily)+'</td><td class="num">'+won(o.weekly)+'</td><td class="num">'+won(o.monthly)+'</td></tr>';}).join('')
    || '<tr><td colspan="4" style="text-align:center;color:#9ca3af">거래처 데이터 없음</td></tr>';
  document.getElementById('modalTitle').textContent=FD.prods[p]+' — 거래처별 예상 발주량 ('+PLABEL[period]+' 정렬)';
  document.getElementById('modalBody').innerHTML=body;
  document.getElementById('modal').classList.add('open');
}
function closeModal(){document.getElementById('modal').classList.remove('open');}
function sortData(d){
  const k=sortKey;
  return d.sort(function(a,b){
    if(k==='name') return String(a.name).localeCompare(String(b.name))*sortDir;
    return (a[k]-b[k])*sortDir;
  });
}
const COLS=[['제품명','name',''],['일간','daily','num'],['주간','weekly','num'],['월간','monthly','num']];
function headHTML(){
  return '<tr><th>#</th>'+COLS.map(function(c){
    const hl=(c[1]===period && c[1]!=='name')?' hl':'';
    const ar=sortKey===c[1]?(sortDir<0?' ▼':' ▲'):'';
    return '<th class="'+(c[2]?'num ':'')+'sorth'+hl+'" onclick="clickSort(\''+c[1]+'\')">'+c[0]+ar+'</th>';
  }).join('')+'</tr>';
}
function rowHTML(o,rank){
  const cell=function(key){ const hl=(key===period)?' hl':''; return '<td class="num'+hl+'">'+won(o[key])+'</td>'; };
  const nm='<a class="link" onclick="showVendors('+o.idx+')">'+o.name+'</a>';
  return '<tr><td class="rk">'+rank+'</td><td>'+nm+'</td>'+cell('daily')+cell('weekly')+cell('monthly')+'</tr>';
}
function clickSort(k){ if(sortKey===k) sortDir=-sortDir; else { sortKey=k; sortDir=(k==='name'?1:-1);} page=1; renderTable(); }
function renderTable(){
  const data=sortData(forecastAll());
  const pages=Math.max(1,Math.ceil(data.length/PER)); if(page>pages) page=pages;
  const st=(page-1)*PER;
  document.getElementById('tHead').innerHTML=headHTML();
  document.getElementById('tBody').innerHTML=data.slice(st,st+PER).map(function(o,i){return rowHTML(o,st+i+1);}).join('');
  document.getElementById('tableInfo').textContent='전체 '+data.length+'개 · '+PLABEL[period]+' 기준 정렬';
  pagerEl(document.getElementById('pager'),page,pages,function(p){page=p;renderTable();});
}
function pagerEl(el,pg,pages,cb){el.innerHTML='';
  function mk(t,p,act,dis){var b=document.createElement('button');b.textContent=t;if(act)b.className='active';if(dis)b.disabled=true;b.onclick=function(){cb(p);};el.appendChild(b);}
  function sp(){var x=document.createElement('span');x.textContent='…';x.style.padding='0 4px';el.appendChild(x);}
  mk('‹',Math.max(1,pg-1),false,pg===1);var a=Math.max(1,pg-3),e=Math.min(pages,pg+3);
  if(a>1)mk('1',1,pg===1,false);if(a>2)sp();
  for(var i=a;i<=e;i++)mk(String(i),i,i===pg,false);
  if(e<pages-1)sp();if(e<pages)mk(String(pages),pages,pg===pages,false);
  mk('›',Math.min(pages,pg+1),false,pg===pages);}
var barObj=new Chart(document.getElementById('barChart'),{type:'bar',data:{labels:[],datasets:[{label:'예상 발주량',data:[],backgroundColor:'#4f46e5',borderRadius:4}]},
  options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},scales:{x:{ticks:{callback:function(v){return won(v);}}}}}});
function renderBar(){
  const data=forecastAll().slice().sort(function(a,b){return b[period]-a[period];}).slice(0,15);
  barObj.data.labels=data.map(function(o){return o.name.length>22? o.name.slice(0,22)+'…':o.name;});
  barObj.data.datasets[0].data=data.map(function(o){return Math.round(o[period]);});
  barObj.update();
  document.getElementById('chartInfo').textContent='· '+PLABEL[period]+' 기준';
}
var wdObj=new Chart(document.getElementById('wdChart'),{type:'bar',data:{labels:WD_KO,datasets:[{label:'요일 평균',data:[],backgroundColor:['#4f46e5','#4f46e5','#4f46e5','#4f46e5','#4f46e5','#cbd5e1','#cbd5e1'],borderRadius:4}]},
  options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{ticks:{callback:function(v){return won(v);}}}}}});
function renderWd(){
  const sum=new Array(7).fill(0), cnt=new Array(7).fill(0);
  for(const i of actIdx){ sum[FD.wd[i]]+=FD.comp[i]; cnt[FD.wd[i]]++; }
  wdObj.data.datasets[0].data=sum.map(function(s,w){return cnt[w]? Math.round(s/cnt[w]):0;});
  wdObj.update();
}
function renderKPIs(){
  const data=forecastAll(); let tot=0; data.forEach(function(o){tot+=o[period];});
  const rv=rangeVals();
  const cards=[
    ['총 예상 발주량('+PLABEL[period]+')',won(tot)+'개'],
    ['분석 제품 수',won(FD.prods.length)+'종'],
    ['영업일 수',won(nBD)+'일 / '+spanDays+'일'],
    ['분석 기간',(rv[0]||FD.dates[0])+' ~ '+(rv[1]||FD.dates[FD.dates.length-1])]];
  document.getElementById('kpis').innerHTML=cards.map(function(c){return '<div class="card"><div class="k">'+c[0]+'</div><div class="v" style="font-size:'+(c[0]==='분석 기간'?'14px':'20px')+'">'+c[1]+'</div></div>';}).join('');
}
function renderAll(){renderWd();renderKPIs();renderBar();renderTable();}
function setMethod(m){method=m;['wday','bday','recent'].forEach(function(x){var b=document.getElementById('m_'+x);if(b)b.className=(x===m)?'active':'';});document.getElementById('methodInfo').textContent='· '+MLABEL[m];page=1;renderAll();}
function setPeriod(p){period=p;sortKey=p;sortDir=-1;['daily','weekly','monthly'].forEach(function(x){var b=document.getElementById('p_'+x);if(b)b.className=(x===p)?'active':'';});page=1;renderAll();}
// ----- 분석 기간(날짜) 선택: 통합 대시보드와 동일한 동작 -----
function isoShift(iso,days,months,years){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));if(years)dt.setUTCFullYear(dt.getUTCFullYear()+years);if(months)dt.setUTCMonth(dt.getUTCMonth()+months);if(days)dt.setUTCDate(dt.getUTCDate()+days);return dt.toISOString().slice(0,10);}
function mondayOf(iso){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),wd=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-wd);return dt.toISOString().slice(0,10);}
function isoWeek(iso){var p=iso.split('-'),dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])),day=(dt.getUTCDay()+6)%7;dt.setUTCDate(dt.getUTCDate()-day+3);var y=dt.getUTCFullYear(),ft=new Date(Date.UTC(y,0,4)),fd=(ft.getUTCDay()+6)%7;ft.setUTCDate(ft.getUTCDate()-fd+3);return [y,1+Math.round((dt-ft)/6048e5)];}
function uniqueDates(){return FD.dates.slice();}
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
function applyBucket(i){var b=BK[i];if(!b)return;document.getElementById('dStart').value=b.start;document.getElementById('dEnd').value=b.end;onRange();}
function setFull(){document.getElementById('dStart').value=FD.dates[0];document.getElementById('dEnd').value=FD.dates[FD.dates.length-1];onRange();}
function resetRange(){document.getElementById('pUnit').value='all';var pk=document.getElementById('pPick');pk.style.display='none';pk.innerHTML='';setFull();}
function updateRangeInfo(){var rv=rangeVals();document.getElementById('rangeInfo').textContent=(rv[0]||'')+' ~ '+(rv[1]||'')+' · 영업일 '+nBD+'일';}
function onRange(){page=1;recompute();renderAll();updateRangeInfo();}
function openFull(){
  const data=sortData(forecastAll());
  const head='<tr><th>#</th><th>제품명</th><th class="num">일간</th><th class="num">주간</th><th class="num">월간</th></tr>';
  const body=data.map(function(o,i){return '<tr><td class="rk">'+(i+1)+'</td><td>'+o.name+'</td><td class="num">'+won(o.daily)+'</td><td class="num">'+won(o.weekly)+'</td><td class="num">'+won(o.monthly)+'</td></tr>';}).join('');
  var w=window.open('','_blank','width=1100,height=820,scrollbars=yes');
  if(!w){alert('팝업이 차단되었습니다. 팝업을 허용한 뒤 다시 시도하세요.');return;}
  w.document.write('<!doctype html><html><head><meta charset="utf-8"><title>발주 예측 — 전체</title><style>body{font-family:Malgun Gothic,sans-serif;margin:0;background:#eef2f7;color:#1f2937}.hd{padding:16px 18px 4px}h2{font-size:16px;border-left:4px solid #4f46e5;padding-left:10px;margin:0}.tip{color:#9ca3af;font-size:12px;margin:6px 0}.scroller{margin:12px 14px;background:#fff;border-radius:14px;box-shadow:0 1px 4px rgba(15,23,42,.07);overflow:auto;max-height:88vh}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:7px 10px;border-bottom:1px solid #eef0f3;text-align:left;white-space:nowrap}th{color:#6b7280;position:sticky;top:0;background:#fff;cursor:pointer}th:hover{color:#4f46e5}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.rk{color:#4f46e5;font-weight:700;width:46px}</style></head><body><div class="hd"><h2>📦 제품별 예상 발주량 — '+MLABEL[method].split(' —')[0]+'</h2><div class="tip">컬럼 헤더 클릭 시 정렬됩니다.</div></div><div class="scroller"><table><thead>'+head+'</thead><tbody>'+body+'</tbody></table></div></body></html>');
  w.document.close();
  var tb=w.document.querySelector('table'),ths=tb.querySelectorAll('thead th');
  ths.forEach(function(th,ci){if(ci===0)return;th.onclick=function(){var body=tb.querySelector('tbody'),rows=Array.prototype.slice.call(body.querySelectorAll('tr')),dir=th.getAttribute('data-dir')==='1'?-1:1;ths.forEach(function(o){o.removeAttribute('data-dir');});th.setAttribute('data-dir',dir===1?'1':'0');rows.sort(function(a,b){var x=a.children[ci].textContent.trim(),y=b.children[ci].textContent.trim(),nx=parseFloat(x.replace(/[^0-9.-]/g,'')),ny=parseFloat(y.replace(/[^0-9.-]/g,'')),both=!isNaN(nx)&&!isNaN(ny);return both?(nx-ny)*dir:x.localeCompare(y)*dir;});rows.forEach(function(r,i){if(r.children[0])r.children[0].textContent=(i+1);body.appendChild(r);});};});
}
(function(){
  var lo=FD.dates[0], hi=FD.dates[FD.dates.length-1];
  var ds=document.getElementById('dStart'), de=document.getElementById('dEnd');
  ds.min=lo; ds.max=hi; ds.value=lo; de.min=lo; de.max=hi; de.value=hi;
  document.getElementById('periodInfo').textContent='데이터 전체: '+lo+' ~ '+hi+' ('+FD.dates.length+'일)';
  document.getElementById('methodInfo').textContent='· '+MLABEL[method];
  recompute(); renderAll(); updateRangeInfo();
})();
</script></body></html>'''

# ===================================================================
#  GUI
# ===================================================================


# ---------- D payload (웹 프런트가 /api/dashboard 로 받는 JSON) ----------
def build_payload(s, l):
    """analyze_sales(s)+analyze_logi(l) 결과 -> 대시보드 JS가 쓰는 D payload (build_html과 동일 shape)."""
    esc=lambda t:str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    _sd=({sid:[[esc(cn), round(stk), st] for cn,stk,st in lst]
          for sid,lst in l['soldout_detail'].items()}
         if l and l.get('soldout_detail') else {})
    isod=lambda d:(f"{str(d)[:4]}-{str(d)[4:6]}-{str(d)[6:8]}" if len(str(d))==8 and str(d).isdigit() else str(d))
    VN={}; SN={}; CN={}
    def gi(dct,k):
        i=dct.get(k)
        if i is None: i=len(dct); dct[k]=i
        return i
    F=[]
    for (dd,vd,sk,cn,g,u,rt,o,pv,amv,cogs,cpex) in s['facts']:
        F.append([isod(dd), gi(VN,vd), gi(SN,sk), gi(CN,cn),
                  round(g), round(u), round(rt), round(o), round(pv), round(amv), round(cogs), round(cpex)])
    def _names(dct):
        arr=[""]*len(dct)
        for k,i in dct.items(): arr[i]=esc(k)
        return arr
    _mtx=None
    if l and l.get('matrix') and l['matrix'].get('lf'):
        mm=l['matrix']
        _mtx=dict(centers=[esc(c) for c in mm['centers']],
                  skus=[esc(c) for c in mm['skus']],
                  lf=[[isod(d), si, ci, round(o), round(ib)] for d,si,ci,o,ib in mm['lf']],
                  stk=[[si, ci, round(v)] for si,ci,v in mm['stk']])
    return dict(F=F, VN=_names(VN), SN=_names(SN), CN=_names(CN),
                period=[isod(s['daily'][0][0]), isod(s['daily'][-1][0])],
                ld=(l['last_date'] if l else ''), sd=_sd, mtx=_mtx,
                plan=PLAN_TARGET, logiHtml=build_logi_html(l))


# ---------- 물류/재고 HTML 조각 (build_html의 logi 블록과 동일 — 프런트 #logiMount 에 주입) ----------
def build_logi_html(l):
    if not l:
        return ""
    won=lambda x:f"{x:,.0f}"
    esc=lambda t:str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    _mtx = bool(l.get('matrix') and l['matrix'].get('lf'))
    lch=('<div class="card sm"><div class="k">총 입고</div><div class="v" id="logiInb">'+won(l['tot']['inb'])+'개</div></div>'
         +'<div class="card sm"><div class="k">총 출고</div><div class="v" id="logiOutb">'+won(l['tot']['outb'])+'개</div></div>'
         +'<div class="card sm"><div class="k">현재 재고</div><div class="v">'+won(l['stock_last'])+'개</div></div>'
         +'<div class="card sm"><div class="k">품절 SKU</div><div class="v">'+str(l['soldout'])+' / '+str(l['total_skus'])+'</div></div>'
         +'<div class="card sm"><div class="k">품절율</div><div class="v">'+f"{l['soldout_rate']:.1f}"+'%</div></div>')
    sl=l.get('soldout_list',[])
    soldout_rows="".join(f'<tr><td><a class="link" onclick="showDetail(&#39;{sid}&#39;,this.textContent)">{esc(nm)}</a></td><td class="num">{sc}/{tc}</td><td class="num">{won(stk)}</td></tr>'
                         for nm,sid,sc,tc,stk in sl)
    if not soldout_rows:
        soldout_rows='<tr><td colspan="3" style="text-align:center;color:#9ca3af">품절 상품 없음</td></tr>'
    mtx_panel = ('''
<div class="panel" style="margin-top:16px"><h2 style="margin-top:0">🗺️ 품목 × 센터 매트릭스 <span class="sub">전체 한눈에 · 출고 많은 순 · 상위 100품목</span><button class="fullbtn" onclick="openFullMatrix()">전체보기 ⧉</button></h2>
<div class="toggle"><button id="mtxO" class="active" onclick="setMtx('o')">출고</button><button id="mtxI" onclick="setMtx('i')">입고</button><button id="mtxS" onclick="setMtx('s')">재고(현재)</button></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="mtxHead"></thead><tbody id="mtxBody"></tbody></table></div></div>
<div class="panel" style="margin-top:16px"><h2 style="margin-top:0">📦 상품 × 일자/월 매트릭스 <span class="sub">상품의 날짜별 출고·입고(전 센터 합산, 물류) / 판매수량(고객 결제 기준, 판매) · 상위 100품목 · 이 표는 아래 자체 기간 사용(상단 기간 무시)</span><button class="fullbtn" onclick="openFullSkuTime()">전체보기 ⧉</button></h2>
<div class="trendctl" style="margin-bottom:10px"><strong style="font-size:12px">📅 이 표 기간</strong><label><input type="date" id="stStart" onchange="renderSkuTime()"> ~ <input type="date" id="stEnd" onchange="renderSkuTime()"></label><button class="resetbtn" onclick="stReset()">전체</button><span class="sub" id="stInfo"></span></div>
<div class="toggle"><button id="stO" class="active" onclick="setSkuTime('o')">출고</button><button id="stI" onclick="setSkuTime('i')">입고</button><button id="stS" onclick="setSkuTime('s')">판매수량</button></div>
<div class="toggle" style="margin-left:8px"><button id="stDay" class="active" onclick="setStUnit('day')">일별</button><button id="stMon" onclick="setStUnit('month')">월별</button></div>
<div class="scrollbox mtxbox"><table class="mtx sortable"><thead id="stHead"></thead><tbody id="stBody"></tbody></table></div></div>''' if _mtx else '')
    logi=f'''<h2>🚚 물류 / 재고 지표 <span class="sub">기준일: {l["last_date"]}</span></h2>
<div class="cards">{lch}</div>
<div class="grid">
<div class="panel"><h2 style="margin-top:0">🏭 센터별 성장 <span class="sub" id="grInfo"></span><button class="fullbtn" onclick="openFullGrowth()">전체보기 ⧉</button></h2>
<div class="trendctl"><select class="psel" id="grUnit" onchange="onGrowthUnit()"><option value="month">월</option><option value="week">주</option></select><select class="psel" id="grPick" onchange="onGrowthPick()"></select></div>
<div class="scrollbox"><table class="sortable"><thead><tr><th>#</th><th>센터</th><th class="num">이번 기간</th><th class="num">직전 기간</th><th class="num">증감률</th></tr></thead><tbody id="grBody"></tbody></table></div></div>
<div class="panel"><h2 style="margin-top:0">⛔ 품절 상품 <span class="sub">{len(sl)}건 · 품절센터 많은 순</span></h2>
<div class="scrollbox"><table class="sortable"><thead><tr><th>상품명</th><th class="num">품절센터</th><th class="num">재고</th></tr></thead><tbody>{soldout_rows}</tbody></table></div></div>
</div>
{mtx_panel}'''
    return logi
