output "gateway_public_url" {
  value       = "https://${google_api_gateway_gateway.gateway.default_hostname}"
  description = "PUBLIC URL: Use this URL to perform your Hashcash tests"
}

output "function_gateway_private_url" {
  value       = google_cloudfunctions2_function.cybercash_gateway.service_config[0].uri
  description = "PRIVATE URL: Gateway Function (returns 403 if accessed directly)"
}

output "function_scheduler_private_url" {
  value       = google_cloudfunctions2_function.cybercash_threat_hunter.service_config[0].uri
  description = "PRIVATE URL: AI Threat Hunter (Triggered by Cloud Scheduler)"
}