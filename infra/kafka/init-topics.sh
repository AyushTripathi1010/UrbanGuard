#!/usr/bin/env bash
set -euo pipefail

# Idempotently create the three topics UrbanGuard relies on.
# Partition counts chosen for a single-broker dev cluster on a laptop.

BROKER=${KAFKA_BROKER:-localhost:9092}
KCMD="docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server $BROKER"

create_topic() {
    local name=$1 partitions=$2 retention_ms=$3
    if $KCMD --describe --topic "$name" >/dev/null 2>&1; then
        echo "topic exists: $name"
        return
    fi
    echo "creating topic: $name (partitions=$partitions)"
    $KCMD --create \
        --topic "$name" \
        --partitions "$partitions" \
        --replication-factor 1 \
        --config retention.ms="$retention_ms"
}

create_topic raw-frames   6  21600000   # 6h retention, frame storm
create_topic alerts       3  604800000  # 7d retention, low volume
create_topic rl-feedback  3  2592000000 # 30d retention, training history

echo "topics:"
$KCMD --list
