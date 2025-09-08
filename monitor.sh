#!/bin/bash
while true; do
    clear
    echo "=== Anubis Scanner Progress ==="
    echo "Time: $(date)"
    psql "$DATABASE_URL" -c "SELECT COUNT(*) as profiles, MAX(anubis_score) as top_score, MAX(total_launches) as max_launches FROM anubis.wallet_profiles;"
    sleep 5
done
