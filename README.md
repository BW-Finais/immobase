# 🏢 ImmoBase — Hausverwaltungs-Dashboard

KI-gestütztes Dashboard für Hausverwaltungen. PDFs hochladen → KI liest aus → Daten in Datenbank → Dashboard.

---

## 📁 Projektstruktur

```
immobase/
├── frontend/
│   └── index.html        ← Das komplette Frontend (eine Datei)
└── backend/
    ├── main.py            ← FastAPI Server (alle API-Endpunkte)
    ├── database.py        ← PostgreSQL Datenbankschicht
    ├── startup.py         ← DB initialisieren beim ersten Start
    ├── requirements.txt   ← Python-Abhängigkeiten
    └── Procfile           ← Railway: wie der Server gestartet wird
```

---

## 🚀 Schritt-für-Schritt Deployment

### Schritt 1 — GitHub Repo anlegen

```bash
# Terminal öffnen im Projektordner
cd immobase
git init
git add .
git commit -m "Initial commit"
```

Dann auf **github.com**:
1. Oben rechts auf **+** → **New repository**
2. Name: `immobase`
3. Visibility: **Public** (für GitHub Pages nötig) oder Private
4. **Create repository** klicken

```bash
# Die zwei Befehle von GitHub kopieren und ausführen, z.B.:
git remote add origin https://github.com/DEINNAME/immobase.git
git push -u origin main
```

---

### Schritt 2 — Backend auf Railway deployen

1. Gehe auf **[railway.app](https://railway.app)** → **Login with GitHub**
2. Klicke **New Project** → **Deploy from GitHub Repo**
3. Wähle dein `immobase` Repository aus
4. Railway fragt nach dem Root-Verzeichnis → **`backend`** eingeben
5. Klicke auf **Add Plugin** → **PostgreSQL** hinzufügen

Railway erkennt die `Procfile` automatisch und started den Server.

**Umgebungsvariablen setzen** (in Railway → dein Service → Variables):
```
JWT_SECRET=irgendein-langer-geheimer-string-hier-eintragen
```
> Die `DATABASE_URL` wird von Railway **automatisch** gesetzt wenn du PostgreSQL hinzufügst.

Nach dem Deploy siehst du unter **Settings → Domains** deine URL:
```
https://immobase-production-xxxx.up.railway.app
```

---

### Schritt 3 — Frontend mit Backend verbinden

Öffne `frontend/index.html` und suche Zeile ~130:

```javascript
// VORHER:
const API = window.IMMOBASE_API || "https://DEINE-RAILWAY-URL.up.railway.app";

// NACHHER (deine echte Railway-URL eintragen):
const API = window.IMMOBASE_API || "https://immobase-production-xxxx.up.railway.app";
```

Dann committen und pushen:
```bash
git add frontend/index.html
git commit -m "Backend URL konfiguriert"
git push
```

---

### Schritt 4 — GitHub Pages aktivieren

1. GitHub Repo → **Settings** → linkes Menü: **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` — Folder: `/frontend`
4. **Save** klicken

Nach ~2 Minuten ist das Frontend live unter:
```
https://DEINNAME.github.io/immobase
```

Diese URL gibst du der Hausverwaltung. Das ist alles was sie braucht.

---

### Schritt 5 — Neue Hausverwaltung anlegen

Für jeden neuen Kunden legst du manuell einen Account an.
Verbinde dich mit der Railway-Datenbank über den integrierten Query-Editor:

```sql
-- 1. Neuen Mandanten anlegen
INSERT INTO mandanten (name) VALUES ('Mustermann Hausverwaltung GmbH') RETURNING id;

-- 2. User anlegen (Passwort-Hash erzeugen — siehe unten)
INSERT INTO users (mandant_id, email, password_hash, name)
VALUES (2, 'kunde@email.de', 'HASH_HIER', 'Mustermann HV');
```

**Passwort-Hash erzeugen** (einmalig, lokal ausführen):
```python
import bcrypt
pw = "sicheresPasswort123"
hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
print(hash)
```

---

## 🔑 Demo-Login

Nach dem ersten Start wird automatisch ein Demo-Account angelegt:
- **E-Mail:** `muster@hausverwaltung.de`
- **Passwort:** `demo1234`

---

## 📥 PDF Export

Im Dashboard oben rechts: **Export PDF ▾**
- Mieterliste
- Zahlungsübersicht
- Reparaturen
- Leerstandsliste
- Gesamtbericht

---

## 💰 Kosten

| Dienst | Plan | Kosten |
|---|---|---|
| GitHub | Free | 0 € |
| Railway | Hobby | ~5 $/Monat (dauerhaft laufend) |
| Railway | Trial | 0 € (500h/Monat) |

Für den Anfang reicht der **Trial** zum Testen. Für echte Kunden → Hobby Plan (~5 $/Monat).

---

## 🛠️ Lokale Entwicklung (optional)

```bash
# Backend lokal starten
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost/immobase"
export JWT_SECRET="local-dev-secret"
python startup.py        # DB initialisieren
uvicorn main:app --reload --port 8000
```

API-Dokumentation dann unter: `http://localhost:8000/docs`

---

## 📞 API Endpunkte

| Method | Pfad | Beschreibung |
|---|---|---|
| POST | `/auth/login` | Login |
| GET | `/stats` | Dashboard-Zahlen |
| GET/POST | `/mieter` | Mieterliste |
| GET/POST | `/zahlungen` | Zahlungen |
| GET/POST | `/reparaturen` | Reparaturen |
| PATCH | `/reparaturen/{id}` | Status ändern |
| GET/POST | `/wohnungen` | Wohnungsliste |
| POST | `/import` | KI-Daten importieren |
| GET | `/dokumente` | Upload-Historie |
| GET | `/export/pdf/{type}` | PDF generieren |
