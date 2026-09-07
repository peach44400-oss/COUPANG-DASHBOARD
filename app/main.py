# -*- coding: utf-8 -*-
"""쿠팡 통합 대시보드 — FastAPI 웹앱.

실행:  python app/main.py   →  http://127.0.0.1:8700
분석/집계/병합/예측 로직은 analytics.py 에 그대로 이관(검증된 공식 불변).
"""
import os
import sys
import json
import time
import base64
import hashlib
import threading
import webbrowser
import subprocess
import urllib.request
import datetime as dt
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analytics as A

# ── 경로: 정적=_MEIPASS(frozen)/app(source), 데이터=exe 옆(업데이트 시 유지) ──
if getattr(sys, "frozen", False):
    BASE = Path(sys._MEIPASS)
    DATA_BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent
    DATA_BASE = BASE.parent
DATA_DIR = DATA_BASE / "data"
DATA_DIR.mkdir(exist_ok=True)
TMP_DIR = DATA_DIR / "_upload"
TMP_DIR.mkdir(exist_ok=True)

# ── 앱 버전 & 자동 업데이트 ──
APP_VERSION = "1.0.2"
UPDATE_MANIFEST_URL = "https://github.com/peach44400-oss/COUPANG-DASHBOARD/releases/latest/download/version.json"


def manifest_url():
    f = DATA_BASE / "update_url.txt"
    if f.exists():
        try:
            u = f.read_text(encoding="utf-8").strip()
            if u:
                return u
        except OSError:
            pass
    return UPDATE_MANIFEST_URL


def _nocache_request(url):
    return urllib.request.Request(
        url + (("&" if "?" in url else "?") + "_cb=" + str(int(time.time()))),
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})


def fetch_manifest():
    u = manifest_url()
    if not u.lower().startswith("https://"):
        raise RuntimeError("업데이트 주소가 https 가 아닙니다")
    with urllib.request.urlopen(_nocache_request(u), timeout=20) as r:
        m = json.loads(r.read().decode("utf-8"))
    if not (m.get("version") and m.get("url")):
        raise RuntimeError("version.json 형식 오류")
    if not str(m["url"]).lower().startswith("https://"):
        raise RuntimeError("다운로드 주소가 https 가 아닙니다")
    return m


def version_newer(a, b):
    def parts(v):
        return [int(x) for x in str(v).strip().split(".") if x.isdigit()]
    pa, pb = parts(a), parts(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa)); pb += [0] * (n - len(pb))
    return pa > pb


app = FastAPI(title="쿠팡 통합 대시보드")


# ── 마스터 로드/저장 헬퍼 ──
def _master():
    return A.load_master(str(DATA_DIR))


def _decode_uploads(files):
    """[{name,data(base64 dataURL)}] → 임시 파일 경로 리스트."""
    paths = []
    for i, f in enumerate(files or []):
        name = os.path.basename(f.get("name") or f"upload_{i}")
        raw = f.get("data") or ""
        if "," in raw[:80]:
            raw = raw.split(",", 1)[1]
        data = base64.b64decode(raw)
        p = TMP_DIR / name
        p.write_bytes(data)
        paths.append(str(p))
    return paths


# ================= API =================
@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/ping")
def ping():
    return {"ok": True, "version": APP_VERSION}


@app.get("/api/state")
def state():
    m = _master()
    lo, hi = A.master_range(m)
    archives = sorted(
        [{"name": p.name, "size": p.stat().st_size}
         for p in DATA_DIR.glob("통합_*.xlsx")],
        key=lambda x: x["name"], reverse=True)
    return {
        "version": APP_VERSION,
        "frozen": bool(getattr(sys, "frozen", False)),
        "range": [lo, hi] if lo else [None, None],
        "salesRows": len(m["sales"][1]),
        "logiRows": len(m["logi"][1]),
        "hasData": bool(m["sales"][1]),
        "archives": archives,
    }


@app.get("/api/dashboard")
def dashboard():
    m = _master()
    if not m["sales"][1]:
        return {"empty": True}
    s = A.analyze_sales(*m["sales"])
    if not s:
        return {"empty": True}
    l = A.analyze_logi(*m["logi"]) if m["logi"][1] else None
    return A.build_payload(s, l)


@app.post("/api/upload")
async def upload(req: Request):
    body = await req.json()
    paths = _decode_uploads(body.get("files"))
    if not paths:
        raise HTTPException(400, "업로드된 파일이 없습니다")
    m = _master()
    res = A.merge_files_into_master(m, paths)
    added = replaced = skipped = 0
    for kind in ("sales", "logi"):
        st = res.get(kind)
        if st:
            added += len(st.get("added", [])); replaced += len(st.get("replaced", [])); skipped += len(st.get("skipped", []))
    detected = {"sales": 0, "logi": 0, "unknown": 0}
    for (_nm, kind, _n) in res.get("detected", []):
        detected[kind if kind in ("sales", "logi") else "unknown"] += 1
    if body.get("apply"):
        A.save_master(str(DATA_DIR), m["sales"], m["logi"])
    for p in paths:
        try: os.remove(p)
        except OSError: pass
    lo, hi = A.master_range(m)
    return {"added": added, "replaced": replaced, "skipped": skipped,
            "detected": detected, "range": [lo, hi] if lo else [None, None]}


