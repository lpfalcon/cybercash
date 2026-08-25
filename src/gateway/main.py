import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

import functions_framework
from pymongo import MongoClient, ReturnDocument


# ==========================================
# GLOBAL CONFIGURATION
# ==========================================


# Secret key for token generation
SECRET_KEY = os.environ.get("CYBERCASH_SECRET")

# DB connection
MONGO_URI = os.environ.get("MONGO_URI")
# Reuse the connection pool between invocations (Serverless best practice)
mongo_client = MongoClient(MONGO_URI, maxPoolSize=50, tz_aware=True)
db = mongo_client.cybercash_db

# Local in-memory cache to prevent database saturation during DDoS attacks
# Structure: {"IP": {"difficulty": 8, "expires_at": datetime}}
LOCAL_PENALTY_CACHE = {}

#------------------------------------------------
# Advanced mongo inicial indexing for performance
#------------------------------------------------

try:
    # The rate limits are deleted after 10 minutes (600 seg)
    db.rate_limits.create_index("created_at", expireAfterSeconds=600)
    # The pending challenges are deleted after 5 minutes (300 seg)
    db.pending_challenges.create_index("created_at", expireAfterSeconds=300)
    # Index for quickly searching AI penalties
    db.ai_penalties.create_index("ip", unique=True)
    # Index for telemetry aggregation query
    db.audit_logs.create_index("timestamp")
except Exception as e:
    print(f"Nota: No se pudieron verificar los índices TTL: {e}")


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_client_ip(request):
    """
    Safely retrieves the real client IP.
    Note: If using a Load Balancer, ensure it is configured to strip
    spoofed X-Forwarded-For headers sent by the client.
    """
    if "X-Forwarded-For" in request.headers:
        # Take the original IP assuming the Load Balancer appends its own at the end
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr


def generate_access_token(fingerprint):
    """Generates a signed HMAC token valid for 5 minutes."""
    expires = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())
    message = f"{fingerprint}|{expires}"
    signature = hmac.new(
        SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{message}|{signature}"


def is_token_valid(token, client_ip):
    """Validates token structure, expiration, and cryptographic signature."""
    try:
        message, t_signature = token.rsplit("|", 1)
        t_ip, t_expires = message.split("|")

        if t_ip != client_ip or datetime.now(UTC).timestamp() > float(t_expires):
            return False

        expected_sig = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()
        # Use compare_digest to prevent timing attacks
        return hmac.compare_digest(t_signature, expected_sig) 
    except Exception:
        return False


def analyze_risk_fast(ip, req_10min):
    """Determines challenge difficulty using local cache, MongoDB, or heuristics."""
    now = datetime.now(UTC)
    
    # 1. Check ultra-fast RAM cache (Prevents network calls to MongoDB)
    cached_penalty = LOCAL_PENALTY_CACHE.get(ip)
    if cached_penalty and cached_penalty["expires_at"] > now:
        return cached_penalty["difficulty"]
    elif cached_penalty:
        del LOCAL_PENALTY_CACHE[ip] # Clear expired cache

    # 2. If not in RAM, check MongoDB (Penalties dictated by the AI scheduler)
    penalty = db.ai_penalties.find_one({"ip": ip})
    if penalty and penalty.get("expires_at", now) > now:
        # Save to local RAM for subsequent requests from this attacker
        LOCAL_PENALTY_CACHE[ip] = {
            "difficulty": penalty.get("difficulty", 8),
            "expires_at": penalty["expires_at"]
        }
        return penalty.get("difficulty", 8)
        
    # 3. Baseline heuristic rules (Fallbacks if AI hasn't analyzed yet)

    if req_10min >= 50: return 8
    if req_10min >= 20: return 6
    return 4


def log_event_async(ip, event_type, challenge, difficulty, details=""):
    """Logs security events. In extreme traffic, this should route to Pub/Sub."""
    db.audit_logs.insert_one({
        "timestamp": datetime.now(UTC),
        "ip": ip,
        "event": event_type,
        "challenge": challenge,
        "difficulty": difficulty,
        "details": details,
    })


# ==========================================
# MAIN API GATEWAY
# ==========================================

@functions_framework.http
def cybercash_gateway(request):
    request_json = request.get_json(silent=True) or {}
    nonce = request_json.get("nonce")
    challenge = request_json.get("challenge")
    auth_header = request.headers.get("X-CyberCash-Token", "")
    
    client_ip = get_client_ip(request)

    # 1. Token Validation (Fast Path)
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        if is_token_valid(token, client_ip):
            return {"status": "Access granted"}, 200

    # 2. Ultra-Fast Rate Limiting (Atomic Operation)
    rate_limit_doc = db.rate_limits.find_one_and_update(
        {"ip": client_ip},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"created_at": datetime.now(UTC)}
        },
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    count_10min = rate_limit_doc.get("count", 1)

    # Calculate risk using RAM, DB, and heuristics
    difficulty = analyze_risk_fast(client_ip, count_10min)

    # 3. Generate Challenge (Phase 1)
    if not request_json or nonce is None:
        dynamic_challenge = str(uuid.uuid4())[:8]
        
        db.pending_challenges.insert_one({
            "challenge": dynamic_challenge,
            "ip": client_ip,
            "difficulty": difficulty,
            "created_at": datetime.now(UTC)
        })
        
        log_event_async(client_ip, "CHALLENGE_REQUESTED", dynamic_challenge, difficulty)
        return {
            "message": "PoW Required", 
            "challenge": dynamic_challenge, 
            "difficulty": difficulty
        }, 401

    # 4. Validate Challenge (Phase 2)
    # find_one_and_delete prevents double-spend race conditions
    challenge_data = db.pending_challenges.find_one_and_delete({
        "challenge": challenge,
        "ip": client_ip
    })
    
    if not challenge_data:
        return {"error": "Invalid, expired, or IP mismatch"}, 403

    expected_difficulty = challenge_data["difficulty"]
    check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()

    if check.startswith("0" * expected_difficulty):
        new_token = generate_access_token(client_ip)
        log_event_async(client_ip, "SUCCESS", challenge, expected_difficulty)
        return {"status": "Access granted", "token": new_token}, 200

    log_event_async(client_ip, "FAILED_POW", challenge, expected_difficulty)
    return {"error": "Insufficient PoW"}, 403