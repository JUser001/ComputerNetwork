#!/usr/bin/env bash
set -euo pipefail

# Run this script from the repository root. Docker Compose controls the three
# FRR routers, while this script records their OSPF routes around each change.
COMPOSE=(docker compose --profile routing)
OUT="w06-routing/out"
mkdir -p "$OUT"

capture_routes() {
  local destination="$1"
  : > "$destination"
  for router in r1 r2 r3; do
    {
      printf '===== %s =====\n' "$router"
      "${COMPOSE[@]}" exec -T "$router" vtysh -c 'show ip route ospf' 2>/dev/null || true
      printf '\n'
    } >> "$destination"
  done
}

# Ignore route age fields, which change every second even when routing is stable.
r1_snapshot() {
  "${COMPOSE[@]}" exec -T r1 vtysh -c 'show ip route ospf' 2>/dev/null \
    | sed -E 's/, [0-9]{2}:[0-9]{2}:[0-9]{2}//g'
}

wait_for_change() {
  local previous="$1" start="$2" label="$3" elapsed current
  for elapsed in $(seq 1 60); do
    sleep 1
    current="$(r1_snapshot)"
    if [[ "$current" != "$previous" ]]; then
      printf '%s: R1 OSPF route changed after about %s seconds\n' "$label" "$elapsed"
      return 0
    fi
  done
  printf '%s: no R1 route change detected within 60 seconds\n' "$label" >&2
  return 1
}

case "${1:-}" in
  up)
    "${COMPOSE[@]}" up -d
    echo 'Waiting 30 seconds for OSPF neighbors to form...'
    sleep 30
    for router in r1 r2 r3; do
      echo "===== $router OSPF neighbors ====="
      "${COMPOSE[@]}" exec -T "$router" vtysh -c 'show ip ospf neighbor' 2>/dev/null || true
    done
    ;;
  routes)
    capture_routes "$OUT/routes-current.txt"
    cat "$OUT/routes-current.txt"
    ;;
  cut)
    capture_routes "$OUT/route-before.txt"
    before="$(r1_snapshot)"
    start="$(date +%s)"
    # In this lab, r1 eth1 is the link from r1 to r2.
    "${COMPOSE[@]}" exec -T r1 ip link set eth1 down
    wait_for_change "$before" "$start" 'Link failure' | tee "$OUT/reconverge.txt"
    sleep 2
    capture_routes "$OUT/route-after.txt"
    echo "Saved all three routers' OSPF tables before and after the link failure."
    ;;
  restore)
    before="$(r1_snapshot)"
    start="$(date +%s)"
    "${COMPOSE[@]}" exec -T r1 ip link set eth1 up
    wait_for_change "$before" "$start" 'Link restoration' | tee -a "$OUT/reconverge.txt"
    sleep 2
    capture_routes "$OUT/route-restored.txt"
    echo "Saved restored OSPF tables to $OUT/route-restored.txt"
    ;;
  cost)
    capture_routes "$OUT/route-cost-before.txt"
    before="$(r1_snapshot)"
    start="$(date +%s)"
    "${COMPOSE[@]}" exec -T r1 vtysh -c 'configure terminal' \
      -c 'interface eth0' -c 'ip ospf cost 100' -c 'end' 2>/dev/null
    wait_for_change "$before" "$start" 'OSPF cost change' | tee -a "$OUT/reconverge.txt"
    sleep 2
    capture_routes "$OUT/route-cost-after.txt"
    echo "Saved all three routers' OSPF tables before and after the cost change."
    ;;
  down)
    "${COMPOSE[@]}" down
    ;;
  *)
    echo "Usage: bash w06-routing/scenario.sh {up|routes|cut|restore|cost|down}" >&2
    exit 2
    ;;
esac
