# 🛡️ CyberCash 2026: Defensa Perimetral Adaptativa

> **Defensa Perimetral Adaptativa mediante Inteligencia Artificial y Costo Computacional Asimétrico**  
> *Desarrollado para la iniciativa **Women CISO 2026**.*

---

## 📌 Resumen Ejecutivo (Abstract)

**CyberCash 2026** propone un cambio de paradigma radical en la seguridad perimetral para arquitecturas Serverless. Al fusionar la capacidad predictiva de la Inteligencia Artificial de última generación (**Gemini 2.5 Flash-Lite en Vertex AI**) con la robustez de los algoritmos *Proof-of-Work* (**Hashcash / SHA-256**), el sistema elimina la asimetría económica que tradicionalmente beneficia a los atacantes.

En lugar de recurrir a bloqueos binarios por IP que generan falsos positivos en redes compartidas, CyberCash impone un **"impuesto computacional" dinámico**. Este impuesto escala proporcionalmente al nivel de riesgo detectado en tiempo real, obligando a los agentes maliciosos a saturar su propia CPU antes de poder interactuar con los activos sensibles del servidor.

---

## 💥 Planteamiento del Problema

En el ecosistema actual de ciberseguridad, existe una disparidad crítica:

* **El Atacante:** Ejecutar ataques de denegación de servicio (DDoS), *scraping* masivo o fuerza bruta es sumamente económico y requiere recursos mínimos gracias a la ejecución multihilo concurrente.
* **La Empresa:** La defensa y mitigación exigen infraestructuras costosas que suelen colapsar su base de datos o agotar el presupuesto Cloud al intentar procesar miles de peticiones maliciosas por segundo.

CyberCash invierte esta relación trasladando el 99% del consumo computacional al atacante mientras el servidor valida las peticiones en una fracción de milisegundo.

---

## 💡 Arquitectura de Bucle Cerrado (*Closed-Loop Cyber Defense*)

El sistema se compone de dos microservicios Serverless independientes desacoplados para garantizar baja latencia y alta disponibilidad:

1. **API Gateway & Gatekeeper (`src/gateway`):**
   * **Fast Path:** Autentica usuarios legítimos mediante tokens firmados con **HMAC SHA-256** (libres de estado / *stateless*).
   * **Protección Local de BD:** Utiliza un caché local en RAM (`LOCAL_PENALTY_CACHE`) para filtrar atacantes recurrentes sin saturar MongoDB.
   * **Anti-Race Condition:** Emplea búsquedas y borrados atómicos (`find_one_and_delete`) para impedir que un script multihilo reutilice un mismo desafío.

2. **AI Threat Hunter & Scheduler (`src/scheduler`):**
   * Agrega la telemetría almacenada en la colección de auditoría en ventanas deslizantes de 15 minutos.
   * Evalúa métricas avanzadas (ratio de fallo en PoW, tasa de peticiones/minuto) mediante **Gemini 2.5 Flash-Lite**.
   * Emite penalizaciones estructuradas (**JSON Schema**) guardadas en MongoDB con TTL automático que el Gateway consume en tiempo real.

---

## 🛠️ Stack Tecnológico

* **Runtime:** Python 3.12 en **Google Cloud Functions / Cloud Run**.
* **Infraestructura como Código (IaC):** **Terraform** + OpenAPI / Swagger Specification.
* **Cerebro de Inferencia:** **Vertex AI** con **Gemini 2.5 Flash-Lite** (Structured JSON Output).
* **Capa de Persistencia:** **MongoDB Atlas** con Índices TTL automáticos y consultas atómicas (`UpdateOne`, `find_one_and_update`).
* **Seguridad & Protocolos:** Hashcash (SHA-256) para Pruebas de Trabajo y firmas criptográficas HMAC SHA-256.
* **Entorno y Paquetes:** `uv` para gestión ultrasensible de dependencias Python.

---

## 📂 Estructura del Repositorio

```text
CyberCash_terraform/
├── src/                        # Código fuente Serverless
│   ├── gateway/                # API Gateway, validación HMAC y verificación PoW
│   │   ├── main.py
│   │   └── requirements.txt
│   └── scheduler/              # Threat Hunter asíncrono con Gemini AI
│       ├── main.py
│       └── requirements.txt
│
├── terraform/                  # Aprovisionamiento automatizado IaC (GCP)
│   ├── gateway/
│   │   └── openapi.yaml        # Especificación OpenAPI
│   ├── main.tf                 # Cloud Functions, API Gateway, IAM
│   ├── provider.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── benchmark.py                # Medición de tiempos de respuesta y latencia
├── botnet.py                   # Simulador de distribución de peticiones
├── multithreading.py           # Test de estrés/ataque multihilo concurrente
├── hashcash.py                 # Algoritmo cliente local SHA-256
├── dashboard.py                # Panel interactivo de métricas
└── cybercash.html              # Interfaz Web interactiva de demostración
```
---

## 💻 Código de la Solución

### 🧠 1. AI Threat Hunter (src/scheduler/main.py)

