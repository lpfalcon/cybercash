import os
import threading

from dotenv import load_dotenv

load_dotenv()
import requests

URL = os.getenv("URL")

def attack_worker(thread_id):
    # SIMULATION: A bot trying to exhaustion resources 
    # by requesting challenges repeatedly without solving them.
    print(f"[!] Bot {thread_id}: Requesting new challenge...")
    
    headers = {
        # Using the SAME fingerprint for all threads to trigger the AI volume alert
        "X-Device-Fingerprint": "target-fingerprint-001", 
        "X-CyberCash-Token": "Bearer 7ad22fc0dea6bcd514c57bd84a9973661e40c804d4d0c52bc4a038191b9fd32b"
    }
    
    try:
        # We send an empty JSON to trigger Phase 1 (Challenge Issuance)
        response = requests.post(URL, headers=headers, json={})
        
        print(f"[*] Bot {thread_id} Response: {response.status_code}")
        if response.status_code == 401:
            data = response.json()
            print(f"    -> Difficulty Level: {data.get('difficulty')} | Status: {data.get('system_status')}")
    except Exception as e:
        print(f"[X] Bot {thread_id} Error: {e}")

# Launching 20 simultaneous threads to overwhelm the 10-request threshold
print("--- STARTING CYBERCASH STRESS TEST ---")
threads = []
for i in range(20):
    t = threading.Thread(target=attack_worker, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("--- ATTACK SIMULATION FINISHED ---")