@app.post("/api/archive")
def archive():
    m = _master()
    path = A.archive_and_reset(str(DATA_DIR), m)
    return {"ok": True, "archive": os.path.basename(path) if path else ""}


@app.get("/api/archive/{name}")
def open_archive(name: str):
    name = os.path.basename(name)
    p = DATA_DIR / name
    if not p.exists():
        raise HTTPException(404, "보관본을 찾을 수 없습니다")
    master = A.load_xlsx_master(str(p))
    html, xlsx, _ = A.generate_from_master(master, str(TMP_DIR))
    return HTMLResponse(Path(html).read_text(encoding="utf-8"))


@app.get("/api/export/dashboard.xlsx")
def export_dashboard():
    m = _master()
    if not m["sales"][1]:
        raise HTTPException(400, "데이터가 없습니다")
    A.generate_from_master(m, str(DATA_DIR))
    return FileResponse(str(DATA_DIR / "dashboard.xlsx"),
                        filename="쿠팡대시보드.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/forecast")
async def forecast(req: Request):
    body = await req.json()
    paths = _decode_uploads(body.get("files"))
    if not paths:
        raise HTTPException(400, "업로드된 파일이 없습니다")
    html, xlsx, parsed = A.generate_forecast(paths, str(DATA_DIR))
    for p in paths:
        try: os.remove(p)
        except OSError: pass
    return {"html": Path(html).read_text(encoding="utf-8"),
            "prods": len(parsed.get("prods", [])),
            "vends": len(parsed.get("vends", [])),
            "period": (parsed["dates"][0] + " ~ " + parsed["dates"][-1]) if parsed.get("dates") else "-"}


@app.get("/api/export/forecast.xlsx")
def export_forecast():
    p = DATA_DIR / "발주예측.xlsx"
    if not p.exists():
        raise HTTPException(400, "먼저 예측을 실행하세요")
    return FileResponse(str(p), filename="발주예측.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── 자동 업데이트 ──
@app.get("/api/update/check")
def update_check():
    info = {"current": APP_VERSION, "frozen": bool(getattr(sys, "frozen", False))}
    try:
        m = fetch_manifest()
    except Exception as e:
        info["error"] = str(e); return info
    info.update(latest=m["version"], notes=m.get("notes", ""), url=m["url"],
                newer=version_newer(m["version"], APP_VERSION))
    return info


@app.post("/api/update/apply")
def update_apply():
    if not getattr(sys, "frozen", False):
        raise HTTPException(400, "개발 모드에서는 자동 업데이트를 쓸 수 없습니다 (배포 exe 전용)")
    m = fetch_manifest()
    if not version_newer(m["version"], APP_VERSION):
        raise HTTPException(400, "이미 최신 버전입니다")
    exe = Path(sys.executable)
    newexe = exe.with_name(exe.stem + "_업데이트" + exe.suffix)
    with urllib.request.urlopen(_nocache_request(m["url"]), timeout=180) as r:
        raw = r.read()
    if len(raw) < 1_000_000:
        raise HTTPException(502, "다운로드 파일이 너무 작습니다")
    want = (m.get("sha256") or "").lower().strip()
    if want and hashlib.sha256(raw).hexdigest() != want:
        raise HTTPException(502, "체크섬 불일치")
    newexe.write_bytes(raw)
    bat = exe.with_name("_자동업데이트.bat")
    bat.write_text(
        "@echo off\r\nchcp 65001 >nul\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f':loop\r\nmove /y "{newexe.name}" "{exe.name}" >nul 2>&1\r\n'
        "if errorlevel 1 (timeout /t 1 /nobreak >nul & goto loop)\r\n"
        f'start "" explorer.exe "{exe}"\r\n'
        'del "%~f0"\r\n', encoding="utf-8")

    def _relaunch():
        time.sleep(0.6)
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(exe.parent),
                         creationflags=0x00000010)
        time.sleep(0.4); os._exit(0)
    threading.Thread(target=_relaunch, daemon=True).start()
    return {"ok": True, "version": m["version"]}


# ── 정적 파일 마운트(맨 끝) ──
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def _wait_port_free(port, timeout=20):
    import socket
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return True
        finally:
            s.close()
        time.sleep(0.4)
    return False


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8700"))
    _wait_port_free(port, 8)
    url = f"http://127.0.0.1:{port}"
    if not os.environ.get("PORT"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        print(f"\n  쿠팡 통합 대시보드 실행 중 →  {url}\n  (이 창을 닫으면 종료됩니다)\n")
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=port, log_level="warning")