```python
# Muestra simplificada de la integración con Vertex AI y Gemini
@functions_framework.http
def run_threat_hunter(request):
    init_services()
    telemetry_data = get_aggregated_telemetry()
    
    if not telemetry_data:
        return {"status": "No suspicious traffic detected"}, 200

    prompt = f"""
    You are the CyberCash threat analysis engine. Analyze the telemetry from the last 15 minutes.
    
    Penalty rules:
    1. If `failure_rate` > 0.8 and requests > 20: It's a brute-force bot. Difficulty: 8, TTL: 7200s.
    2. If it solves everything (high successful_pows) but requests > 100: Advanced scraper. Difficulty: 6, TTL: 3600s.
    3. Normal traffic: Do not include in your response.
    
    Telemetry to analyze: {json.dumps(telemetry_data)}
    """

    generation_config = GenerationConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=response_schema
    )

    response = model.generate_content(prompt, generation_config=generation_config)
    penalties = json.loads(response.text)

    # Inyección masiva y atómica de penalizaciones hacia MongoDB
    mongo_operations = [
        UpdateOne(
            {"ip": p["ip"]},
            {"$set": {"difficulty": p.get("difficulty", 6), "expires_at": datetime.now(UTC) + timedelta(seconds=p.get("ttl_seconds", 3600))}},
            upsert=True
        ) for p in penalties if p.get("ip")
    ]
    
    if mongo_operations:
        db.ai_penalties.bulk_write(mongo_operations)
    
    return {"status": "success", "penalties_applied": len(mongo_operations)}, 200
```

---

### 🌐 2. API Gateway & Fast Path Validation (src/gateway/main.py)

```python
@functions_framework.http
def cybercash_gateway(request):
    client_ip = get_client_ip(request)
    auth_header = request.headers.get("X-CyberCash-Token", "")

    # 1. Validar Token HMAC (Fast Path sin llamadas a Base de Datos)
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        if is_token_valid(token, client_ip):
            return {"status": "Access granted"}, 200

    # 2. Análisis Rápido de Riesgo (Memoria RAM Cache -> DB)
    difficulty = analyze_risk_fast(client_ip, count_10min)

    # 3. Fase de Desafío (Emisión)
    if not request_json or nonce is None:
        dynamic_challenge = str(uuid.uuid4())[:8]
        db.pending_challenges.insert_one({
            "challenge": dynamic_challenge, "ip": client_ip, 
            "difficulty": difficulty, "created_at": datetime.now(UTC)
        })
        return {"message": "PoW Required", "challenge": dynamic_challenge, "difficulty": difficulty}, 401

    # 4. Fase de Verificación Atómica (Protección contra Race Conditions)
    challenge_data = db.pending_challenges.find_one_and_delete({
        "challenge": challenge, "ip": client_ip
    })
    
    if not challenge_data:
        return {"error": "Invalid, expired, or IP mismatch"}, 403

    check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
    if check.startswith("0" * challenge_data["difficulty"]):
        new_token = generate_access_token(client_ip)
        return {"status": "Access granted", "token": new_token}, 200

    return {"error": "Insufficient PoW"}, 403
```

---

## 📊 Resultados Experimentales

Durante las pruebas de estrés ejecutadas con scripts de ataque multihilo (`multithreading.py`), se obtuvieron las siguientes métricas de impacto:

| Perfil de Tráfico | Comportamiento | Nivel Asignado por IA | Tiempo de Cómputo (Cliente) | Carga en Servidor |
| :--- | :--- | :--- | :--- | :--- |
| **Humano / Orgánico** | Peticiones espaciadas | Dificultad 4 | `< 0.05s` | Mínima |
| **Advanced Scraper** | Concurrencia media, 100+ reqs | Dificultad 6 (TTL 1h) | `~ 2.5s` por hilo | Nula (Verificación) |
| **Brute-Force Botnet** | Tasa de fallo PoW > 80% | Dificultad 8 (TTL 2h) | `> 40s` por hilo | Nula (CPU atacante saturada) |

---

## 🌱 Filosofía del Proyecto: Ética y Sostenibilidad

* 🛡️ **Inclusión y Ética (Anti-Exclusión):** A diferencia de las listas negras tradicionales que bloquean direcciones IP de forma tajante (afectando a usuarios legítimos en redes compartidas/NAT), CyberCash es una solución inclusiva. Exige una prueba de legitimidad mediante esfuerzo, reduciendo drásticamente los falsos positivos.
* 🌱 **Sostenibilidad (*Green Security*):** El consumo energético incrementa única y exclusivamente cuando se detecta una amenaza activa. Esto se traduce en un modelo de "seguridad verde" que optimiza la CPU de la empresa, trasladando el gasto computacional únicamente al agente malicioso.

---

## 🏆 Créditos e Iniciativa

* **Contribuidores:**
  - [Laura Falcón](https://www.github.com/lpfalcon)
  - [Luisa Guerrero](https://www.github.com/luisaguerrero1421)
  - [Antuane Huaman](https://www.github.com/github0dot5Ane)


* **Iniciativa:** Women CISO 2026
* **Entorno de Despliegue:** Google Cloud Platform (`cybercash-2026-production`)

