#!/bin/bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

BUCKET_NAME="${geoserver_data_bucket}"
MOUNT_POINT="${geoserver_data_mount_point}"
ONLY_DIR="${geoserver_data_only_dir}"
READ_ONLY="${geoserver_data_read_only}"
MOUNT_MODE="rw"
FSTAB_OPTIONS="_netdev,allow_other,implicit_dirs,x-systemd.requires=network-online.target"
DOCKER_VOLUME_SUFFIX=""
GEOSERVER_DATA_MOUNT_PRESENT="false"

wait_for_apt() {
  while fuser /var/lib/dpkg/lock >/dev/null 2>&1 \
    || fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
    || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    sleep 5
  done
}

apt_retry() {
  local attempt=1
  local max_attempts=12

  while true; do
    wait_for_apt

    if "$@"; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      return 1
    fi

    attempt=$((attempt + 1))
    sleep 5
  done
}

retry() {
  local attempt=1
  local max_attempts="$${RETRY_MAX_ATTEMPTS:-5}"

  while true; do
    if "$@"; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      return 1
    fi

    attempt=$((attempt + 1))
    sleep 5
  done
}

mkdir -p "$MOUNT_POINT"

apt_retry apt-get update
apt_retry apt-get install -y ca-certificates curl gnupg lsb-release docker.io fuse

rm -f /usr/share/keyrings/cloud.google.asc
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
  | tee /usr/share/keyrings/cloud.google.asc >/dev/null

echo "deb [signed-by=/usr/share/keyrings/cloud.google.asc] https://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" \
  > /etc/apt/sources.list.d/gcsfuse.list

apt_retry apt-get update
apt_retry apt-get install -y gcsfuse

systemctl enable docker
systemctl restart docker

if ! grep -q "^user_allow_other$" /etc/fuse.conf; then
  echo "user_allow_other" >> /etc/fuse.conf
fi

if [ -n "$ONLY_DIR" ]; then
  FSTAB_OPTIONS="$${FSTAB_OPTIONS},only_dir=$${ONLY_DIR}"
fi

if [ "$READ_ONLY" = "true" ]; then
  MOUNT_MODE="ro"
  DOCKER_VOLUME_SUFFIX=":ro"
fi

if ! grep -q "^$${BUCKET_NAME}[[:space:]]" /etc/fstab; then
  echo "$${BUCKET_NAME} $${MOUNT_POINT} gcsfuse $${MOUNT_MODE},$${FSTAB_OPTIONS} 0 0" >> /etc/fstab
fi

mountpoint -q "$MOUNT_POINT" || mount "$MOUNT_POINT"

if [ -f "$MOUNT_POINT/global.xml" ]; then
  GEOSERVER_DATA_MOUNT_PRESENT="true"
fi

docker rm -f geoserver || true
retry docker pull ${geoserver_image}

docker_args=(
  -d
  --name geoserver
  --restart unless-stopped
  -p 8080:8080
  -e PROXY_BASE_URL="https://${domain_name}/geoserver"
  -e EXTRA_JAVA_OPTS="-DGEOSERVER_CSRF_WHITELIST=${domain_name}"
)

if [ "$GEOSERVER_DATA_MOUNT_PRESENT" = "true" ]; then
  docker_args+=(-v "$${MOUNT_POINT}:/opt/geoserver_data$${DOCKER_VOLUME_SUFFIX}")
fi

docker run "$${docker_args[@]}" ${geoserver_image}
