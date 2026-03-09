from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import database as db
import jwt
import bcrypt
import datetime
import io
import json
import os

app = FastAPI(title="ImmoBase API", version="1.0.0")

# DB beim Start initialisieren
try:
    db.init_db()
    db.seed_demo()
    print("✅ Datenbank bereit")
except Exception as e:
    print(f"⚠️ DB Init: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
JWT_SECRET = os.environ.get("JWT_SECRET", "immobase-secret-change-in-production")

# ── AUTH ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token abgelaufen")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Ungültiger Token")

@app.post("/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_email(req.email)
    if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="E-Mail oder Passwort falsch")
    token = jwt.encode({
        "user_id": user["id"],
        "mandant_id": user["mandant_id"],
        "email": user["email"],
        "name": user["name"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }, JWT_SECRET, algorithm="HS256")
    return {"token": token, "name": user["name"], "email": user["email"]}

@app.get("/auth/me")
def me(payload = Depends(verify_token)):
    return payload

# ── MIETER ──────────────────────────────────────────────────────

class MieterCreate(BaseModel):
    name: str
    wohnung: Optional[str] = None
    kontakt: Optional[str] = None
    mietbeginn: Optional[str] = None
    mietende: Optional[str] = None
    status: Optional[str] = "aktiv"

@app.get("/mieter")
def get_mieter(
    search: Optional[str] = None,
    wohnung: Optional[str] = None,
    status: Optional[str] = None,
    payload = Depends(verify_token)
):
    return db.get_mieter(payload["mandant_id"], search=search, wohnung=wohnung, status=status)

@app.post("/mieter")
def create_mieter(mieter: MieterCreate, payload = Depends(verify_token)):
    return db.create_mieter(payload["mandant_id"], mieter.dict())

@app.delete("/mieter/{mieter_id}")
def delete_mieter(mieter_id: int, payload = Depends(verify_token)):
    db.delete_mieter(payload["mandant_id"], mieter_id)
    return {"ok": True}

# ── ZAHLUNGEN ───────────────────────────────────────────────────

class ZahlungCreate(BaseModel):
    mieter: str
    wohnung: Optional[str] = None
    betrag: Optional[float] = None
    monat: Optional[str] = None
    datum: Optional[str] = None
    status: Optional[str] = "offen"

@app.get("/zahlungen")
def get_zahlungen(
    search: Optional[str] = None,
    monat: Optional[str] = None,
    status: Optional[str] = None,
    payload = Depends(verify_token)
):
    return db.get_zahlungen(payload["mandant_id"], search=search, monat=monat, status=status)

@app.post("/zahlungen")
def create_zahlung(zahlung: ZahlungCreate, payload = Depends(verify_token)):
    return db.create_zahlung(payload["mandant_id"], zahlung.dict())

# ── REPARATUREN ─────────────────────────────────────────────────

class ReparaturCreate(BaseModel):
    wohnung: Optional[str] = None
    beschreibung: str
    datum: Optional[str] = None
    prioritaet: Optional[str] = "mittel"
    status: Optional[str] = "offen"

@app.get("/reparaturen")
def get_reparaturen(
    search: Optional[str] = None,
    status: Optional[str] = None,
    prioritaet: Optional[str] = None,
    payload = Depends(verify_token)
):
    return db.get_reparaturen(payload["mandant_id"], search=search, status=status, prioritaet=prioritaet)

@app.post("/reparaturen")
def create_reparatur(rep: ReparaturCreate, payload = Depends(verify_token)):
    return db.create_reparatur(payload["mandant_id"], rep.dict())

@app.patch("/reparaturen/{rep_id}")
def update_reparatur(rep_id: int, data: dict, payload = Depends(verify_token)):
    db.update_reparatur(payload["mandant_id"], rep_id, data)
    return {"ok": True}

# ── WOHNUNGEN ───────────────────────────────────────────────────

class WohnungCreate(BaseModel):
    adresse: Optional[str] = None
    einheit: Optional[str] = None
    groesse: Optional[float] = None
    miete: Optional[float] = None
    mieter: Optional[str] = None
    status: Optional[str] = "leer"

@app.get("/wohnungen")
def get_wohnungen(
    search: Optional[str] = None,
    status: Optional[str] = None,
    payload = Depends(verify_token)
):
    return db.get_wohnungen(payload["mandant_id"], search=search, status=status)

@app.post("/wohnungen")
def create_wohnung(wohnung: WohnungCreate, payload = Depends(verify_token)):
    return db.create_wohnung(payload["mandant_id"], wohnung.dict())

# ── STATS ───────────────────────────────────────────────────────

@app.get("/stats")
def get_stats(payload = Depends(verify_token)):
    return db.get_stats(payload["mandant_id"])

# ── DOKUMENTE / IMPORT ──────────────────────────────────────────

class ImportData(BaseModel):
    filename: str
    dokumenttyp: str
    zusammenfassung: Optional[str] = None
    mieter: Optional[List[dict]] = []
    zahlungen: Optional[List[dict]] = []
    reparaturen: Optional[List[dict]] = []
    wohnungen: Optional[List[dict]] = []

@app.post("/import")
def import_data(data: ImportData, payload = Depends(verify_token)):
    mid = payload["mandant_id"]
    counts = {"mieter": 0, "zahlungen": 0, "reparaturen": 0, "wohnungen": 0}

    for m in (data.mieter or []):
        db.create_mieter(mid, m)
        counts["mieter"] += 1
    for z in (data.zahlungen or []):
        db.create_zahlung(mid, z)
        counts["zahlungen"] += 1
    for r in (data.reparaturen or []):
        db.create_reparatur(mid, r)
        counts["reparaturen"] += 1
    for w in (data.wohnungen or []):
        db.create_wohnung(mid, w)
        counts["wohnungen"] += 1

    db.log_dokument(mid, data.filename, data.dokumenttyp, data.zusammenfassung, counts)
    return {"ok": True, "counts": counts}

@app.get("/dokumente")
def get_dokumente(payload = Depends(verify_token)):
    return db.get_dokumente(payload["mandant_id"])

# ── PDF EXPORT ──────────────────────────────────────────────────

@app.get("/export/pdf/{report_type}")
def export_pdf(report_type: str, payload = Depends(verify_token)):
    # PDF export handled in frontend
    raise HTTPException(status_code=501, detail="PDF export wird im Browser generiert")

@app.get("/")
def root():
    return {"status": "ImmoBase API läuft", "version": "1.0.0"}
