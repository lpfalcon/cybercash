import os
import json
from datetime import UTC, datetime, timedelta

import functions_framework
from pymongo import MongoClient, UpdateOne
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("REGION", "us-central1")
vertexai.init(project=PROJECT_ID, location=REGION)
model = GenerativeModel("gemini-2.5-flash")

MONGO_URI = os.environ.get("MONGO_URI")
mongo_client = MongoClient(MONGO_URI, maxPoolSize=20)
db = mongo_client.cybercash_db

# ==========================================
# TELEMETRY AGGREGATION
# ==========================================
def get_aggregated_telemetry():
    """Summarizes logs from the last 15 minutes, prioritizing attackers."""
    fifteen_mins_ago = datetime.now(UTC) - timedelta(minutes=15)
    
    pipeline = [
        # IMPORTANT: Ensure you have an index on {"timestamp": 1} in MongoDB
        {"$match": {"timestamp": {"$gte": fifteen_mins_ago}}},
        {"$group": {
            "_id": "$ip",
            "total_requests": {"$sum": 1},
            "failed_pows": {
                "$sum": {"$cond": [{"$eq": ["$event", "FAILED_POW"]}, 1, 0]}
            },
            "successful_pows": {
                "$sum": {"$cond": [{"$eq": ["$event", "SUCCESS"]}, 1, 0]}
            }
        }},
        {"$match": {"total_requests": {"$gt": 10}}}, # Ignore normal/low traffic
        {"$sort": {"total_requests": -1}}, # Analyze the noisiest IPs first
        {"$limit": 500} # SAFETY LIMIT: Prevents sending an infinite payload to Gemini
    ]
    
    results = list(db.audit_logs.aggregate(pipeline))
    telemetry = []
    
    for r in results:
        telemetry.append({
            "ip": r["_id"],
            "total_requests": r["total_requests"],
            "failed_pows": r["failed_pows"],
            "successful_pows": r["successful_pows"],
            "failure_rate": round(r["failed_pows"] / r["total_requests"], 2) if r["total_requests"] > 0 else 0
        })
    return telemetry

# ==========================================
# MAIN SCHEDULER FUNCTION
# ==========================================
@functions_framework.http
def run_threat_hunter(request):
    print("Starting AI threat hunt...")
    
    telemetry_data = get_aggregated_telemetry()
    
    if not telemetry_data:
        print("Normal traffic. No action required.")
        return {"status": "No suspicious traffic detected"}, 200

    prompt = f"""
    You are the CyberCash threat analysis engine. Analyze the telemetry from the last 15 minutes.
    
    Penalty rules:
    1. If `failure_rate` > 0.8 and requests > 20: It's a brute-force bot. Difficulty: 8, TTL: 7200s.
    2. If it solves everything (high successful_pows) but requests > 100: Advanced scraper. Difficulty: 6, TTL: 3600s.
    3. Normal traffic: Do not include in your response.
    
    Telemetry to analyze:
    {json.dumps(telemetry_data)}
    """

    # Enforce strict output structure using OpenAPI Schema
    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "ip": {"type": "STRING"},
                "difficulty": {"type": "INTEGER"},
                "ttl_seconds": {"type": "INTEGER"}
            },
            "required": ["ip", "difficulty", "ttl_seconds"]
        }
    }

    generation_config = GenerationConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=response_schema
    )

    try:
        response = model.generate_content(prompt, generation_config=generation_config)
        penalties = json.loads(response.text)
        
        if not penalties:
            return {"status": "AI detected no threats under current rules"}, 200

        mongo_operations = []
        
        for penalty in penalties:
            ip = penalty.get("ip")
            difficulty = penalty.get("difficulty", 6)
            ttl = penalty.get("ttl_seconds", 3600)
            
            if ip:
                expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
                mongo_operations.append(
                    UpdateOne(
                        {"ip": ip},
                        {"$set": {"difficulty": difficulty, "expires_at": expires_at}},
                        upsert=True
                    )
                )
                print(f"AI detected attack. Penalizing IP {ip} with difficulty={difficulty}")

        # Execute all database updates in a single efficient batch
        if mongo_operations:
            result = db.ai_penalties.bulk_write(mongo_operations)
            return {
                "status": "success", 
                "penalties_applied": result.upserted_count + result.modified_count
            }, 200
            
    except json.JSONDecodeError:
        print("Critical error: Vertex AI did not return valid JSON.")
        return {"error": "Invalid AI output"}, 500
    except Exception as e:
        print(f"Execution error: {e}")
        return {"error": str(e)}, 500

    return {"status": "completed with no actions"}, 200