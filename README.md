# 🛡️ CyberCash 2026: Defensa Perimetral Adaptativa

> **Defensa Perimetral Adaptativa mediante Inteligencia Artificial y Costo Computacional Asimétrico**  
> *Desarrollado  para la iniciativa **Women CISO 2026**.*

---

## 📌 Resumen Ejecutivo (Abstract)

**CyberCash 2026** propone un cambio de paradigma radical en la seguridad perimetral. Al fusionar la capacidad predictiva de la Inteligencia Artificial de última generación (**Gemini 2.5 Flash en Vertex AI**) con la robustez criptográfica de los algoritmos *Proof-of-Work* (**Hashcash / SHA-256**), el sistema elimina la asimetría económica que tradicionalmente beneficia a los atacantes.

En lugar de recurrir a bloqueos binarios que suelen generar falsos positivos, CyberCash impone un **"impuesto computacional" dinámico**. Este impuesto escala proporcionalmente al nivel de riesgo detectado en tiempo real, obligando a los agentes maliciosos a consumir recursos críticos (CPU y tiempo) antes de poder interactuar con los activos sensibles.

---

## 💥 Planteamiento del Problema

En el ecosistema actual de la ciberseguridad, existe una desigualdad económica y operativa crítica:

* **El Atacante:** Ejecutar ataques de denegación de servicio (DDoS) o de fuerza bruta resulta extremadamente económico y requiere recursos financieros mínimos.
* **La Empresa:** Por el contrario, la defensa y mitigación exigen una infraestructura costosa y una gestión de recursos constante, la cual suele verse desbordada ante ataques volumétricos.

Esta disparidad permite a los atacantes perpetrar miles de intentos sin sufrir ninguna penalización, logrando agotar la disponibilidad del servidor objetivo mientras sus propios costos operativos se mantienen prácticamente en cero.

---

## 💡 La Solución: Escudo Heurístico y Fricción Computacional

CyberCash introduce el concepto de **"fricción computacional inteligente"**. El sistema adopta el algoritmo original de Hashcash no como un sistema monetario, sino como una barrera de entrada adaptativa que incrementa su complejidad (se "espesa") al detectar anomalías en el tráfico de red.

### 🛠️ Stack Tecnológico
* **Runtime:** Python 3.12 desplegado en arquitectura *Serverless* sobre **Google Cloud Run** / **Cloud Functions**.
* **Cerebro de Inferencia:** **Vertex AI** con el modelo **Gemini 2.5 Flash**, seleccionado por su baja latencia y amplia ventana de contexto.
* **Capa de Persistencia:** **MongoDB Atlas** (NoSQL) para registrar y consultar telemetría de red en tiempo real.
* **Protocolo de Desafío:** **Hashcash (SHA-256)** para la generación dinámica de Pruebas de Trabajo (*Proof-of-Work*).

---

## 🔄 Arquitectura y Flujo Lógico de Defensa (Pipeline)

El flujo de seguridad se articula en 4 pasos críticos:

1. **Interceptación y Telemetría:** Cada petición entrante se registra en MongoDB Atlas para calcular métricas de tráfico utilizando ventanas deslizantes de 1 y 10 minutos (`req_1min`, `req_10min`).
2. **Análisis de Ráfaga (*Burst Analysis*):** Se calculan los volúmenes de tráfico recientes y se inyectan como *features* al motor de decisión de IA.
3. **Inferencia Adaptativa (Vertex AI):** El modelo Gemini evalúa la telemetría y ajusta dinámicamente el nivel de dificultad criptográfica:
   * 🟢 **Riesgo Bajo (Dificultad 4):** Tráfico humano normal. Latencia imperceptible.
   * 🟡 **Riesgo Medio (Dificultad 6):** Anomalía detectada (> 5 req/min). Mitigación preventiva.
   * 🔴 **Riesgo Alto (Dificultad 8):** Ataque confirmado o saturación de API. Mitigación agresiva.
4. **Respuesta de Mitigación:** Si no se presenta una prueba válida, el servidor emite una respuesta `HTTP 401 Unauthorized` junto con un encabezado `X-Hashcash-Challenge`. El cliente debe resolver el desafío matemático antes de acceder al backend real.

---

## 💻 Código de la Solución

### 🧠 Motor de Inferencia y Escalado de Dificultad (`analyze_risk`)

```python
def analyze_risk(ip, req_1min, req_10min):
    """
    Asks Vertex AI to evaluate risk based on statistical volume.
    """
    # Professional Security Prompt
    prompt = f"""
You are a specialized Cyber-Security Risk Engine.
Analyze the following telemetry for Source IP: {ip}

- Requests in the last 60 seconds: {req_1min}
- Total requests in the last 10 minutes: {req_10min}

CRITERIA:
- If 1min requests > 10: High Risk (Potential Brute Force). Return 8.
- If 1min requests > 5: Medium Risk (Suspicious Burst). Return 6.
- If 10min requests > 30: High Risk (Sustained Scraping/DoS). Return 8.
- If 10min requests are significantly higher than 1min average: Sustained Attack. Return 8.

TASK:
Analyze if the behavior is Human (Low frequency) or Bot (High/Consistent frequency).
Return ONLY the recommended HashCash difficulty level:
- 4: Low Risk / Likely Human.
- 6: Medium Risk / Suspicious.
- 8: High Risk / Attack Detected.

OUTPUT: Return ONLY the integer (4, 6, or 8). No text.
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
```

