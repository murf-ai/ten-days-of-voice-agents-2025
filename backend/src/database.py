import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tutor_state", "mastery.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS mastery (
            concept_id TEXT PRIMARY KEY,
            times_explained INTEGER DEFAULT 0,
            times_quizzed INTEGER DEFAULT 0,
            times_taught_back INTEGER DEFAULT 0,
            last_score INTEGER,
            avg_score REAL
        )
    """)
    conn.commit()
    conn.close()


def save_mastery(concept_id, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO mastery (concept_id, times_explained, times_quizzed, times_taught_back, last_score, avg_score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(concept_id) DO UPDATE SET
            times_explained=excluded.times_explained,
            times_quizzed=excluded.times_quizzed,
            times_taught_back=excluded.times_taught_back,
            last_score=excluded.last_score,
            avg_score=excluded.avg_score
    """, (
        concept_id,
        data.get("times_explained", 0),
        data.get("times_quizzed", 0),
        data.get("times_taught_back", 0),
        data.get("last_score"),
        data.get("avg_score")
    ))

    conn.commit()
    conn.close()


def load_mastery():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute("SELECT * FROM mastery").fetchall()
    conn.close()

    mastery = {}
    for row in rows:
        mastery[row[0]] = {
            "times_explained": row[1],
            "times_quizzed": row[2],
            "times_taught_back": row[3],
            "last_score": row[4],
            "avg_score": row[5]
        }
    return mastery
