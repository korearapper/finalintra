"""
광고를 잘 아는 사람들 — 인트라넷 백엔드 API v4
FastAPI + Supabase REST (No SDK) + Decodo Proxy
Railway 배포용
"""
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os, httpx, random, json, re, hashlib, time
from datetime import datetime, timedelta

# ===== ENV =====
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
PROXY_HOST = os.getenv("PROXY_HOST", "kr.decodo.com")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")
PROXY_PORT_START = int(os.getenv("PROXY_PORT_START", "10001"))
PROXY_PORT_END = int(os.getenv("PROXY_PORT_END", "19999"))
JWT_SECRET = os.getenv("JWT_SECRET", "adpeople-secret-2026")

# ===== APP =====
app = FastAPI(title="광고를 잘 아는 사람들 API", version="4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== SUPABASE REST HELPERS =====
SB_HEADERS = {}

@app.on_event("startup")
async def startup():
    global SB_HEADERS
    SB_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

async def sb_get(table: str, params: str = ""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}" if params else f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(url, headers=SB_HEADERS)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_post(table: str, data: dict):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, json=data)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_patch(table: str, params: str, data: dict):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.patch(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=SB_HEADERS, json=data)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

async def sb_delete(table: str, params: str):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=SB_HEADERS)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return {"ok": True}

# ===== PROXY =====
def get_proxy() -> str:
    port = random.randint(PROXY_PORT_START, PROXY_PORT_END)
    return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{port}"

# ===== MODELS =====
class LoginRequest(BaseModel):
    user_id: str
    password: str

class CampaignCreate(BaseModel):
    campaign_name: str
    campaign_type: str = "smart_place"
    client_name: str = ""
    place_url: str = ""
    keywords: str = ""
    daily_traffic: int = 0
    status: str = "active"
    memo: str = ""

class CampaignUpdate(BaseModel):
    campaign_name: Optional[str] = None
    campaign_type: Optional[str] = None
    client_name: Optional[str] = None
    place_url: Optional[str] = None
    keywords: Optional[str] = None
    daily_traffic: Optional[int] = None
    status: Optional[str] = None
    memo: Optional[str] = None

class RankCheckRequest(BaseModel):
    keyword: str
    place_name: Optional[str] = None
    phone: Optional[str] = None
    rank_range: int = 300

class NoticeCreate(BaseModel):
    title: str
    content: str
    is_pinned: bool = False

class NoticeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_pinned: Optional[bool] = None

class TeamMemberCreate(BaseModel):
    user_id: str
    password: str
    name: str
    position: str = ""
    role: str = "STAFF"
    level: int = 1

class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    role: Optional[str] = None
    level: Optional[int] = None

class SalesRecord(BaseModel):
    date: str
    client_name: str
    item: str = ""
    amount: int = 0
    cost: int = 0
    profit: int = 0
    memo: str = ""

# ===== UTILS =====
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ===== HEALTH =====
@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0", "time": datetime.now().isoformat()}

# ===== AUTH =====
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    try:
        users = await sb_get("users", f"user_id=eq.{req.user_id}&select=*")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 연결 실패: {str(e)}")
    if not users:
        raise HTTPException(status_code=401, detail="아이디가 존재하지 않습니다")
    user = users[0]
    if user["password_hash"] != hash_pw(req.password):
        raise HTTPException(status_code=401, detail="비밀번호가 틀렸습니다")
    return {
        "success": True,
        "user": {
            "id": user.get("id"),
            "user_id": user["user_id"],
            "name": user["name"],
            "position": user.get("position", ""),
            "role": user.get("role", "STAFF"),
            "level": user.get("level", 1),
        }
    }

# ===== CAMPAIGNS =====
@app.get("/api/campaigns")
async def get_campaigns():
    return await sb_get("campaigns", "order=created_at.desc")

@app.post("/api/campaigns")
async def create_campaign(req: CampaignCreate):
    data = req.dict()
    data["created_at"] = datetime.now().isoformat()
    result = await sb_post("campaigns", data)
    return result[0] if isinstance(result, list) else result

@app.patch("/api/campaigns/{cid}")
async def update_campaign(cid: int, req: CampaignUpdate):
    data = {k: v for k, v in req.dict().items() if v is not None}
    data["updated_at"] = datetime.now().isoformat()
    result = await sb_patch("campaigns", f"id=eq.{cid}", data)
    return result[0] if isinstance(result, list) else result

@app.delete("/api/campaigns/{cid}")
async def delete_campaign(cid: int):
    return await sb_delete("campaigns", f"id=eq.{cid}")

