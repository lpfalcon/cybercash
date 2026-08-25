import os
import time
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# Target API URL from environment variables or default local path
URL = os.getenv("URL")

# Load attack configuration
NUM_THREADS = 20  # Number of concurrent requests (threads)

def solve_hashcash(challenge, difficulty):
    """Solves the Proof of Work (PoW) cryptographic challenge."""
    objective = "0" * difficulty
    nonce = 0
    while True:
        content = f"{challenge}{nonce}".encode()
        if hashlib.sha256(content).hexdigest().startswith(objective):
            return nonce
        nonce += 1

def worker_simulate_attack(thread_id):
    """
    Executes an independent worker thread.
    Attempts to flood the endpoint and solves the PoW challenge if required by the server.
    """
    start_time = time.time()
    try:
        # 1. Initial burst request (without prior authentication token)
        res = requests.post(URL, json={}, timeout=10)
        
        # CASE A: Server demands Proof of Work (Protection active)
        if res.status_code == 401:
            data = res.json()
            challenge = data.get("challenge")
            difficulty = data.get("difficulty")
            
            # Thread must spend local CPU time solving its assigned cryptographic puzzle
            pow_start = time.time()
            nonce = solve_hashcash(challenge, difficulty)
            pow_duration = time.time() - pow_start
            
            # Submit PoW solution back to the server
            res_token = requests.post(
                URL, 
                json={"challenge": challenge, "nonce": nonce},
                timeout=10
            )
            
            total_duration = time.time() - start_time
            if res_token.status_code == 200:
                return {
                    "thread_id": thread_id,
                    "status": "Success (PoW Solved)",
                    "pow_time": pow_duration,
                    "total_time": total_duration,
                    "code": 200
                }
            else:
                return {
                    "thread_id": thread_id,
                    "status": "PoW Validation Failed",
                    "total_time": total_duration,
                    "code": res_token.status_code
                }
        
        # CASE B: Server responded directly without requiring PoW
        total_duration = time.time() - start_time
        return {
            "thread_id": thread_id,
            "status": "Direct Response",
            "pow_time": 0,
            "total_time": total_duration,
            "code": res.status_code
        }

    except requests.exceptions.RequestException as e:
        return {
            "thread_id": thread_id,
            "status": f"Connection Error: {type(e).__name__}",
            "pow_time": 0,
            "total_time": time.time() - start_time,
            "code": 0
        }

def run_stress_test():
    print("=" * 60)
    print(f"🔥 STARTING MULTITHREADED LOAD SIMULATION ON LOCALHOST")
    print(f"🎯 Target Endpoint: {URL}")
    print(f"⚡ Concurrent Threads: {NUM_THREADS}")
    print("=" * 60 + "\n")

    global_start = time.time()
    results = []

    # Dispatch all threads simultaneously in parallel
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(worker_simulate_attack, i) for i in range(1, NUM_THREADS + 1)]
        
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"[Thread {res['thread_id']:02d}] "
                  f"HTTP Code: {res['code']} | "
                  f"Status: {res['status']} | "
                  f"Total Time: {res['total_time']:.2f}s")

    total_test_duration = time.time() - global_start

    # Metrics aggregation for presentation/reporting
    successful_requests = sum(1 for r in results if r['code'] == 200)
    pow_challenges_solved = sum(1 for r in results if r['pow_time'] > 0)
    failed_requests = sum(1 for r in results if r['code'] != 200)

    print("\n" + "=" * 60)
    print("📊 STRESS TEST & RESILIENCE SUMMARY")
    print("=" * 60)
    print(f"⏱️  Total Test Duration: {total_test_duration:.2f} seconds")
    print(f"✅ Successfully Completed Requests: {successful_requests}/{NUM_THREADS}")
    print(f"⛏️  PoW Challenges Solved by Threads: {pow_challenges_solved}")
    print(f"❌ Rejected / Failed Requests: {failed_requests}")
    print("=" * 60)

if __name__ == "__main__":
    run_stress_test()