import os

import requests
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("URL", "YOUR_CLOUD_FUNCTION_URL_HERE")

print("--- STARTING BOTNET IP-SPOOFING SIMULATION ---")

for i in range(50):
    fake_ip = f"192.168.1.{i}"
    headers = {
        "X-Forwarded-For": fake_ip,
        # We use a static fingerprint to see if the AI detects the "Many IPs, One Device" pattern
        "X-Device-Fingerprint": "botnet-zombie-001",
        "X-CyberCash-Token": "Bearer invalid-token-test"
    }
    
    try:
        response = requests.post(URL, headers=headers, json={})
        data = response.json()
        
        difficulty = data.get("difficulty", "N/A")
        status = data.get("system_status", "N/A")
        
        print(f"Request {i+1} | Spoofed IP: {fake_ip} | Difficulty: {difficulty} | Status: {status}")
        
    except Exception as e:
        print(f"Request {i+1} failed: {e}")

print("--- SIMULATION COMPLETE ---")