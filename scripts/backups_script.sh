#!/bin/bash
# ~/scripts/backup-dbs.sh

export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.orbstack/bin"

BACKUP_DIR=~/backups/postgres
LOG_FILE="$BACKUP_DIR/backup.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETAIN_DAYS=14

mkdir -p "$BACKUP_DIR"
exec >> "$LOG_FILE" 2>&1

dump() {
  local container=$1 user=$2 db=$3
  local out="$BACKUP_DIR/${db}_${TIMESTAMP}.dump"
  docker exec "$container" pg_dump -U "$user" -Fc "$db" > "$out"
  echo "$(date): backed up $db → $out ($(du -sh "$out" | cut -f1))"
}

dump willbot-willbot_db-1   willbot    willbot
dump paperstore-db-1        paperstore paperstore

# Rotate old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETAIN_DAYS -delete
echo "$(date): rotation done (kept last ${RETAIN_DAYS} days)"
