import sqlite3

# Migración: Agregar columna system_instructions a la tabla config existente
DB_PATH = "/app/db/rag_config.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Verificar si la columna ya existe
cursor.execute("PRAGMA table_info(config)")
columns = [row[1] for row in cursor.fetchall()]

if 'system_instructions' not in columns:
    print("Agregando columna system_instructions...")
    default_instructions = (
        "INSTRUCCIONES CRÍTICAS:\n"
        "1. SOLO puedes responder usando la información del CONTEXTO proporcionado.\n"
        "2. Si la pregunta NO puede responderse con el CONTEXTO, debes decir: 'No tengo información sobre eso en mi base de conocimientos.'\n"
        "3. NUNCA inventes, supongas o uses conocimiento externo.\n"
        "4. Usa tu personalidad ÚNICAMENTE para dar formato y tono a la respuesta, NO para añadir información."
    )
    
    cursor.execute("ALTER TABLE config ADD COLUMN system_instructions TEXT")
    cursor.execute("UPDATE config SET system_instructions = ? WHERE id = 1", (default_instructions,))
    conn.commit()
    print("Columna agregada exitosamente!")
else:
    print("La columna system_instructions ya existe.")

conn.close()
