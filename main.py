"""
광고를 잘 아는 사람들 — 인트라넷 백엔드 API v5
FastAPI + Supabase REST (No SDK) + Decodo Proxy
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os, httpx, random, json, re, hashlib, time, urllib.parse
from datetime import datetime, timedelta

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
PROXY_HOST = os.getenv("PROXY_HOST", "kr.decodo.com")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")
PROXY_PORT_START = int(os.getenv("PROXY_PORT_START", "10001"))
PROXY_PORT_END = int(os.getenv("PROXY_PORT_END", "19999"))

app = FastAPI(title="AdPeople API", version="5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SB_HEADERS = {}

@app.on_event("startup")
async def startup():
    global SB_HEADERS
    SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

async def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}" if params else f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, headers=SB_HEADERS)
        if r.status_code >= 400: raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_post(table, data):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, json=data)
        if r.status_code >= 400: raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_patch(table, params, data):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=SB_HEADERS, json=data)
        if r.status_code >= 400: raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_delete(table, params):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=SB_HEADERS)
        if r.status_code >= 400: raise HTTPException(status_code=r.status_code, detail=r.text)
        return {"ok": True}

def get_proxy():
    port = random.randint(PROXY_PORT_START, PROXY_PORT_END)
    return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{port}"

NAVER_HDR = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36","Referer":"https://m.search.naver.com/","Accept-Language":"ko-KR,ko;q=0.9"}

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

# Models
class LoginRequest(BaseModel):
    user_id: str; password: str
class CampaignCreate(BaseModel):
    campaign_name: str; campaign_type: str = "smart_place"; client_name: str = ""; place_url: str = ""; keywords: str = ""; daily_traffic: int = 0; status: str = "active"; memo: str = ""
class CampaignUpdate(BaseModel):
    campaign_name: Optional[str] = None; campaign_type: Optional[str] = None; client_name: Optional[str] = None; place_url: Optional[str] = None; keywords: Optional[str] = None; daily_traffic: Optional[int] = None; status: Optional[str] = None; memo: Optional[str] = None
class RankCheckRequest(BaseModel):
    keyword: str; place_id: str; rank_range: int = 300
class RankMonitorAdd(BaseModel):
    keyword: str; place_id: str; place_name: str = ""
class KeyHunterRequest(BaseModel):
    place_id: str; keyword_count: int = 50
class NoticeCreate(BaseModel):
    title: str; content: str; is_pinned: bool = False
class NoticeUpdate(BaseModel):
    title: Optional[str] = None; content: Optional[str] = None; is_pinned: Optional[bool] = None
class BoardPostCreate(BaseModel):
    title: str; content: str; author: str = ""
class BoardPostUpdate(BaseModel):
    title: Optional[str] = None; content: Optional[str] = None
class TeamMemberCreate(BaseModel):
    user_id: str; password: str; name: str; position: str = ""; role: str = "STAFF"; level: int = 1
class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None; position: Optional[str] = None; role: Optional[str] = None; level: Optional[int] = None
class SalesRecord(BaseModel):
    date: str; client_name: str; item: str = ""; amount: int = 0; cost: int = 0; profit: int = 0; memo: str = ""

@app.get("/health")
async def health():
    return {"status":"ok","version":"5.0","time":datetime.now().isoformat()}

# AUTH
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    try: users = await sb_get("users", f"user_id=eq.{req.user_id}&select=*")
    except Exception as e: raise HTTPException(500, f"DB 연결 실패: {str(e)}")
    if not users: raise HTTPException(401, "아이디가 존재하지 않습니다")
    user = users[0]
    if user["password_hash"] != hash_pw(req.password): raise HTTPException(401, "비밀번호가 틀렸습니다")
    return {"success":True,"user":{"id":user.get("id"),"user_id":user["user_id"],"name":user["name"],"position":user.get("position",""),"role":user.get("role","STAFF"),"level":user.get("level",1)}}

# CAMPAIGNS
@app.get("/api/campaigns")
async def get_campaigns(): return await sb_get("campaigns","order=created_at.desc")
@app.post("/api/campaigns")
async def create_campaign(req: CampaignCreate):
    d = req.dict(); d["created_at"]=datetime.now().isoformat(); r=await sb_post("campaigns",d); return r[0] if isinstance(r,list) else r
@app.patch("/api/campaigns/{cid}")
async def update_campaign(cid:int, req:CampaignUpdate):
    d={k:v for k,v in req.dict().items() if v is not None}; d["updated_at"]=datetime.now().isoformat(); r=await sb_patch("campaigns",f"id=eq.{cid}",d); return r[0] if isinstance(r,list) else r
@app.delete("/api/campaigns/{cid}")
async def delete_campaign(cid:int): return await sb_delete("campaigns",f"id=eq.{cid}")

# RANK MONITORING
async def _get_place_detail(pid, proxy=None):
    p = proxy or get_proxy()
    detail = {"name":"","n1":0,"n2":0,"n3":0,"blog_review":0,"visitor_review":0}
    try:
        async with httpx.AsyncClient(proxy=p, timeout=15, verify=False) as c:
            r = await c.get(f"https://m.place.naver.com/restaurant/{pid}/home", headers={"User-Agent":NAVER_HDR["User-Agent"],"Referer":"https://m.place.naver.com/"})
            text = r.text
        nm = re.search(r'"name"\s*:\s*"([^"]+)"', text)
        if nm: detail["name"] = nm.group(1)
        br = re.search(r'"blogCafeReviewCount"\s*:\s*(\d+)', text)
        if br: detail["blog_review"] = int(br.group(1))
        vr = re.search(r'"visitorReviewCount"\s*:\s*(\d+)', text)
        if vr: detail["visitor_review"] = int(vr.group(1))
    except: pass
    return detail

async def _find_rank(keyword, place_id, rank_range=300, proxy=None):
    p = proxy or get_proxy()
    rank = 0; pure_rank = 0; all_results = []
    for start in range(1, rank_range+1, 50):
        try:
            url = f"https://m.search.naver.com/search.naver?where=m_local&query={urllib.parse.quote(keyword)}&start={start}"
            async with httpx.AsyncClient(proxy=p, timeout=20, verify=False) as c:
                r = await c.get(url, headers=NAVER_HDR)
                text = r.text
            items = re.findall(r'"id"\s*:\s*"?(\d+)"?', text)
            ad_ids = set(re.findall(r'"isAdItem"\s*:\s*true[^}]*"id"\s*:\s*"?(\d+)"?', text))
            for m2 in re.finditer(r'"id"\s*:\s*"?(\d+)"?[^}]*"isAdItem"\s*:\s*true', text):
                ad_ids.add(m2.group(1))
            seen = set()
            for item_id in items:
                if item_id in seen: continue
                seen.add(item_id)
                if item_id in ad_ids: continue
                pure_rank += 1
                matched = str(item_id)==str(place_id)
                all_results.append({"rank":pure_rank,"place_id":item_id,"matched":matched})
                if matched and rank==0: rank=pure_rank
        except: pass
        time.sleep(0.3)
    return {"rank":rank,"results":all_results[:50]}

@app.post("/api/rank/check")
async def check_rank(req: RankCheckRequest):
    proxy = get_proxy()
    detail = await _get_place_detail(req.place_id, proxy)
    rr = await _find_rank(req.keyword, req.place_id, req.rank_range, proxy)
    today = datetime.now().strftime("%Y-%m-%d")
    rec = {"keyword":req.keyword,"place_id":req.place_id,"place_name":detail["name"],"rank":rr["rank"],"n1_score":detail["n1"],"n2_score":detail["n2"],"n3_score":detail["n3"],"blog_review":detail["blog_review"],"visitor_review":detail["visitor_review"],"check_date":today,"checked_at":datetime.now().isoformat()}
    try: await sb_post("rank_history", rec)
    except: pass
    return {**rec, "results":rr["results"]}

@app.get("/api/rank/monitors")
async def get_monitors(): return await sb_get("rank_monitors","order=created_at.desc")
@app.post("/api/rank/monitors")
async def add_monitor(req: RankMonitorAdd):
    d={"keyword":req.keyword,"place_id":req.place_id,"place_name":req.place_name,"created_at":datetime.now().isoformat()}
    r=await sb_post("rank_monitors",d); return r[0] if isinstance(r,list) else r
@app.delete("/api/rank/monitors/{mid}")
async def delete_monitor(mid:int): return await sb_delete("rank_monitors",f"id=eq.{mid}")

@app.get("/api/rank/history")
async def rank_history(keyword:str="", place_id:str="", days:int=7):
    params="order=check_date.desc,checked_at.desc"
    if keyword: params+=f"&keyword=eq.{urllib.parse.quote(keyword)}"
    if place_id: params+=f"&place_id=eq.{place_id}"
    sd=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    params+=f"&check_date=gte.{sd}"
    return await sb_get("rank_history",params)

@app.post("/api/rank/check-all")
async def check_all():
    mons = await sb_get("rank_monitors","select=*")
    results=[]
    for m in mons:
        try:
            px=get_proxy(); d=await _get_place_detail(m["place_id"],px); rr=await _find_rank(m["keyword"],m["place_id"],300,px)
            today=datetime.now().strftime("%Y-%m-%d")
            rec={"keyword":m["keyword"],"place_id":m["place_id"],"place_name":d.get("name",m.get("place_name","")),"rank":rr["rank"],"n1_score":d["n1"],"n2_score":d["n2"],"n3_score":d["n3"],"blog_review":d["blog_review"],"visitor_review":d["visitor_review"],"check_date":today,"checked_at":datetime.now().isoformat()}
            await sb_post("rank_history",rec)
            results.append({"keyword":m["keyword"],"rank":rr["rank"],"status":"ok"})
        except Exception as e: results.append({"keyword":m["keyword"],"rank":0,"status":str(e)})
        time.sleep(1)
    return {"checked":len(results),"results":results}

# KEYHUNTER
@app.post("/api/keyhunter/analyze")
async def keyhunter(req: KeyHunterRequest):
    proxy=get_proxy(); pid=req.place_id
    detail=await _get_place_detail(pid,proxy)
    place_name=detail["name"]
    try:
        async with httpx.AsyncClient(proxy=proxy,timeout=15,verify=False) as c:
            r=await c.get(f"https://m.place.naver.com/restaurant/{pid}/home",headers={"User-Agent":NAVER_HDR["User-Agent"],"Referer":"https://m.place.naver.com/"})
            text=r.text
    except: text=""
    categories=list(set(re.findall(r'"category"\s*:\s*"([^"]+)"',text)))[:10]
    am=re.search(r'"roadAddress"\s*:\s*"([^"]+)"',text)
    address=am.group(1) if am else ""
    rp=[]
    if address:
        pts=address.split()
        if len(pts)>=2: rp.extend([pts[0],pts[1]])
        if len(pts)>=3: rp.append(pts[2])
    test_kws=[]
    for rg in rp:
        for cat in categories:
            kw=f"{rg} {cat}"
            if place_name not in kw: test_kws.append(kw)
        test_kws.extend([f"{rg} 맛집",f"{rg} 추천"])
    for cat in categories: test_kws.append(cat)
    test_kws=list(dict.fromkeys(test_kws))[:req.keyword_count]
    found=[]
    for kw in test_kws:
        try:
            px2=get_proxy()
            url=f"https://m.search.naver.com/search.naver?where=m_local&query={urllib.parse.quote(kw)}&start=1"
            async with httpx.AsyncClient(proxy=px2,timeout=20,verify=False) as c:
                r2=await c.get(url,headers=NAVER_HDR); t2=r2.text
            items=re.findall(r'"id"\s*:\s*"?(\d+)"?',t2)
            ad_ids=set(re.findall(r'"isAdItem"\s*:\s*true[^}]*"id"\s*:\s*"?(\d+)"?',t2))
            for mx in re.finditer(r'"id"\s*:\s*"?(\d+)"?[^}]*"isAdItem"\s*:\s*true',t2): ad_ids.add(mx.group(1))
            pr=0;mr=0;seen=set()
            for iid in items:
                if iid in seen: continue
                seen.add(iid)
                if iid in ad_ids: continue
                pr+=1
                if str(iid)==str(pid) and mr==0: mr=pr
                if pr>5: break
            if 1<=mr<=5: found.append({"keyword":kw,"rank":mr})
        except: pass
        time.sleep(0.5)
    return {"place_id":pid,"place_name":place_name,"address":address,"categories":categories,"tested_count":len(test_kws),"found_keywords":found,"tested_keywords":test_kws}

# NOTICES
@app.get("/api/notices")
async def get_notices(): return await sb_get("notices","order=is_pinned.desc,created_at.desc")
@app.post("/api/notices")
async def create_notice(req:NoticeCreate):
    d=req.dict();d["created_at"]=datetime.now().isoformat();d["author"]="관리자";r=await sb_post("notices",d);return r[0] if isinstance(r,list) else r
@app.patch("/api/notices/{nid}")
async def update_notice(nid:int,req:NoticeUpdate):
    d={k:v for k,v in req.dict().items() if v is not None};d["updated_at"]=datetime.now().isoformat();r=await sb_patch("notices",f"id=eq.{nid}",d);return r[0] if isinstance(r,list) else r
@app.delete("/api/notices/{nid}")
async def delete_notice(nid:int): return await sb_delete("notices",f"id=eq.{nid}")

# BOARD
@app.get("/api/board")
async def get_board(): return await sb_get("board_posts","order=created_at.desc")
@app.get("/api/board/{pid}")
async def get_post(pid:int):
    r=await sb_get("board_posts",f"id=eq.{pid}")
    if not r: raise HTTPException(404,"not found")
    try:
        v=(r[0].get("views",0)or 0)+1;await sb_patch("board_posts",f"id=eq.{pid}",{"views":v})
    except:pass
    return r[0]
@app.post("/api/board")
async def create_post(req:BoardPostCreate):
    d=req.dict();d["created_at"]=datetime.now().isoformat();d["views"]=0;r=await sb_post("board_posts",d);return r[0] if isinstance(r,list) else r
@app.patch("/api/board/{pid}")
async def update_post(pid:int,req:BoardPostUpdate):
    d={k:v for k,v in req.dict().items() if v is not None};d["updated_at"]=datetime.now().isoformat();r=await sb_patch("board_posts",f"id=eq.{pid}",d);return r[0] if isinstance(r,list) else r
@app.delete("/api/board/{pid}")
async def delete_post(pid:int): return await sb_delete("board_posts",f"id=eq.{pid}")

# SALES
@app.get("/api/sales")
async def get_sales(month:str=""):
    params="order=date.desc"
    if month:
        s=f"{month}-01";em=int(month.split("-")[1]);ey=int(month.split("-")[0])
        end=f"{ey+1}-01-01" if em==12 else f"{ey}-{em+1:02d}-01"
        params+=f"&date=gte.{s}&date=lt.{end}"
    return await sb_get("sales",params)
@app.post("/api/sales")
async def create_sale(req:SalesRecord):
    d=req.dict();d["created_at"]=datetime.now().isoformat();r=await sb_post("sales",d);return r[0] if isinstance(r,list) else r
@app.patch("/api/sales/{sid}")
async def update_sale(sid:int,data:dict):
    data["updated_at"]=datetime.now().isoformat();r=await sb_patch("sales",f"id=eq.{sid}",data);return r[0] if isinstance(r,list) else r
@app.delete("/api/sales/{sid}")
async def delete_sale(sid:int): return await sb_delete("sales",f"id=eq.{sid}")

# TEAM
@app.get("/api/team")
async def get_team(): return await sb_get("users","select=id,user_id,name,position,role,level,created_at&order=level.desc,created_at.asc")
@app.post("/api/team")
async def create_member(req:TeamMemberCreate):
    ex=await sb_get("users",f"user_id=eq.{req.user_id}")
    if ex: raise HTTPException(409,"이미 존재하는 아이디")
    d={"user_id":req.user_id,"password_hash":hash_pw(req.password),"name":req.name,"position":req.position,"role":req.role,"level":req.level,"created_at":datetime.now().isoformat()}
    r=await sb_post("users",d);return r[0] if isinstance(r,list) else r
@app.patch("/api/team/{uid}")
async def update_member(uid:int,req:TeamMemberUpdate):
    d={k:v for k,v in req.dict().items() if v is not None};r=await sb_patch("users",f"id=eq.{uid}",d);return r[0] if isinstance(r,list) else r
@app.delete("/api/team/{uid}")
async def delete_member(uid:int): return await sb_delete("users",f"id=eq.{uid}")

# SELLER DB
@app.get("/api/sellerdb/search")
async def search_seller(keyword:str=""):
    if not keyword: raise HTTPException(400,"키워드 입력")
    proxy=get_proxy();results=[]
    try:
        for st in [1,16,31]:
            url=f"https://m.search.naver.com/search.naver?where=m_local&query={urllib.parse.quote(keyword)}&start={st}"
            async with httpx.AsyncClient(proxy=proxy,timeout=15,verify=False) as c:
                r=await c.get(url,headers=NAVER_HDR);text=r.text
            names=re.findall(r'"name":"([^"]+)"',text);addrs=re.findall(r'"roadAddress":"([^"]+)"',text);phones=re.findall(r'"phone":"([^"]*)"',text)
            for i in range(len(names)):
                results.append({"name":names[i],"address":addrs[i] if i<len(addrs) else "","phone":phones[i] if i<len(phones) else ""})
            time.sleep(0.3)
    except Exception as e: raise HTTPException(500,f"크롤링 에러: {str(e)}")
    return {"keyword":keyword,"count":len(results),"results":results}

@app.get("/api/proxy/status")
async def proxy_status():
    proxy=get_proxy()
    try:
        async with httpx.AsyncClient(proxy=proxy,timeout=10,verify=False) as c:
            r=await c.get("https://httpbin.org/ip");return {"status":"ok","proxy_ip":r.json().get("origin","?")}
    except Exception as e: return {"status":"error","detail":str(e)}

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    try:
        ca=await sb_get("campaigns","select=id,status");us=await sb_get("users","select=id");nt=await sb_get("notices","select=id")
        sl=await sb_get("sales","select=amount,profit");mn=await sb_get("rank_monitors","select=id")
        ta=sum(s.get("amount",0)for s in sl)if sl else 0;tp=sum(s.get("profit",0)for s in sl)if sl else 0
        ac=len([c for c in ca if c.get("status")=="active"])if ca else 0
        return {"total_campaigns":len(ca)if ca else 0,"active_campaigns":ac,"total_members":len(us)if us else 0,"total_notices":len(nt)if nt else 0,"total_sales_amount":ta,"total_profit":tp,"total_monitors":len(mn)if mn else 0}
    except: return {"total_campaigns":0,"active_campaigns":0,"total_members":0,"total_notices":0,"total_sales_amount":0,"total_profit":0,"total_monitors":0}

@app.exception_handler(Exception)
async def gh(request,exc): return JSONResponse(500,{"detail":str(exc)})
