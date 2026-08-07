# 1. Habilitar los servicios necesarios en el nuevo proyecto
resource "google_project_service" "services" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com", # Vertex AI para Gemini
    "run.googleapis.com"         # Cloud Functions v2 depende de Cloud Run
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Bucket de almacenamiento para guardar el código de la función
resource "google_storage_bucket" "function_bucket" {
  name     = "${var.project_id}-cybercash-code"
  location = var.region
  force_destroy = true
}

# 3. Subir el código fuente comprimido (asumiendo que tienes un archivo function.zip)
resource "google_storage_bucket_object" "source_code" {
  name   = "function-${data.archive_file.lambda_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = "${path.module}/../function.zip"
}

# Data fuente para comprimir tu carpeta de la Cloud Function automáticamente
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src" # Apunta a donde está tu código Python actual
  output_path = "${path.module}/../function.zip"
}

# 4. Crear la Cloud Function (v2)
resource "google_cloudfunctions2_function" "cybercash_function" {
  depends_on = [google_project_service.services]
  name        = var.function_name
  location    = var.region
  description = "CyberCash AI Adaptive Security Gateway"

  build_config {
    runtime     = "python311" # O la versión que uses
    entry_point = "handler"   # Nombre de tu función principal en main.py
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
    
    # Aquí irán tus variables de entorno como la URI de Mongo
    environment_variables = {
      MONGO_URI = "tu_uri_de_mongo_aqui"
    }
  }
}

# 5. Hacer la función pública para que tus scripts de ataque puedan estresarla
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloudfunctions2_function.cybercash_function.location
  service  = google_cloudfunctions2_function.cybercash_function.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}