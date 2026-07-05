#!/bin/bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

BUCKET_NAME="${geoserver_data_bucket}"
MOUNT_POINT="${geoserver_data_mount_point}"
ONLY_DIR="${geoserver_data_only_dir}"
READ_ONLY="${geoserver_data_read_only}"
SURVEYS_BUCKET="${surveys_bucket}"
SURVEYS_MOUNT_POINT="${surveys_mount_point}"
SURVEYS_ONLY_DIR="${surveys_only_dir}"
SURVEYS_CONTAINER_MOUNT_POINT="${surveys_container_mount_point}"
MOUNT_MODE="rw"
FSTAB_OPTIONS="_netdev,allow_other,implicit_dirs,x-systemd.requires=network-online.target"
DOCKER_VOLUME_SUFFIX=""
GEOSERVER_DATA_MOUNT_PRESENT="false"
SURVEYS_MOUNT_PRESENT="false"

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

ensure_bucket_mount() {
  local bucket_name="$1"
  local mount_point="$2"
  local only_dir="$3"
  local read_only="$4"
  local mount_mode="rw"
  local fstab_options="_netdev,allow_other,implicit_dirs,x-systemd.requires=network-online.target"

  mkdir -p "$mount_point"

  if [ -n "$only_dir" ]; then
    fstab_options="$${fstab_options},only_dir=$${only_dir}"
  fi

  if [ "$read_only" = "true" ]; then
    mount_mode="ro"
  fi

  if ! grep -q "^[^#].*[[:space:]]$${mount_point}[[:space:]]gcsfuse[[:space:]]" /etc/fstab; then
    echo "$${bucket_name} $${mount_point} gcsfuse $${mount_mode},$${fstab_options} 0 0" >> /etc/fstab
  fi

  mountpoint -q "$mount_point" || mount "$mount_point"
}

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

if [ "$READ_ONLY" = "true" ]; then
  MOUNT_MODE="ro"
  DOCKER_VOLUME_SUFFIX=":ro"
fi

ensure_bucket_mount "$BUCKET_NAME" "$MOUNT_POINT" "$ONLY_DIR" "$READ_ONLY"

if [ -f "$MOUNT_POINT/global.xml" ]; then
  GEOSERVER_DATA_MOUNT_PRESENT="true"
fi

if [ -n "$SURVEYS_BUCKET" ]; then
  ensure_bucket_mount "$SURVEYS_BUCKET" "$SURVEYS_MOUNT_POINT" "$SURVEYS_ONLY_DIR" "true"
  SURVEYS_MOUNT_PRESENT="true"
fi

docker rm -f geoserver || true
retry docker pull ${geoserver_image}

COMMUNITY_EXTENSIONS="${geoserver_community_extensions}"
STABLE_EXTENSIONS="${geoserver_stable_extensions}"

docker_args=(
  -d
  --name geoserver
  --restart unless-stopped
  -p 8080:8080
  -e PROXY_BASE_URL="https://${domain_name}/geoserver"
  -e EXTRA_JAVA_OPTS="-DGEOSERVER_CSRF_WHITELIST=${domain_name}"
)

if [ -n "$COMMUNITY_EXTENSIONS" ] || [ -n "$STABLE_EXTENSIONS" ]; then
  docker_args+=(-e INSTALL_EXTENSIONS=true)
fi

if [ -n "$STABLE_EXTENSIONS" ]; then
  docker_args+=(-e STABLE_EXTENSIONS="$STABLE_EXTENSIONS")
fi

if [ -n "$COMMUNITY_EXTENSIONS" ]; then
  docker_args+=(-e COMMUNITY_EXTENSIONS="$COMMUNITY_EXTENSIONS")
fi

if [ "$GEOSERVER_DATA_MOUNT_PRESENT" = "true" ]; then
  docker_args+=(-v "$${MOUNT_POINT}:/opt/geoserver_data$${DOCKER_VOLUME_SUFFIX}")
fi

if [ "$SURVEYS_MOUNT_PRESENT" = "true" ]; then
  docker_args+=(-v "$${SURVEYS_MOUNT_POINT}:$${SURVEYS_CONTAINER_MOUNT_POINT}:ro")
fi

docker run "$${docker_args[@]}" ${geoserver_image}
