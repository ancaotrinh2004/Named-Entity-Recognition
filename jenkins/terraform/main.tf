# Ref: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.80.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Firewall — SSH, Jenkins UI, JNLP agent
resource "google_compute_firewall" "jenkins" {
  name    = "${var.jenkins_instance_name}-firewall"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "8081", "50000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["jenkins"]
}

# Static External IP
resource "google_compute_address" "jenkins_ip" {
  name   = "${var.jenkins_instance_name}-ip"
  region = var.region
}

# Compute Engine Instance
resource "google_compute_instance" "jenkins" {
  name         = var.jenkins_instance_name
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["jenkins"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = var.disk_size_gb
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.jenkins_ip.address
    }
  }

  # Startup script: cài Docker + Docker Compose rồi build và run Jenkins
  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e

    # 1. Cài Docker
    curl https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker

    # 2. Cài Docker Compose
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    # 3. Tạo thư mục project Jenkins
    mkdir -p /opt/jenkins
    cd /opt/jenkins

    # 4. Tạo Dockerfile (giống file local của bạn)
    cat > Dockerfile << 'DOCKERFILE'
FROM jenkins/jenkins:lts-jdk17
USER root
RUN curl https://get.docker.com > dockerinstall && chmod 777 dockerinstall && ./dockerinstall && \
    curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl && \
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
USER jenkins
DOCKERFILE

    # 5. Tạo docker-compose.yaml (giống file local của bạn)
    cat > docker-compose.yaml << 'COMPOSE'
version: '3.8'
services:
  jenkins:
    build: .
    container_name: jenkins
    restart: unless-stopped
    privileged: true
    user: root
    ports:
      - "8081:8080"
    volumes:
      - jenkins_home:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock
volumes:
  jenkins_home:
COMPOSE

    # 6. Build và chạy Jenkins
    docker-compose up -d --build
  SCRIPT

  service_account {
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  labels = {
    role = "jenkins"
    env  = "ci-cd"
  }
}

# Output
output "jenkins_url" {
  value = "http://${google_compute_address.jenkins_ip.address}:8081"
}

output "jenkins_ip" {
  value = google_compute_address.jenkins_ip.address
}
