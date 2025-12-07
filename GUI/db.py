import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "requests.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        data_json TEXT NOT NULL,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

def save_request(nombre, contacts_list):
    """
    Guarda en formato:
    {
        "nombre": "...",
        "contacts": [
            {"email": "...", "phone": "...", "name": "...", "role": "...", "url": "..."},
        ]
    }
    """
    payload = {
        "nombre": nombre,
        "contacts": contacts_list
    }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO requests (nombre, data_json)
        VALUES (?, ?)
    """, (nombre, json.dumps(payload, ensure_ascii=False)))

    conn.commit()
    conn.close()

def get_all_requests():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, data_json, date FROM requests ORDER BY id DESC")
    data = cursor.fetchall()
    conn.close()
    return data

def get_request_by_id(req_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, data_json, date FROM requests WHERE id = ?", (req_id,))
    data = cursor.fetchone()
    conn.close()
    return data

def update_request(req_id, nombre, contacts_list):
    payload = {
        "nombre": nombre,
        "contacts": contacts_list
    }

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE requests
        SET nombre = ?, data_json = ?
        WHERE id = ?
    """, (nombre, json.dumps(payload, ensure_ascii=False), req_id))

    conn.commit()
    conn.close()

def delete_request(req_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()
