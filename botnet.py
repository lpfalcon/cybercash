import os
import time
import hashlib
import requests
import random
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

# Set this to your API Gateway URL or Local URL
URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8080")

print("""
====================================================
 💥 CYBERCASH ENTERPRISE - TRAFFIC SIMULATOR 💥
====================================================
""")

def solve_pow(challenge, difficulty):
    """Simulates a legitimate client solving the cryptographic puzzle."""
    nonce = 0
    prefix = "0" * difficulty
    while True:
        check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if check.startswith(prefix):
            return nonce
        nonce += 1

def simulate_legitimate_user(user_id):
    """Simulates a normal user who requests a challenge and successfully solves it."""
    ip = f"203.0.113.{user_id}" # Normal IP range
    headers = {"X-Forwarded-For": ip}
    
    try:
        # Phase 1: Request Challenge
        res1 = requests.post(URL, headers=headers, json={})
        if res1.status_code != 401:
            return f"User {user_id} | Failed to get challenge"
            
        data = res1.json()
        challenge = data.get("challenge")
        difficulty = data.get("difficulty")
        
        # Phase 2: Solve Challenge
        nonce = solve_pow(challenge, difficulty)
        
        # Phase 3: Submit Solution
        res2 = requests.post(URL, headers=headers, json={"challenge": challenge, "nonce": nonce})
        
        if res2.status_code == 200:
            return f"✅ User {user_id} ({ip}) | Solved PoW (Dif {difficulty}) | Access GRANTED"
        else:
            return f"❌ User {user_id} ({ip}) | Failed PoW | Access DENIED"
            
    except Exception as e:
        return f"User {user_id} Error: {e}"

def simulate_dumb_bot(bot_id):
    """Simulates a bot that tries to guess the PoW or just spams fake nonces."""
    ip = f"198.51.100.{random.randint(1, 5)}" # Small botnet reusing IPs
    headers = {"X-Forwarded-For": ip}
    
    try:
        res1 = requests.post(URL, headers=headers, json={})
        if res1.status_code == 401:
            data = res1.json()
            # Bot sends a random incorrect nonce
            fake_nonce = random.randint(1000, 9999)
            res2 = requests.post(URL, headers=headers, json={"challenge": data["challenge"], "nonce": fake_nonce})
            return f"🤖 Bot {bot_id} ({ip}) | Guessed wrong PoW | Result: {res2.status_code}"
    except Exception as e:
         return f"Bot {bot_id} Error: {e}"

def simulate_ddos_flood(request_id):
    """Simulates a volumetric DDoS attack with heavy IP spoofing."""
    ip = f"10.0.{random.randint(1,255)}.{random.randint(1,255)}" # Massive IP spoofing
    headers = {"X-Forwarded-For": ip}
    
    try:
        # Just spams the endpoint without ever trying to solve the PoW
        res = requests.post(URL, headers=headers, json={})
        difficulty = res.json().get("difficulty", "N/A") if res.status_code == 401 else "Error"
        return f"🔥 DDoS Req {request_id} ({ip}) | Pinged Server | Assigned Dif: {difficulty}"
    except Exception as e:
        return f"DDoS Error: {e}"

# --- EXECUTION RUNNER ---

def run_simulation():
    print("Starting simulation... Watch your Dashboard update in real-time!\n")
    
    tasks = []
    
    # 1. Add 10 Legitimate Users
    for i in range(1, 11):
        tasks.append((simulate_legitimate_user, i))
        
    # 2. Add 30 Dumb Bots (Will generate FAILED_POW events)
    for i in range(1, 31):
        tasks.append((simulate_dumb_bot, i))
        
    # 3. Add 60 DDoS Requests (Will generate a massive spike in CHALLENGE_REQUESTED)
    for i in range(1, 61):
        tasks.append((simulate_ddos_flood, i))
        
    # Shuffle the tasks to mix traffic types randomly
    random.shuffle(tasks)
    
    # Execute concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(func, arg) for func, arg in tasks]
        
        for future in futures:
            print(future.result())
            time.sleep(0.1) # Slight delay to make logs readable

    print("\n--- SIMULATION COMPLETE ---")
    print("Wait 10 seconds for the Dashboard to auto-refresh and display the new data.")

if __name__ == "__main__":
    run_simulation()