import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

import functions_framework
import vertexai
from pymongo import MongoClient
from vertexai.generative_models import GenerativeModel

# VERTEX AI
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
vertexai.init(project=PROJECT_ID, location="us-central1")
model = GenerativeModel(
    "gemini-2.5-flash-image", generation_config={"temperature": 0.1}
)

# DB connection
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.cybercash_db

# Secret key for token generation

SECRET_KEY = os.environ.get("CYBERCASH_SECRET", "super-secret-key-2026")


def generate_access_token(fingerprint):
    """Generates a signed HMAC token valid for 5 minutes."""
    expires = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())
    message = f"{fingerprint}|{expires}"
    signature = hmac.new(
        SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{message}|{signature}"


def is_token_valid(token, current_fingerprint):
    """Validates the session token integrity, ownership, and expiration."""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            print(f"DEBUG: Token structure error. Parts found: {len(parts)}")
            return False

        t_fingerprint, t_expires, t_signature = parts

        if t_fingerprint != current_fingerprint:
            print(
                f"DEBUG: Fingerprint mismatch. Header: {current_fingerprint} vs Token: {t_fingerprint}"
            )
            return False

        if datetime.now(UTC).timestamp() > float(t_expires):
            print(
                f"DEBUG: Token expired. Header: {current_fingerprint} vs Token: {t_fingerprint}"
            )
            return False

        expected_message = f"{t_fingerprint}|{t_expires}"
        expected_sig = hmac.new(
            SECRET_KEY.encode(), expected_message.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(t_signature, expected_sig)
    except Exception:
        return False


def analyze_risk(ip, fingerprint, req_10min):
    """
    Asks Vertex AI to evaluate risk based on statistical volume.
    """
    # Professional Security Prompt
    prompt = f"""
    [ROLE]
    You are the CyberCash Adaptive Risk Engine. Your goal is to apply computational friction (PoW) 
    to suspicious entities to prevent API exhaustion.

    [TELEMETRY]
    - Source IP: {ip}
    - Device Fingerprint (Hardware ID): {fingerprint}
    - Request Volume (10-min window): {req_10min}

    [THREAT ANALYSIS GUIDELINES]
    1. DEVICE CONSISTENCY: If req_10min > 30 from a single fingerprint, it's a high-velocity bot.
    2. BEHAVIORAL PATTERN: 
       - 1-10 requests: Likely Human / Low frequency.
       - 11-25 requests: Suspicious / Potential Crawler.
       - >25 requests: Aggressive Bot / DoS attempt.

    [DECISION LOGIC]
    - Return 4: Low risk. User experience is priority.
    - Return 6: Moderate risk. Increase CPU cost to discourage automation.
    - Return 8: Critical risk. Force maximum computational penalty to mitigate attack.

    [STRICT OUTPUT RULE]
    Return ONLY the integer (4, 6, or 8). Do not provide explanations or labels.
    """

    try:
        response = model.generate_content(prompt)
        # Extract only digits to be safe
        if not response or not response.text:
            return 4

        result = "".join(filter(str.isdigit, response.text))
        difficulty = int(result) if result in ["4", "6", "8"] else 4

        print(f"DEBUG: AI Decision for {ip} -> Difficulty Level: {difficulty}")

        return difficulty
    except Exception as e:
        print(f"AI Error: {e}")
        return 4  # Fail-safe default


def log_event(ip, event_type, challenge, difficulty, fingerprint, details=""):
    """
    Log  security events in audit collection
    """

    db.audit_logs.insert_one(
        {
            "timestamp": datetime.now(UTC),
            "ip": ip,
            "event": event_type,
            "challenge": challenge,
            "difficulty": difficulty,
            "fingerprint": fingerprint,
            "details": details,
        }
    )


@functions_framework.http
def cybercash_gateway(request):

    request_json = request.get_json(silent=True) or {}
    nonce = request_json.get("nonce")
    challenge = request_json.get("challenge")

    # ingerprintand identification
    fingerprint = request.headers.get("X-Device-Fingerprint", "unknown")
    auth_header = request.headers.get("X-CyberCash-Token", "")

    # Client IP identification
    if "X-Forwarded-For" in request.headers:
        client_ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    else:
        client_ip = request.remote_addr

    # Token verification

    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        if is_token_valid(token, fingerprint):
            return {"status": "Access granted", "method": "Token"}, 200
        else:
            print(f"DEBUG: Invalid token presented by {fingerprint}")

    datetime_now = datetime.now(UTC)
    # 2. Extract Statistics from MongoDB (The "Food" for the AI)
    ten_min_ago = datetime_now - timedelta(minutes=10)
    one_hour_ago = datetime_now - timedelta(hours=1)

    # Fast counts using indexed fields

    count_10min = db.audit_logs.count_documents(
        {
            "fingerprint": fingerprint,
            "event": "CHALLENGE_REQUESTED",
            "timestamp": {"$gte": ten_min_ago},
        }
    )

    print(
        f"TELEMETRY: IP={client_ip} | fingerprint= {fingerprint} | Window_10min={count_10min}"
    )

    # Historical suspicion check (Prevents "Low-and-Slow" from cooling down)
    recent_penalty = db.audit_logs.find_one(
        {
            "fingerprint": fingerprint,
            "difficulty": {"$gte": 6},
            "timestamp": {"$gte": one_hour_ago},
        }
    )
    # Adaptive difficulty logic
    difficulty = 4

    if count_10min > 10:
        difficulty = analyze_risk(
            ip=client_ip, fingerprint=fingerprint, req_10min=count_10min
        )

    # PERSISTENT PENALTY: Keep difficulty at 6 if they were penalized recently
    if recent_penalty and difficulty < 6:
        difficulty = 6
        print(
            f"DEBUG: Applying persistent penalty for {fingerprint} due to recent history."
        )
    # Phase 1: Challenge
    if not request_json or nonce is None:
        dynamic_challenge = str(uuid.uuid4())[:8]

        # LOG Challenge requested event
        log_event(
            ip=client_ip,
            event_type="CHALLENGE_REQUESTED",
            challenge=dynamic_challenge,
            difficulty=difficulty,
            fingerprint=fingerprint,
            details="New challenge issued",
        )

        # INSERT spent_nonces
        db.spent_nonces.insert_one(
            {
                "token": dynamic_challenge,
                "status": "active",
                "ip": client_ip,
                "created_at": datetime_now,
            }
        )

        return {
            "message": "This account is protected by Cybercash. You must solve a challenge to enter.",
            "challenge": dynamic_challenge,
            "difficulty": difficulty,
            "system_status": "High Traffic - Increasing PoW"
            if difficulty > 4
            else "Normal",
            "fingerprint_status": "Identified"
            if fingerprint != "unknown"
            else "Missing",
        }, 401

    # Phase 2: Challenge Validation
    valid_challenge = db.spent_nonces.find_one_and_delete({"token": challenge})

    if not valid_challenge:
        log_event(
            client_ip,
            "INVALID_CHALLENGE",
            challenge,
            difficulty,
            fingerprint,
            "Challenge not found or reused",
        )
        return {"status": "Access deny", "error": "Invalid challenge"}, 403

    check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()

    if check.startswith("0" * difficulty):
        new_token = generate_access_token(fingerprint)

        log_event(
            client_ip,
            "SUCCESS",
            challenge,
            difficulty,
            fingerprint,
            "Valid PoW submitted",
        )

        return {
            "status": "Access granted",
            "message": f"User {challenge} accepted",
            "token": new_token,
            "expires_in": "5m",
        }, 200

    return {"status": "Error: Insufficient proof of work"}, 403
