output "load_balancer_ip" {
  value = module.https_lb.external_ip
}

output "geoserver_url" {
  value = "https://${var.domain_name}/geoserver"
}
