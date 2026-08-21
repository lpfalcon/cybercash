# Habilita los servicios necesarios en Google Cloud
resource "google_project_service" "services" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com", # Necesario para Functions v2
    "apigateway.googleapis.com",       # API Gateway
    "servicecontrol.googleapis.com",    # Dependencia de Gateway
    "servicemanagement.googleapis.com", # Dependencia de Gateway
    "cloudscheduler.googleapis.com"     # Habilitar Cloud Scheduler
  ])
  service            = each.key
  disable_on_destroy = false
}

# Bucket de almacenamiento para guardar el código de las funciones
resource "google_storage_bucket" "function_bucket" {
  name          = "${var.project_id}-cybercash-code"
  location      = var.region
  force_destroy = true
}

# ==========================================
# 1. EMPAQUETADO DE CÓDIGO
# ==========================================

# Comprime la carpeta del Gateway
data "archive_file" "gateway_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/gateway"
  output_path = "${path.module}/../gateway.zip"
}

# Comprime la carpeta del Scheduler
data "archive_file" "scheduler_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/scheduler"
  output_path = "${path.module}/../scheduler.zip"
}

# Sube el código del Gateway
resource "google_storage_bucket_object" "gateway_code" {
  name   = "gateway-${data.archive_file.gateway_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.gateway_zip.output_path
}

# Sube el código del Scheduler
resource "google_storage_bucket_object" "scheduler_code" {
  name   = "scheduler-${data.archive_file.scheduler_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.scheduler_zip.output_path
}

# ==========================================
# 2. FUNCIONES CLOUD (V2)
# ==========================================

# Función Gateway (Rápida, sin IA)
resource "google_cloudfunctions2_function" "cybercash_gateway" {
  depends_on  = [google_project_service.services]
  name        = var.function_name
  location    = var.region
  description = "CyberCash API Gateway - Fast Path"

  build_config {
    runtime     = "python311"
    entry_point = "cybercash_gateway" # Nombre de tu función en main.py
    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.gateway_code.name
      }
    }
  }

  service_config {
    max_instance_count = 5
    available_memory   = "256M" # Menos memoria requerida
    timeout_seconds    = 60
    
    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      MONGO_URI            = var.mongo_uri
      CYBERCASH_SECRET     = var.cybercash_secret
    }
  }
}

# Función Scheduler (Pesada, con IA)
resource "google_cloudfunctions2_function" "cybercash_threat_hunter" {
  depends_on  = [google_project_service.services]
  name        = "cybercash-threat-hunter"
  location    = var.region
  description = "CyberCash AI Threat Hunter"

  build_config {
    runtime     = "python311"
    entry_point = "run_threat_hunter" # Nombre de tu función en scheduler.py
    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.scheduler_code.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "512M" # Más memoria para Vertex AI
    timeout_seconds    = 120
    
    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      MONGO_URI            = var.mongo_uri
      REGION               = var.region
    }
  }
}

# ==========================================
# 3. SEGURIDAD E IAM
# ==========================================

# Service Account para el API Gateway público
resource "google_service_account" "gateway_sa" {
  account_id   = "cybercash-gateway-sa"
  display_name = "SA for CyberCash API Gateway"
  depends_on   = [google_project_service.services]
}

# Permiso para que el Gateway invoque la función Gateway
resource "google_cloud_run_service_iam_member" "gateway_access" {
  location = google_cloudfunctions2_function.cybercash_gateway.location
  service  = google_cloudfunctions2_function.cybercash_gateway.service_config[0].service
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gateway_sa.email}"
}

# Service Account exclusiva para que Cloud Scheduler invoque el Threat Hunter
resource "google_service_account" "scheduler_sa" {
  account_id   = "cybercash-scheduler-sa"
  display_name = "SA for Cloud Scheduler to invoke Threat Hunter"
  depends_on   = [google_project_service.services]
}

# Permiso para que Cloud Scheduler invoque la función del Threat Hunter
resource "google_cloud_run_service_iam_member" "scheduler_access" {
  location = google_cloudfunctions2_function.cybercash_threat_hunter.location
  service  = google_cloudfunctions2_function.cybercash_threat_hunter.service_config[0].service
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# ==========================================
# 4. API GATEWAY PÚBLICO
# ==========================================

resource "google_api_gateway_api" "api" {
  provider     = google
  api_id       = "cybercash-api"
  display_name = "CyberCash Security API"
  depends_on   = [google_project_service.services]
}


#Configuración del Gateway 
resource "google_api_gateway_api_config" "api_config" {
  provider      = google
  api           = google_api_gateway_api.api.api_id
  api_config_id = "cybercash-config"

  openapi_documents {
    document {
      path = "spec.yaml"
      contents = base64encode(templatefile("${path.module}/gateway/openapi.yaml", {
        # URL del cloud function en el YAML
        function_url = google_cloudfunctions2_function.cybercash_gateway.service_config[0].uri
      }))
    }
  }

  gateway_config {
    backend_config {
      google_service_account = google_service_account.gateway_sa.email
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_api_gateway_gateway" "gateway" {
  provider   = google
  region     = var.region
  api_config = google_api_gateway_api_config.api_config.id
  gateway_id = "cybercash-gateway"
  depends_on = [google_api_gateway_api_config.api_config]
}

# ==========================================
# 5. CLOUD SCHEDULER JOB (El "Cron" de la IA)
# ==========================================

resource "google_cloud_scheduler_job" "threat_hunter_trigger" {
  depends_on       = [google_project_service.services]
  name             = "trigger-ai-threat-hunter"
  description      = "Ejecuta el análisis de IA de Vertex cada 15 minutos"
  schedule         = "*/15 * * * *"
  time_zone        = "UTC"
  attempt_deadline = "180s"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.cybercash_threat_hunter.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}