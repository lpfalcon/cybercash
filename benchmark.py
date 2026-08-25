import os
import time
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv("URL")

def solve_pow(challenge, difficulty):
    start = time.time()
    nonce = 0
    prefix = "0" * difficulty
    while True:
        check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if check.startswith(prefix):
            return nonce, time.time() - start
        nonce += 1

def attack_worker(target_ip, request_id):
    headers = {"X-Forwarded-For": target_ip}
    
    # Step 1: Request Challenge
    t0 = time.time()
    res1 = requests.post(URL, headers=headers, json={})
    if res1.status_code != 401:
        return {"id": request_id, "status": res1.status_code, "cpu_time": 0, "net_time": time.time() - t0}

    data = res1.json()
    diff = data["difficulty"]
    
    # Step 2: Resolve PoW
    nonce, cpu_time = solve_pow(data["challenge"], diff)
    
    # Step 3: Submit Response
    res2 = requests.post(URL, headers=headers, json={"challenge": data["challenge"], "nonce": nonce})
    net_time = (time.time() - t0) - cpu_time
    
    return {
        "id": request_id,
        "difficulty": diff,
        "cpu_time": cpu_time,
        "net_time": net_time,
        "status": res2.status_code
    }

def run_stress_test(ip="198.51.100.99", total_requests=15):
    print(f"🔥 Iniciando Stress Test de PoW para IP {ip}...\n")
    results = []
    
    # Execute requests sequentially to avoid overwhelming the server
    for i in range(1, total_requests + 1):
        res = attack_worker(ip, i)
        results.append(res)
        print(f"Req #{i:02d} | Dif: {res.get('difficulty', 'N/A')} | CPU Cliente: {res['cpu_time']:.4f}s | Red Gateway: {res['net_time']:.4f}s | HTTP {res['status']}")

if __name__ == "__main__":
    run_stress_test()