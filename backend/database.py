import psycopg2
import psycopg2.extras
import os
import bcrypt

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ── SETUP ────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mandanten (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS mieter (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            name TEXT NOT NULL,
            wohnung TEXT,
            kontakt TEXT,
            mietbeginn TEXT,
            mietende TEXT,
            status TEXT DEFAULT 'aktiv',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS zahlungen (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            mieter TEXT NOT NULL,
            wohnung TEXT,
            betrag NUMERIC,
            monat TEXT,
            datum TEXT,
            status TEXT DEFAULT 'offen',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS reparaturen (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            wohnung TEXT,
            beschreibung TEXT NOT NULL,
            datum TEXT,
            prioritaet TEXT DEFAULT 'mittel',
            status TEXT DEFAULT 'offen',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS wohnungen (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            adresse TEXT,
            einheit TEXT,
            groesse NUMERIC,
            miete NUMERIC,
            mieter TEXT,
            status TEXT DEFAULT 'leer',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS dokumente (
            id SERIAL PRIMARY KEY,
            mandant_id INTEGER REFERENCES mandanten(id),
            filename TEXT NOT NULL,
            dokumenttyp TEXT,
            zusammenfassung TEXT,
            counts JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.close()
    print("✅ Datenbank initialisiert")

def seed_demo():
    """Demo-Account anlegen falls noch nicht vorhanden"""
    conn = get_conn()
    cur = dict_cursor(conn)

    cur.execute("SELECT id FROM mandanten WHERE name = 'Demo Hausverwaltung'")
    if cur.fetchone():
        conn.close()
        return

    cur.execute("INSERT INTO mandanten (name) VALUES ('Demo Hausverwaltung') RETURNING id")
    mandant_id = cur.fetchone()["id"]

    pw_hash = bcrypt.hashpw("demo1234".encode(), bcrypt.gensalt()).decode()
    cur.execute("""
        INSERT INTO users (mandant_id, email, password_hash, name)
        VALUES (%s, 'muster@hausverwaltung.de', %s, 'Muster Hausverwaltung')
    """, (mandant_id, pw_hash))

    conn.close()
    print("✅ Demo-Account angelegt: muster@hausverwaltung.de / demo1234")

# ── AUTH ─────────────────────────────────────────────────────────

def get_user_by_email(email):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# ── MIETER ───────────────────────────────────────────────────────

def get_mieter(mandant_id, search=None, wohnung=None, status=None):
    conn = get_conn()
    cur = dict_cursor(conn)
    q = "SELECT * FROM mieter WHERE mandant_id = %s"
    params = [mandant_id]
    if search:
        q += " AND (LOWER(name) LIKE %s OR LOWER(wohnung) LIKE %s)"
        s = f"%{search.lower()}%"
        params += [s, s]
    if wohnung:
        q += " AND wohnung = %s"
        params.append(wohnung)
    if status:
        q += " AND status = %s"
        params.append(status)
    q += " ORDER BY created_at DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_mieter(mandant_id, data):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO mieter (mandant_id, name, wohnung, kontakt, mietbeginn, mietende, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
    """, (mandant_id, data.get('name',''), data.get('wohnung'), data.get('kontakt'),
          data.get('mietbeginn'), data.get('mietende'), data.get('status','aktiv')))
    row = cur.fetchone()
    conn.close()
    return dict(row)

def delete_mieter(mandant_id, mieter_id):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("DELETE FROM mieter WHERE id = %s AND mandant_id = %s", (mieter_id, mandant_id))
    conn.close()

# ── ZAHLUNGEN ────────────────────────────────────────────────────

def get_zahlungen(mandant_id, search=None, monat=None, status=None):
    conn = get_conn()
    cur = dict_cursor(conn)
    q = "SELECT * FROM zahlungen WHERE mandant_id = %s"
    params = [mandant_id]
    if search:
        q += " AND (LOWER(mieter) LIKE %s OR LOWER(wohnung) LIKE %s)"
        s = f"%{search.lower()}%"
        params += [s, s]
    if monat:
        q += " AND monat = %s"
        params.append(monat)
    if status:
        q += " AND status = %s"
        params.append(status)
    q += " ORDER BY created_at DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_zahlung(mandant_id, data):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO zahlungen (mandant_id, mieter, wohnung, betrag, monat, datum, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
    """, (mandant_id, data.get('mieter',''), data.get('wohnung'), data.get('betrag'),
          data.get('monat'), data.get('datum'), data.get('status','offen')))
    row = cur.fetchone()
    conn.close()
    return dict(row)

# ── REPARATUREN ──────────────────────────────────────────────────

def get_reparaturen(mandant_id, search=None, status=None, prioritaet=None):
    conn = get_conn()
    cur = dict_cursor(conn)
    q = "SELECT * FROM reparaturen WHERE mandant_id = %s"
    params = [mandant_id]
    if search:
        q += " AND (LOWER(beschreibung) LIKE %s OR LOWER(wohnung) LIKE %s)"
        s = f"%{search.lower()}%"
        params += [s, s]
    if status:
        q += " AND LOWER(status) = %s"
        params.append(status.lower())
    if prioritaet:
        q += " AND LOWER(prioritaet) = %s"
        params.append(prioritaet.lower())
    q += " ORDER BY created_at DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_reparatur(mandant_id, data):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO reparaturen (mandant_id, wohnung, beschreibung, datum, prioritaet, status)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
    """, (mandant_id, data.get('wohnung'), data.get('beschreibung',''),
          data.get('datum'), data.get('prioritaet','mittel'), data.get('status','offen')))
    row = cur.fetchone()
    conn.close()
    return dict(row)

def update_reparatur(mandant_id, rep_id, data):
    conn = get_conn()
    cur = dict_cursor(conn)
    if 'status' in data:
        cur.execute("UPDATE reparaturen SET status = %s WHERE id = %s AND mandant_id = %s",
                    (data['status'], rep_id, mandant_id))
    if 'prioritaet' in data:
        cur.execute("UPDATE reparaturen SET prioritaet = %s WHERE id = %s AND mandant_id = %s",
                    (data['prioritaet'], rep_id, mandant_id))
    conn.close()

# ── WOHNUNGEN ────────────────────────────────────────────────────

def get_wohnungen(mandant_id, search=None, status=None):
    conn = get_conn()
    cur = dict_cursor(conn)
    q = "SELECT * FROM wohnungen WHERE mandant_id = %s"
    params = [mandant_id]
    if search:
        q += " AND LOWER(adresse) LIKE %s"
        params.append(f"%{search.lower()}%")
    if status:
        q += " AND LOWER(status) = %s"
        params.append(status.lower())
    q += " ORDER BY adresse, einheit"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_wohnung(mandant_id, data):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("""
        INSERT INTO wohnungen (mandant_id, adresse, einheit, groesse, miete, mieter, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
    """, (mandant_id, data.get('adresse'), data.get('einheit'), data.get('groesse'),
          data.get('miete'), data.get('mieter'), data.get('status','leer')))
    row = cur.fetchone()
    conn.close()
    return dict(row)

# ── STATS ────────────────────────────────────────────────────────

def get_stats(mandant_id):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT COUNT(*) as c FROM wohnungen WHERE mandant_id = %s", (mandant_id,))
    einheiten = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM mieter WHERE mandant_id = %s AND status = 'aktiv'", (mandant_id,))
    mieter = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM zahlungen WHERE mandant_id = %s AND status != 'bezahlt'", (mandant_id,))
    zahlungen_offen = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM reparaturen WHERE mandant_id = %s AND status != 'erledigt'", (mandant_id,))
    reparaturen_offen = cur.fetchone()["c"]
    conn.close()
    return {
        "einheiten": einheiten,
        "mieter": mieter,
        "zahlungen_offen": zahlungen_offen,
        "reparaturen_offen": reparaturen_offen
    }

# ── DOKUMENTE ────────────────────────────────────────────────────

def log_dokument(mandant_id, filename, dokumenttyp, zusammenfassung, counts):
    conn = get_conn()
    cur = dict_cursor(conn)
    import json
    cur.execute("""
        INSERT INTO dokumente (mandant_id, filename, dokumenttyp, zusammenfassung, counts)
        VALUES (%s, %s, %s, %s, %s)
    """, (mandant_id, filename, dokumenttyp, zusammenfassung, json.dumps(counts)))
    conn.close()

def get_dokumente(mandant_id):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT * FROM dokumente WHERE mandant_id = %s ORDER BY created_at DESC", (mandant_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── STARTUP ──────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    seed_demo()
