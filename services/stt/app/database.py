import sqlite3
import os

DB_PATH = "/app/db/stt_config.db" if os.path.exists("/app/db") else "stt_config.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de configuración
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY,
            language TEXT,
            beam_size INTEGER
        )
    ''')
    
    # Insertar valores por defecto si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM config')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO config (language, beam_size)
            VALUES (?, ?)
        ''', (
            "es",  # Default language: Spanish
            5      # Default beam_size
        ))
    
    conn.commit()
    conn.close()

def get_config():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM config WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_config(data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fields = []
    values = []
    for key, value in data.items():
        if key in ['language', 'beam_size']:
            fields.append(f"{key} = ?")
            values.append(value)
    
    if fields:
        query = f"UPDATE config SET {', '.join(fields)} WHERE id = 1"
        cursor.execute(query, values)
        conn.commit()
    
    conn.close()
