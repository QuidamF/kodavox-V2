import sys
import os

# Permitir importar la carpeta orchestrator desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.services.rag_chroma import ChromaRAGService

def main():
    print("--- Iniciando prueba de RAG con ChromaDB ---")
    rag = ChromaRAGService()

    col_name = "test_collection"
    print(f"\n1. Creando colección '{col_name}'...")
    rag.create_collection(col_name)

    print("\n2. Listando colecciones actuales:")
    print(rag.list_collections())

    print("\n3. Añadiendo un documento de texto de prueba...")
    test_content = b"KodaVox es un asistente virtual de voz impulsado por modelos de lenguaje y RAG. Fue creado en el a\xc3\xb1o 2024 para revolucionar la interacci\xc3\xb3n humano-computadora."
    rag.add_document(col_name, "test_file.txt", test_content)

    print("\n4. Consultando el contexto...")
    query = "\xc2\xbfQu\xc3\xa9 es KodaVox?"
    print(f"Pregunta: {query}")
    context = rag.get_relevant_context(col_name, query, top_k=1)
    
    print("\n--- Contexto Recuperado ---")
    print(context)
    print("---------------------------")

    print("\n5. Limpiando colección de prueba...")
    rag.delete_collection(col_name)

    print("\nPrueba completada exitosamente.")

if __name__ == "__main__":
    main()
