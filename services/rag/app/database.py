import sqlite3
import os

DB_PATH = "/app/db/rag_config.db" if os.path.exists("/app/db") else "rag_config.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de configuración
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY,
            persona TEXT,
            system_instructions TEXT,
            rag_k INTEGER,
            rag_max_context INTEGER,
            rag_temperature REAL,
            rag_max_length INTEGER,
            ollama_timeout INTEGER
        )
    ''')
    
    # Insertar valores por defecto si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM config')
    if cursor.fetchone()[0] == 0:
        default_instructions = (
            "INSTRUCCIONES CRÍTICAS:\n"
            "1. SOLO puedes responder usando la información del CONTEXTO proporcionado.\n"
            "2. Si la pregunta NO puede responderse con el CONTEXTO, debes decir: 'No tengo información sobre eso en mi base de conocimientos.'\n"
            "3. NUNCA inventes, supongas o uses conocimiento externo.\n"
            "4. Usa tu personalidad ÚNICAMENTE para dar formato y tono a la respuesta, NO para añadir información."
        )
        cursor.execute('''
            INSERT INTO config (persona, system_instructions, rag_k, rag_max_context, rag_temperature, rag_max_length, ollama_timeout)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Eres un asistente de voz. Usa el contexto para responder de forma breve y clara.",
            default_instructions,
            4,
            6000,
            0.1,
            1024,
            300
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
        if key in ['persona', 'system_instructions', 'rag_k', 'rag_max_context', 'rag_temperature', 'rag_max_length', 'ollama_timeout']:
            fields.append(f"{key} = ?")
            values.append(value)
    
    if fields:
        query = f"UPDATE config SET {', '.join(fields)} WHERE id = 1"
        cursor.execute(query, values)
        conn.commit()
    
    conn.close()
