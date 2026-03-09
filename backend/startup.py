import database as db
import bcrypt

if __name__ == "__main__":
    print("🚀 ImmoBase Startup...")
    db.init_db()

    # Demo account
    db.seed_demo()

    # Dein persönlicher Account
    import psycopg2
    import psycopg2.extras
    import os

    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Mandant anlegen falls nicht vorhanden
    cur.execute("SELECT id FROM mandanten WHERE name = 'Finais Hausverwaltung'")
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO mandanten (name) VALUES ('Finais Hausverwaltung') RETURNING id")
        mandant_id = cur.fetchone()["id"]
    else:
        mandant_id = row["id"]

    # User anlegen oder updaten
    pw_hash = bcrypt.hashpw("Immobase1".encode(), bcrypt.gensalt()).decode()
    cur.execute("SELECT id FROM users WHERE email = 'b.winkler@finais.de'")
    if cur.fetchone():
        cur.execute("UPDATE users SET password_hash = %s WHERE email = 'b.winkler@finais.de'", (pw_hash,))
        print("✅ Account aktualisiert: b.winkler@finais.de")
    else:
        cur.execute("""
            INSERT INTO users (mandant_id, email, password_hash, name)
            VALUES (%s, 'b.winkler@finais.de', %s, 'Benedikt Winkler')
        """, (mandant_id, pw_hash))
        print("✅ Account angelegt: b.winkler@finais.de")

    conn.close()
    print("✅ Bereit!")