---

### 🌐 Gateway de Seguridad (`cybercash_gateway`)

```python
@functions_framework.http
def cybercash_gateway(request):
    request_json = request.get_json(silent=True) or {}
    nonce = request_json.get("nonce")
    challenge = request_json.get("challenge")

    # Client IP identification
    if "X-Forwarded-For" in request.headers:
        client_ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    else:
        client_ip = request.remote_addr

    datetime_now = datetime.now(UTC)
    # 2. Extract Statistics from MongoDB (The "Food" for the AI)
    one_min_ago = datetime_now - timedelta(minutes=1)
    ten_min_ago = datetime_now - timedelta(minutes=10)

    # Fast counts using indexed fields
    count_1min = db.audit_logs.count_documents(
        {"ip": client_ip, "timestamp": {"$gte": one_min_ago}}
    )
    count_10min = db.audit_logs.count_documents(
        {"ip": client_ip, "timestamp": {"$gte": ten_min_ago}}
    )

    print(f"TELEMETRY: IP={client_ip} | Window_1min={count_1min} | Window_10min={count_10min}")

    # Adaptive difficulty logic
    difficulty = 4

    if count_1min > 5:
        difficulty = analyze_risk(
            ip=client_ip, req_1min=count_1min, req_10min=count_10min
        )

    # Phase 1: Challenge Request
    if not request_json or nonce is None:
        dynamic_challenge = str(uuid.uuid4())[:8]

        # LOG Challenge requested event
        log_event(
            ip=client_ip,
            event_type="CHALLENGE_REQUESTED",
            challenge=dynamic_challenge,
            difficulty=difficulty,
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
        }, 401

    # Phase 2: Challenge Validation
    valid_challenge = db.spent_nonces.find_one_and_delete({"token": challenge})

    if not valid_challenge:
        log_event(
            client_ip,
            "INVALID_CHALLENGE",
            challenge,
            difficulty,
            "Challenge not found or reused",
        )
        return {"status": "Access deny", "error": "Invalid challenge"}, 403

    check = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()

    if check.startswith("0" * difficulty):
        log_event(
            client_ip,
            "SUCCESS",
            challenge,
            difficulty,
            "Valid PoW submitted",
        )

        return {
            "status": "Access granted",
            "message": f"User {challenge} accepted",
        }, 200

    return {"status": "Error: Insufficient proof of work"}, 403
```

---

## 📊 Resultados Experimentales

Durante las pruebas de estrés ejecutadas en el entorno `cybercash-2026-production` para simular ataques de ráfaga, se obtuvieron los siguientes métricas de impacto:

| Escenario | Volumen de Tráfico | Decisión IA | Impacto Atacante (Costo CPU) |
| :--- | :--- | :--- | :--- |
| **Orgánico** | 2 req / min | Nivel 4 | < 0.1s CPU |
| **Sospechoso** | 7 req / min | Nivel 6 | ~ 3s CPU |
| **Ataque Sostenido** | 15+ req / min | Nivel 8 | > 45s CPU |

> 💥 **Análisis de Impacto:** Al alcanzar el Nivel 8, un bot que intente ejecutar 1,000 peticiones requeriría **más de 12 horas** de procesamiento continuo para completarlas. Esto invalida por completo la viabilidad técnica y económica de un ataque de fuerza bruta o raspado de datos (*scraping*).

---

## 🌱 Filosofía del Proyecto: Ética y Sostenibilidad

* 🛡️ **Inclusión y Ética (Anti-Exclusión):** A diferencia de las listas negras tradicionales que bloquean direcciones IP de forma tajante (afectando a usuarios legítimos en redes compartidas/NAT), CyberCash es una solución inclusiva. Exige una prueba de legitimidad mediante esfuerzo, reduciendo drásticamente los falsos positivos.
* 🌱 **Sostenibilidad (*Green Security*):** El consumo energético incrementa única y exclusivamente cuando se detecta una amenaza activa. Esto se traduce en un modelo de "seguridad verde" que optimiza la CPU de la empresa, trasladando el gasto computacional únicamente al agente malicioso.

---

## 🏆 Créditos e Iniciativa

* **Contribuidores:**
  - [Laura Falcón](https://www.github.com/lpfalcon)
  - [Luisa Guerrero](https://www.github.com/luisaguerrero1421)

* **Iniciativa:** Women CISO 2026
* **Entorno de Despliegue:** Google Cloud Platform (`cybercash-2026-production`)

