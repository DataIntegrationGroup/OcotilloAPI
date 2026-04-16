locals {
  prefix         = "geoserver"
  vm_name        = "geoserver-proto-01"
  disk_name      = "geoserver-data-disk-01"
  instance_group = "geoserver-ig"
  tags           = ["geoserver", "allow-health-check"]
}

resource "google_project_service" "compute" {
  service = "compute.googleapis.com"
}

resource "google_compute_disk" "geoserver_data" {
  name = local.disk_name
  type = "pd-ssd"
  zone = var.zone
  size = var.data_disk_size_gb
}

resource "google_compute_firewall" "ssh_admin" {
  name          = "geoserver-allow-ssh-admin"
  network       = var.network_name
  direction     = "INGRESS"
  source_ranges = [var.admin_ssh_cidr]
  target_tags   = ["geoserver"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_instance" "geoserver" {
  name         = local.vm_name
  zone         = var.zone
  machine_type = var.machine_type
  tags         = local.tags

  boot_disk {
    initialize_params {
      image = "projects/cos-cloud/global/images/family/cos-stable"
      size  = var.boot_disk_size_gb
    }
  }

  attached_disk {
    source      = google_compute_disk.geoserver_data.id
    device_name = google_compute_disk.geoserver_data.name
  }

  network_interface {
    network = var.network_name
    access_config {}
  }

  metadata_startup_script = templatefile("${path.module}/startup-geoserver.sh.tpl", {
    disk_name       = google_compute_disk.geoserver_data.name
    geoserver_image = var.geoserver_image
  })
}

resource "google_compute_instance_group" "geoserver" {
  name      = local.instance_group
  zone      = var.zone
  instances = [google_compute_instance.geoserver.self_link]

  named_port {
    name = "http"
    port = 8080
  }
}

module "https_lb" {
  source  = "terraform-google-modules/lb-http/google"
  version = "~> 12.0"

  name    = local.prefix
  project = var.project_id

  ssl                             = true
  managed_ssl_certificate_domains = [var.domain_name]
  https_redirect                  = true

  firewall_networks = [var.network_name]
  target_tags       = ["allow-health-check"]

  backends = {
    default = {
      description = "GeoServer backend"

      protocol    = "HTTP"
      port        = 8080
      port_name   = "http"
      timeout_sec = 30
      enable_cdn  = false

      health_check = {
        request_path = "/geoserver/index.html"
        port         = 8080
      }

      log_config = {
        enable      = true
        sample_rate = 1.0
      }

      groups = [
        {
          group = google_compute_instance_group.geoserver.self_link
        }
      ]

      iap_config = {
        enable = false
      }
    }
  }
}