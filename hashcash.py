import hashlib
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv("URL")

def solve_hashcash(input_data, difficulty):
    objective = "0" * difficulty
    nonce = 0
    while True:
        content = f"{input_data}{nonce}".encode()
        if hashlib.sha256(content).hexdigest().startswith(objective):
            return nonce
        nonce += 1


def simulate_traffic(total_requests=15):
    try:
        print("🚀 Iniciando CyberCash Client...")
        auth_token = None

        for i in range(1, total_requests + 1):
            print(f"\n--- Intento #{i} ---")
            start_time = time.time()

            # Preparamos headers dinámicos
            headers = {}
            if auth_token:
                headers["X-CyberCash-Token"] = f"Bearer {auth_token}"
                print(f"🔑 Usando Token: {auth_token[:15]}...")

            # 1. Petición inicial
            result = requests.post(URL, headers=headers, json={})

            # CASO A: El servidor pide reto (No hay token o expiró)
            if result.status_code == 401:
                json_result = result.json()
                challenge = json_result["challenge"]
                difficulty = json_result["difficulty"]

                print(f"📡 Reto Nivel {difficulty} recibido.")

                # Resolver reto
                nonce = solve_hashcash(challenge, difficulty)

                # 2. SEGUNDA PETICIÓN: Enviar solución para obtener el Token
                # NOTA: Aquí enviamos la solución del reto
                result_token = requests.post(
                    URL, json={"challenge": challenge, "nonce": nonce}, headers=headers
                )

                if result_token.status_code == 200:
                    # ¡GUARDAMOS EL TOKEN AQUÍ PARA EL SIGUIENTE INTENTO!
                    auth_token = result_token.json().get("token")
                    duration = time.time() - start_time
                    print(f"✅ Acceso Concedido en {duration:.2f}s. Token guardado.")
                else:
                    print(f"❌ Error en validación: {result_token.json().get('error')}")

            # CASO B: Acceso directo con Token
            elif result.status_code == 200:
                print(
                    f"⚡ Acceso instantáneo vía {result.json().get('method', 'Token')} en {time.time() - start_time:.4f}s"
                )

            else:
                print(f"⚠️ Estado inesperado: {result.status_code}")
                print(result.text)

            time.sleep(1)  # Espera un segundo entre intentos para ver el flujo

    except Exception as e:
        print(f"🔴 ERROR EN EL SCRIPT: {e}")


if __name__ == "__main__":
    simulate_traffic(5)
