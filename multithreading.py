import hashlib
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
# Make sure GATEWAY_URL points to your actual backend
URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8080")

def solve_hashcash(challenge, difficulty):
    """Solves the Proof of Work (PoW) cryptographic challenge."""
    objective = "0" * difficulty
    nonce = 0
    while True:
        content = f"{challenge}{nonce}".encode()
        if hashlib.sha256(content).hexdigest().startswith(objective):
            return nonce
        nonce += 1

def run_legitimate_client(total_requests=15):
    """Simulates a legitimate client application interacting with the API."""
    try:
        print(f"🚀 Starting CyberCash Enterprise Client...")
        print(f"🔗 Target URL: {URL}\n")
        
        auth_token = None

        for i in range(1, total_requests + 1):
            print(f"--- Request #{i:02d} ---")
            start_time = time.time()

            # Dynamic headers (Only adding the token if we have one)
            headers = {}
            if auth_token:
                headers["X-CyberCash-Token"] = f"Bearer {auth_token}"
                print(f"🔑 Using Cached Token: {auth_token[:10]}...{auth_token[-5:]}")

            # 1. Initial Request (Attempting access)
            result = requests.post(URL, headers=headers, json={})

            # CASE A: Server demands PoW (No token, invalid, or expired)
            if result.status_code == 401:
                json_result = result.json()
                challenge = json_result.get("challenge")
                difficulty = json_result.get("difficulty")

                print(f"🛡️  Server requested PoW | Difficulty: {difficulty} | Challenge: {challenge}")

                # Solve the cryptographic challenge locally
                pow_start = time.time()
                nonce = solve_hashcash(challenge, difficulty)
                pow_duration = time.time() - pow_start
                
                print(f"⛏️  Solved PoW in {pow_duration:.3f}s | Nonce: {nonce}")

                # 2. SECOND REQUEST: Submit solution to get access and a token
                result_token = requests.post(
                    URL, 
                    json={"challenge": challenge, "nonce": nonce}, 
                    headers=headers
                )

                if result_token.status_code == 200:
                    # SAVE THE TOKEN FOR SUBSEQUENT REQUESTS
                    auth_token = result_token.json().get("token")
                    total_duration = time.time() - start_time
                    print(f"✅ Access Granted in {total_duration:.3f}s total. Token saved.")
                else:
                    print(f"❌ PoW Validation Failed: {result_token.json().get('error', 'Unknown error')}")
                    auth_token = None # Clear invalid token to force a new challenge next time

            # CASE B: Direct access via valid Token (Fast Path)
            elif result.status_code == 200:
                duration = time.time() - start_time
                print(f"⚡ Instant Access via Token in {duration:.4f}s")

            else:
                print(f"⚠️ Unexpected Server Response: {result.status_code}")
                print(result.text)

            # 1 second delay to mimic normal human/app interaction pacing
            time.sleep(1)  

    except requests.exceptions.RequestException as e:
        print(f"🔴 CONNECTION ERROR: Is the server running? Details: {e}")
    except Exception as e:
        print(f"🔴 UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    # Simulate a user making 20 legitimate requests
    run_legitimate_client(20)