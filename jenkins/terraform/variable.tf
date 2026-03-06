// Variables for Jenkins Compute Engine
// Access by var.project_id, var.region, etc.

variable "project_id" {
  description = "The project ID to host Jenkins"
  default     = "aide1-488405"
}

variable "region" {
  description = "The region for Jenkins VM"
  default     = "asia-southeast1"
}

variable "zone" {
  description = "The zone for Jenkins VM"
  default     = "asia-southeast1-b"
}

variable "jenkins_instance_name" {
  description = "Name of the Jenkins VM instance"
  default     = "jenkins-server"
}

variable "machine_type" {
  description = "Machine type for Jenkins VM"
  default     = "e2-standard-2" // 2 vCPU, 8GB RAM
}

variable "disk_size_gb" {
  description = "Boot disk size in GB"
  default     = 50
}
