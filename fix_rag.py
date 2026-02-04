import requests
import sys

BASE_URL = "http://localhost:8002"

def run():
    # 1. Purge
    print("Purging database...")
    try:
        r = requests.delete(f"{BASE_URL}/purge")
        print(f"Purge status: {r.status_code}")
        print(r.text)
    except Exception as e:
        print(f"Purge failed: {e}")
        return

    # 2. Ingest
    print("\nIngesting test data...")
    try:
        r = requests.post(f"{BASE_URL}/ingest", params={"text": "Hello world, this is a test of the RAG system.", "source": "test_script"})
        print(f"Ingest status: {r.status_code}")
        print(r.text)
    except Exception as e:
        print(f"Ingest failed: {e}")
        return

    # 3. Ask
    print("\nQuerying 'Hello'...")
    try:
        r = requests.get(f"{BASE_URL}/ask", params={"query": "Hello"})
        print(f"Query status: {r.status_code}")
        print(r.text)
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    run()
