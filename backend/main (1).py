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
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

app = FastAPI(title="ImmoBase API", version="1.0.0")

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
    mid = payload["mandant_id"]
    mandant_name = payload.get("name", "Hausverwaltung")
    buf = io.BytesIO()

    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', fontSize=18, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a3a5c'), spaceAfter=4)
    sub_style = ParagraphStyle('sub', fontSize=10, fontName='Helvetica',
        textColor=colors.HexColor('#64748b'), spaceAfter=20)
    head_style = ParagraphStyle('head', fontSize=12, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1e4d8c'), spaceBefore=16, spaceAfter=8)

    BLUE = colors.HexColor('#1e4d8c')
    LIGHT = colors.HexColor('#dbeafe')
    GREY = colors.HexColor('#f7f8fa')

    elements = []
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    def make_header(title, subtitle):
        elements.append(Paragraph(f"ImmoBase — {title}", title_style))
        elements.append(Paragraph(f"{mandant_name}  ·  Erstellt am {now}", sub_style))

    def styled_table(headers, rows, col_widths):
        data = [headers] + rows
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), BLUE),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GREY]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e5ea')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    if report_type == "mieter":
        make_header("Mieterliste", "")
        data = db.get_mieter(mid)
        elements.append(Paragraph(f"Gesamt: {len(data)} Mieter", sub_style))
        rows = [[d.get('name',''), d.get('wohnung',''), d.get('kontakt',''),
                 d.get('mietbeginn',''), d.get('status','')] for d in data]
        elements.append(styled_table(
            ['Name', 'Wohnung', 'Kontakt', 'Mietbeginn', 'Status'],
            rows or [['—','—','—','—','—']],
            [4.5*cm, 4.5*cm, 4*cm, 3*cm, 2*cm]
        ))

    elif report_type == "zahlungen":
        make_header("Zahlungsübersicht", "")
        data = db.get_zahlungen(mid)
        offen = sum(1 for d in data if d.get('status') != 'bezahlt')
        elements.append(Paragraph(f"Gesamt: {len(data)}  ·  Offen: {offen}", sub_style))
        rows = [[d.get('mieter',''), d.get('wohnung',''),
                 f"{d.get('betrag','')} €" if d.get('betrag') else '—',
                 d.get('monat',''), d.get('status','')] for d in data]
        elements.append(styled_table(
            ['Mieter', 'Wohnung', 'Betrag', 'Monat', 'Status'],
            rows or [['—','—','—','—','—']],
            [4*cm, 4*cm, 2.5*cm, 3.5*cm, 2.5*cm]
        ))

    elif report_type == "reparaturen":
        make_header("Reparatur- & Wartungsübersicht", "")
        data = db.get_reparaturen(mid)
        offen = sum(1 for d in data if d.get('status') == 'offen')
        elements.append(Paragraph(f"Gesamt: {len(data)}  ·  Offen: {offen}", sub_style))
        rows = [[d.get('wohnung',''), d.get('beschreibung',''),
                 d.get('datum',''), d.get('prioritaet',''), d.get('status','')] for d in data]
        elements.append(styled_table(
            ['Wohnung', 'Beschreibung', 'Datum', 'Priorität', 'Status'],
            rows or [['—','—','—','—','—']],
            [3.5*cm, 6*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        ))

    elif report_type == "leerstand":
        make_header("Wohnungsübersicht & Leerstand", "")
        data = db.get_wohnungen(mid)
        leer = sum(1 for d in data if d.get('status') == 'leer')
        elements.append(Paragraph(f"Gesamt: {len(data)}  ·  Leerstand: {leer}", sub_style))
        rows = [[d.get('adresse',''), d.get('einheit',''),
                 f"{d.get('groesse','')} m²" if d.get('groesse') else '—',
                 f"{d.get('miete','')} €" if d.get('miete') else '—',
                 d.get('mieter','—'), d.get('status','')] for d in data]
        elements.append(styled_table(
            ['Adresse', 'Einheit', 'Größe', 'Kaltmiete', 'Mieter', 'Status'],
            rows or [['—','—','—','—','—','—']],
            [4*cm, 2.5*cm, 2*cm, 2.5*cm, 3.5*cm, 2.5*cm]
        ))

    elif report_type == "gesamt":
        make_header("Gesamtbericht", "")
        stats = db.get_stats(mid)
        elements.append(Paragraph(f"Einheiten: {stats['einheiten']}  ·  Mieter: {stats['mieter']}  ·  Offene Zahlungen: {stats['zahlungen_offen']}  ·  Offene Reparaturen: {stats['reparaturen_offen']}", sub_style))

        elements.append(Paragraph("Mieter", head_style))
        mieter_data = db.get_mieter(mid)
        rows = [[d.get('name',''), d.get('wohnung',''), d.get('status','')] for d in mieter_data]
        elements.append(styled_table(['Name','Wohnung','Status'], rows or [['—','—','—']], [6*cm,8*cm,3*cm]))

        elements.append(Paragraph("Offene Zahlungen", head_style))
        zahl_data = [d for d in db.get_zahlungen(mid) if d.get('status') != 'bezahlt']
        rows = [[d.get('mieter',''), d.get('wohnung',''), f"{d.get('betrag','')} €", d.get('status','')] for d in zahl_data]
        elements.append(styled_table(['Mieter','Wohnung','Betrag','Status'], rows or [['—','—','—','—']], [5*cm,5*cm,3*cm,4*cm]))

        elements.append(Paragraph("Offene Reparaturen", head_style))
        rep_data = [d for d in db.get_reparaturen(mid) if d.get('status') != 'erledigt']
        rows = [[d.get('wohnung',''), d.get('beschreibung',''), d.get('prioritaet','')] for d in rep_data]
        elements.append(styled_table(['Wohnung','Beschreibung','Priorität'], rows or [['—','—','—']], [4*cm,10*cm,3*cm]))

    else:
        raise HTTPException(status_code=400, detail="Unbekannter Report-Typ")

    doc.build(elements)
    buf.seek(0)
    filename = f"immobase_{report_type}_{datetime.date.today()}.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/")
def root():
    return {"status": "ImmoBase API läuft", "version": "1.0.0"}
