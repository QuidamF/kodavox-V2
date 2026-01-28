from qdrant_client import QdrantClient
import sys

try:
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections()
    print(f"Collections: {collections}")
    for col in collections.collections:
        config = client.get_collection(col.name)
        print(f"--- Configuration for {col.name} ---")
        print(config)
except Exception as e:
    print(f"Error: {e}")
