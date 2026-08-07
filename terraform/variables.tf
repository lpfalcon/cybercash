variable "project_id"{
    type = string
    description = "The ID of your New Google Cloud Project"
}

variable "region"{
    type = string
    default = "us-central1"
    description = "The region where the resources will be deployed"
}


variable "function_name" {
    type = string
    default = "cybercash-gateway"
    description = "The name of the Cloud Function to be created"}


variable "mongo_uri" {
    type        = string
    description = "The MongoDB connection URI for the CyberCash backend"
    sensitive   = true # this variable is sensitive and will not be displayed in logs or outputs
}


variable "cyberchash_secret" {
    type        = string
    description = "A secret key used for the CyberCash Hashcash algorithm"
    sensitive   = true # this variable is sensitive and will not be displayed in logs or outputs
}