output "gateway_public_url" {
  value       = "https://${google_api_gateway_gateway.gateway.default_hostname}"
  description = "PUBLIC URL: Use this URL to perform your Hashcash tests (e.g., add /auth to the end)"
}

output "function_private_url" {
  value       = google_cloudfunctions2_function.cybercash_function.service_config[0].uri
  description = "PRIVATE URL: The internal URL of the Cloud Function (if you try to access it directly, you'll get a 403 Forbidden error)"
}