#!/bin/bash
# chaos.sh - Chaos Engineering para JUNO AI
set -e
NAMESPACE='juno'
DURATION=60

function chaos_api() {
    echo '[CHAOS] Matando pods da API aleatoriamente...'
    kubectl -n $NAMESPACE delete pod -l app=juno-api --wait=false
    sleep $DURATION
    kubectl -n $NAMESPACE rollout status deployment/juno-api
}

function chaos_db() {
    echo '[CHAOS] Simulando latencia no PostgreSQL...'
    docker exec juno_db pgbench -U postgres -c 100 -j 10 -T $DURATION postgres
}

function chaos_network() {
    echo '[CHAOS] Simulando particao de rede...'
    docker network disconnect juno_network juno_api
    sleep $DURATION
    docker network connect juno_network juno_api
}

function chaos_memory() {
    echo '[CHAOS] Pressao de memoria...'
    docker exec juno_api stress-ng --vm 2 --vm-bytes 512M --timeout ${DURATION}s
}

case "$1" in
    api) chaos_api ;;
    db) chaos_db ;;
    network) chaos_network ;;
    memory) chaos_memory ;;
    all)
        chaos_api &
        chaos_db &
        chaos_network &
        wait
        ;;
    *)
        echo "Uso: $0 [api|db|network|memory|all]"
        exit 1
        ;;
esac

echo '[CHAOS] Experimento concluido. Verifique dashboards e logs.'
