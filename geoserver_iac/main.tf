locals {
  prefix          = "geoserver"
  vm_name         = "geoserver-proto-01"
  instance_group  = "geoserver-ig"
  service_account = "geoserver-vm"
  tags            = ["geoserver", "allow-health-check"]
}

resource "google_project_service" "compute" {
  service = "compute.googleapis.com"
}

resource "google_project_service" "storage" {
  service = "storage.googleapis.com"
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
      image = var.instance_image
      size  = var.boot_disk_size_gb
    }
  }

  network_interface {
    network = var.network_name
    access_config {}
  }

  service_account {
    email  = google_service_account.geoserver_vm.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/startup-geoserver.sh.tpl", {
    domain_name                    = var.domain_name
    geoserver_data_bucket          = var.geoserver_data_bucket
    geoserver_data_mount_point     = var.geoserver_data_mount_point
    geoserver_data_only_dir        = var.geoserver_data_only_dir
    geoserver_data_read_only       = var.geoserver_data_read_only
    geoserver_image                = var.geoserver_image
    geoserver_community_extensions = var.geoserver_community_extensions
    geoserver_stable_extensions    = var.geoserver_stable_extensions
    surveys_bucket                 = var.surveys_bucket
    surveys_container_mount_point  = var.surveys_container_mount_point
    surveys_mount_point            = var.surveys_mount_point
    surveys_only_dir               = var.surveys_only_dir
  })

  depends_on = [
    google_project_service.compute,
    google_project_service.storage,
    google_storage_bucket_iam_member.geoserver_data_viewer,
    google_storage_bucket_iam_member.geoserver_surveys_viewer,
  ]
}

resource "google_compute_instance_group" "geoserver" {
  name = local.instance_group
  zone = var.zone

  named_port {
    name = "http"
    port = 8080
  }
}

resource "google_compute_instance_group_membership" "geoserver" {
  instance_group = google_compute_instance_group.geoserver.name
  instance       = google_compute_instance.geoserver.self_link
  zone           = var.zone
}

resource "google_project_service" "servicenetworking" {
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

data "google_compute_network" "default" {
  name = var.network_name
}

resource "google_service_account" "geoserver_vm" {
  account_id   = local.service_account
  display_name = "GeoServer VM service account"
}

resource "google_storage_bucket_iam_member" "geoserver_data_viewer" {
  bucket     = var.geoserver_data_bucket
  role       = "roles/storage.objectViewer"
  member     = "serviceAccount:${google_service_account.geoserver_vm.email}"
  depends_on = [google_project_service.storage]
}

resource "google_storage_bucket_iam_member" "geoserver_surveys_viewer" {
  count      = var.surveys_bucket != "" ? 1 : 0
  bucket     = var.surveys_bucket
  role       = "roles/storage.objectViewer"
  member     = "serviceAccount:${google_service_account.geoserver_vm.email}"
  depends_on = [google_project_service.storage]
}

resource "google_project_iam_member" "geoserver_vm_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.geoserver_vm.email}"
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
