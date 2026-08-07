# Habilita los servicios necesarios en Google Cloud
resource "google_project_service" "services" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com", # Necesario para Functions v2
    "apigateway.googleapis.com",       # API Gateway
    "servicecontrol.googleapis.com",   # Dependencia de Gateway
    "servicemanagement.googleapis.com" # Dependencia de Gateway
  ])
  service            = each.key
  disable_on_destroy = false
}

# Bucket de almacenamiento para guardar el código de la función
resource "google_storage_bucket" "function_bucket" {
  name          = "${var.project_id}-cybercash-code"
  location      = var.region
  force_destroy = true
}


# Data fuente para comprimir la  carpeta de la Cloud Function automáticamente
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/main.py"  # Apunta al archivo main de la carpeta src
  output_path = "${path.module}/../function.zip"
}

# Sube el código fuente comprimido
resource "google_storage_bucket_object" "source_code" {
  name   = "function-${data.archive_file.lambda_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.lambda_zip.output_path
}

# Crea la Cloud Function (v2) - Backend
resource "google_cloudfunctions2_function" "cybercash_function" {
  depends_on  = [google_project_service.services]
  name        = var.function_name
  location    = var.region
  description = "CyberCash AI Adaptive Security Backend"

  build_config {
    runtime     = "python311"
    entry_point = "handler"
    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.source_code.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "512M"
    timeout_seconds    = 60
    
    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      MONGO_URI = var.mongo_uri
      CYBERCASH_SECRET = var.cybercash_secret
    }
  }
}

# Crea una Service Account exclusiva para el Gateway
resource "google_service_account" "gateway_sa" {
  account_id   = "cybercash-gateway-sa"
  display_name = "Service Account for CyberCash API Gateway"
  depends_on   = [google_project_service.services]
}

# Da permiso SOLO al Gateway para invocar la Función (Cierra la puerta trasera)
resource "google_cloud_run_service_iam_member" "gateway_access" {
  location = google_cloudfunctions2_function.cybercash_function.location
  service  = google_cloudfunctions2_function.cybercash_function.service_config[0].service
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gateway_sa.email}"
}

# Define la API Lógica del Gateway
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
        function_url = google_cloudfunctions2_function.cybercash_function.service_config[0].uri
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

# Despliegue del Gateway Físico (El punto de acceso público)
resource "google_api_gateway_gateway" "gateway" {
  provider   = google
  region     = var.region
  api_config = google_api_gateway_api_config.api_config.id
  gateway_id = "cybercash-gateway"
  depends_on = [google_api_gateway_api_config.api_config]
}