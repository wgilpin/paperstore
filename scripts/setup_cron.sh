#!/bin/bash
# Adds the DB backup cron job if not already present.

CRON_JOB="15 3 * * * /bin/bash /Users/will/projects/paperstore/scripts/backups_script.sh"

if crontab -l 2>/dev/null | grep -qF "backups_script.sh"; then
  echo "Cron job already exists, nothing to do."
else
  (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
  echo "Cron job added: $CRON_JOB"
fi
