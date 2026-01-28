import sqlite3
import os

DB_PATH = "/app/db/tts_config.db" if os.path.exists("/app/db") else "tts_config.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de configuración TTS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tts_config (
            id INTEGER PRIMARY KEY,
            voice_sample TEXT,
            language TEXT
        )
    ''')
    
    # Insertar valores por defecto si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM tts_config')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO tts_config (voice_sample, language)
            VALUES (?, ?)
        ''', ("Karla.wav", "es"))
    
    conn.commit()
    conn.close()

def get_tts_config():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tts_config WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_tts_config(data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fields = []
    values = []
    for key, value in data.items():
        if key in ['voice_sample', 'language']:
            fields.append(f"{key} = ?")
            values.append(value)
    
    if fields:
        query = f"UPDATE tts_config SET {', '.join(fields)} WHERE id = 1"
        cursor.execute(query, values)
        conn.commit()
    
    conn.close()
