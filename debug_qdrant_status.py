import requests
import json

QDRANT_URL = "http://localhost:6333"

def check_collection():
    try:
        # List collections
        r = requests.get(f"{QDRANT_URL}/collections")
        if r.status_code != 200:
            print(f"Error listing collections: {r.text}")
            return
        
        collections = r.json().get('result', {}).get('collections', [])
        print(f"Found collections: {[c['name'] for c in collections]}")
        
        for c in collections:
            name = c['name']
            r = requests.get(f"{QDRANT_URL}/collections/{name}")
            if r.status_code == 200:
                info = r.json().get('result', {})
                config = info.get('config', {}).get('params', {}).get('vectors', {})
                print(f"Collection '{name}':")
                print(f"  - Status: {info.get('status')}")
                print(f"  - Vector Params: {config}")
                print(f"  - Points count: {info.get('points_count')}")
            else:
                print(f"Error getting info for {name}: {r.text}")

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    check_collection()
