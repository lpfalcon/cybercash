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
