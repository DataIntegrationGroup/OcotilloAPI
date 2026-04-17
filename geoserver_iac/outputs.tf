output "load_balancer_ip" {
  value = module.https_lb.external_ip
}

output "geoserver_url" {
  value = "https://${var.domain_name}/geoserver"
}

output "geoserver_data_bucket" {
  value = var.geoserver_data_bucket
}

output "geoserver_data_mount_prefix" {
  value = var.geoserver_data_only_dir
}

output "surveys_bucket" {
  value = var.surveys_bucket
}

output "surveys_mount_prefix" {
  value = var.surveys_only_dir
}
