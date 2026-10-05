#!/bin/bash
set -euo pipefail

# ============================================================
# Automated Daily Backups: MongoDB → Google Cloud Storage
# Run this ON the VM after migration is verified
# ============================================================

# --- CONFIGURATION (update from install script output) ---
MONGO_USER="cloudfinops_app"        # cloudfinops_app
MONGO_PASS="0bB5QOnNdR45wGjjn2zllRMf"        # (from install script)
MONGO_DB="cloudfinops"
GCS_BUCKET="cloudfinops-mongodb-backups"
PROJECT_ID="cloudfinops-test-001"
RETENTION_DAYS=7
# ---------------------------------------------------------

echo "=== Setting up Automated MongoDB Backups ==="

# Validate inputs
if [ -z "$MONGO_USER" ] || [ -z "$MONGO_PASS" ]; then
  echo "ERROR: Please fill in MONGO_USER and MONGO_PASS"
  exit 1
fi

# Step 1: Verify GCS bucket access
echo "[1/4] Verifying GCS bucket access..."
gsutil ls "gs://$GCS_BUCKET/" > /dev/null 2>&1 \
  && echo "  Bucket accessible: gs://$GCS_BUCKET" \
  || { echo "  ERROR: Cannot access gs://$GCS_BUCKET. Run bucket setup from local machine."; exit 1; }

# Step 2: Create backup script
echo "[2/4] Creating backup script..."
sudo tee /opt/mongodb-backup.sh > /dev/null <<SCRIPT
#!/bin/bash
set -euo pipefail

TIMESTAMP=\$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/tmp/mongodb-backup-\$TIMESTAMP"
LOG_FILE="/var/log/mongodb-backup.log"

echo "[\$TIMESTAMP] Starting backup..." >> "\$LOG_FILE"

# Dump
mongodump \\
  --uri="mongodb://${MONGO_USER}:${MONGO_PASS}@localhost:27017/${MONGO_DB}?authSource=admin" \\
  --out="\$BACKUP_DIR" \\
  --gzip \\
  --numParallelCollections=2 \\
  2>> "\$LOG_FILE"

# Upload to GCS
gsutil -m cp -r "\$BACKUP_DIR" "gs://${GCS_BUCKET}/\$TIMESTAMP/" 2>> "\$LOG_FILE"

# Cleanup local
rm -rf "\$BACKUP_DIR"

echo "[\$TIMESTAMP] Backup complete. Uploaded to gs://${GCS_BUCKET}/\$TIMESTAMP/" >> "\$LOG_FILE"
SCRIPT

sudo chmod +x /opt/mongodb-backup.sh

# Step 3: Setup cron (daily at 3:30 AM UTC)
echo "[3/4] Setting up daily cron job..."
(sudo crontab -l 2>/dev/null | grep -v mongodb-backup; echo "30 3 * * * /opt/mongodb-backup.sh") | sudo crontab -
echo "  Scheduled: Daily at 3:30 AM UTC"

# Step 4: Run first backup now
echo "[4/4] Running first backup..."
sudo /opt/mongodb-backup.sh && echo "  First backup: SUCCESS" || echo "  First backup: FAILED"

# Verify
echo ""
echo "=== Backup Setup Complete ==="
echo "Bucket:    gs://$GCS_BUCKET"
echo "Schedule:  Daily at 3:30 AM UTC"
echo "Retention: $RETENTION_DAYS days (auto-deleted)"
echo ""
echo "Manual backup:  sudo /opt/mongodb-backup.sh"
echo "Check backups:  gsutil ls gs://$GCS_BUCKET/"
echo "View logs:      tail -20 /var/log/mongodb-backup.log"