# ===== RANK CHECK (네이버 플레이스) =====
@app.post("/api/rank/check")
async def check_rank(req: RankCheckRequest):
    results = []
    proxy = get_proxy()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://m.search.naver.com/"
    }
    try:
        for start in range(1, req.rank_range + 1, 50):
            url = f"https://m.search.naver.com/search.naver?where=m_local&query={req.keyword}&start={start}"
            async with httpx.AsyncClient(proxy=proxy, timeout=15, verify=False) as c:
                r = await c.get(url, headers=headers)
                text = r.text
                # 간단한 파싱 - place 이름 추출
                places = re.findall(r'"name":"([^"]+)"', text)
                for i, name in enumerate(places):
                    rank = start + i
                    is_ad = False  # 광고 필터링은 별도 로직 필요
                    matched = False
                    if req.place_name and req.place_name in name:
                        matched = True
                    results.append({
                        "rank": rank,
                        "name": name,
                        "is_ad": is_ad,
                        "matched": matched
                    })
            time.sleep(0.3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 에러: {str(e)}")

    found = [r for r in results if r.get("matched")]
    return {
        "keyword": req.keyword,
        "total_results": len(results),
        "found": found,
        "found_rank": found[0]["rank"] if found else None,
        "results": results[:50]  # 상위 50개만 반환
    }

# ===== KEYHUNTER =====
@app.post("/api/keyhunter/analyze")
async def keyhunter_analyze(place_url: str = "", keyword_count: int = 30):
    """플레이스 URL에서 키워드 추출 + 순위 분석"""
    proxy = get_proxy()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://m.place.naver.com/"
    }
    try:
        # 1. 플레이스 정보 가져오기
        place_id = re.search(r'/(\d+)', place_url)
        if not place_id:
            raise HTTPException(status_code=400, detail="유효하지 않은 플레이스 URL")
        pid = place_id.group(1)
        async with httpx.AsyncClient(proxy=proxy, timeout=15, verify=False) as c:
            r = await c.get(f"https://m.place.naver.com/restaurant/{pid}/home", headers=headers)
            text = r.text
        # 업체명 추출
        name_match = re.search(r'"name":"([^"]+)"', text)
        place_name = name_match.group(1) if name_match else "알수없음"
        # 카테고리, 키워드 추출
        cat_match = re.findall(r'"category":"([^"]+)"', text)
        categories = list(set(cat_match))[:5]
        return {
            "place_id": pid,
            "place_name": place_name,
            "categories": categories,
            "suggested_keywords": categories,  # 확장 가능
            "message": "분석 완료"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KeyHunter 에러: {str(e)}")

# ===== RANK HISTORY =====
@app.get("/api/rank/history")
async def rank_history(keyword: str = "", place_name: str = ""):
    params = "order=checked_at.desc&limit=30"
    if keyword:
        params += f"&keyword=eq.{keyword}"
    if place_name:
        params += f"&place_name=eq.{place_name}"
    return await sb_get("rank_history", params)

@app.post("/api/rank/history")
async def save_rank_history(data: dict):
    data["checked_at"] = datetime.now().isoformat()
    result = await sb_post("rank_history", data)
    return result[0] if isinstance(result, list) else result

# ===== SALES (스프레드시트) =====
@app.get("/api/sales")
async def get_sales(month: str = ""):
    params = "order=date.desc"
    if month:
        start = f"{month}-01"
        end_month = int(month.split("-")[1])
        end_year = int(month.split("-")[0])
        if end_month == 12:
            end = f"{end_year + 1}-01-01"
        else:
            end = f"{end_year}-{end_month + 1:02d}-01"
        params += f"&date=gte.{start}&date=lt.{end}"
    return await sb_get("sales", params)

@app.post("/api/sales")
async def create_sale(req: SalesRecord):
    data = req.dict()
    data["created_at"] = datetime.now().isoformat()
    result = await sb_post("sales", data)
    return result[0] if isinstance(result, list) else result

@app.patch("/api/sales/{sid}")
async def update_sale(sid: int, data: dict):
    data["updated_at"] = datetime.now().isoformat()
    result = await sb_patch("sales", f"id=eq.{sid}", data)
    return result[0] if isinstance(result, list) else result

@app.delete("/api/sales/{sid}")
async def delete_sale(sid: int):
    return await sb_delete("sales", f"id=eq.{sid}")

# ===== NOTICES (공지사항) =====
@app.get("/api/notices")
async def get_notices():
    return await sb_get("notices", "order=is_pinned.desc,created_at.desc")

@app.post("/api/notices")
async def create_notice(req: NoticeCreate):
    data = req.dict()
    data["created_at"] = datetime.now().isoformat()
    data["author"] = "관리자"
    result = await sb_post("notices", data)
    return result[0] if isinstance(result, list) else result

@app.patch("/api/notices/{nid}")
async def update_notice(nid: int, req: NoticeUpdate):
    data = {k: v for k, v in req.dict().items() if v is not None}
    data["updated_at"] = datetime.now().isoformat()
    result = await sb_patch("notices", f"id=eq.{nid}", data)
    return result[0] if isinstance(result, list) else result

@app.delete("/api/notices/{nid}")
async def delete_notice(nid: int):
    return await sb_delete("notices", f"id=eq.{nid}")

# ===== TEAM (팀 관리) =====
@app.get("/api/team")
async def get_team():
    return await sb_get("users", "select=id,user_id,name,position,role,level,created_at&order=level.desc,created_at.asc")

@app.post("/api/team")
async def create_member(req: TeamMemberCreate):
    existing = await sb_get("users", f"user_id=eq.{req.user_id}")
    if existing:
        raise HTTPException(status_code=409, detail="이미 존재하는 아이디입니다")
    data = {
        "user_id": req.user_id,
        "password_hash": hash_pw(req.password),
        "name": req.name,
        "position": req.position,
        "role": req.role,
        "level": req.level,
        "created_at": datetime.now().isoformat()
    }
    result = await sb_post("users", data)
    return result[0] if isinstance(result, list) else result

@app.patch("/api/team/{uid}")
async def update_member(uid: int, req: TeamMemberUpdate):
    data = {k: v for k, v in req.dict().items() if v is not None}
    result = await sb_patch("users", f"id=eq.{uid}", data)
    return result[0] if isinstance(result, list) else result

@app.delete("/api/team/{uid}")
async def delete_member(uid: int):
    return await sb_delete("users", f"id=eq.{uid}")

# ===== SELLER DB (영업 DB 추출) =====
@app.get("/api/sellerdb/search")
async def search_seller(keyword: str = ""):
    if not keyword:
        raise HTTPException(status_code=400, detail="키워드를 입력하세요")
    proxy = get_proxy()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://m.search.naver.com/"
    }
    results = []
    try:
        for start in [1, 16, 31]:
            url = f"https://m.search.naver.com/search.naver?where=m_local&query={keyword}&start={start}"
            async with httpx.AsyncClient(proxy=proxy, timeout=15, verify=False) as c:
                r = await c.get(url, headers=headers)
                text = r.text
            names = re.findall(r'"name":"([^"]+)"', text)
            addresses = re.findall(r'"roadAddress":"([^"]+)"', text)
            phones = re.findall(r'"phone":"([^"]*)"', text)
            for i in range(len(names)):
                results.append({
                    "name": names[i],
                    "address": addresses[i] if i < len(addresses) else "",
                    "phone": phones[i] if i < len(phones) else "",
                })
            time.sleep(0.3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 에러: {str(e)}")
    return {"keyword": keyword, "count": len(results), "results": results}

# ===== PROXY STATUS =====
@app.get("/api/proxy/status")
async def proxy_status():
    proxy = get_proxy()
    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=10, verify=False) as c:
            r = await c.get("https://httpbin.org/ip")
            return {"status": "ok", "proxy_ip": r.json().get("origin", "unknown")}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ===== DASHBOARD STATS =====
@app.get("/api/dashboard/stats")
async def dashboard_stats():
    try:
        campaigns = await sb_get("campaigns", "select=id,status")
        users = await sb_get("users", "select=id")
        notices = await sb_get("notices", "select=id")
        sales = await sb_get("sales", "select=amount,profit")
        total_amount = sum(s.get("amount", 0) for s in sales) if sales else 0
        total_profit = sum(s.get("profit", 0) for s in sales) if sales else 0
        active_campaigns = len([c for c in campaigns if c.get("status") == "active"]) if campaigns else 0
        return {
            "total_campaigns": len(campaigns) if campaigns else 0,
            "active_campaigns": active_campaigns,
            "total_members": len(users) if users else 0,
            "total_notices": len(notices) if notices else 0,
            "total_sales_amount": total_amount,
            "total_profit": total_profit,
        }
    except Exception:
        return {
            "total_campaigns": 0, "active_campaigns": 0,
            "total_members": 0, "total_notices": 0,
            "total_sales_amount": 0, "total_profit": 0,
        }

# ===== ERROR HANDLER =====
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )
