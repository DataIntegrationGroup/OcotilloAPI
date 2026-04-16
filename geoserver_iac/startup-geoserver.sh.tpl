#!/bin/bash
set -euxo pipefail

DEVICE="/dev/disk/by-id/google-${disk_name}"
MOUNT_POINT="/mnt/disks/geoserver-data"

mkdir -p "$MOUNT_POINT"

if ! blkid "$DEVICE"; then
  mkfs.ext4 -F "$DEVICE"
fi

mount "$DEVICE" "$MOUNT_POINT"

mkdir -p "$MOUNT_POINT/data_dir"

docker rm -f geoserver || true
docker pull ${geoserver_image}

docker run -d   --name geoserver   --restart unless-stopped   -p 8080:8080   -v "$MOUNT_POINT/data_dir:/opt/geoserver_data"   ${geoserver_image}
