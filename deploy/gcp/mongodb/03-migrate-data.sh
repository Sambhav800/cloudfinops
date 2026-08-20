#!/bin/bash
set -euo pipefail

# ============================================================
# Data Migration: MongoDB Atlas → GCE VM
# Run this from your LOCAL machine (needs mongodump/mongorestore)
# ============================================================

# --- CONFIGURATION (update these) ---
ATLAS_URI="mongodb+srv://sambhav_db_user:yp4TFmgeJzOvyYR4@cluster0.lykdg0n.mongodb.net"
ATLAS_DB="cloudfinops"

# These will be output by 02-install-mongodb.sh — paste them here
NEW_HOST="35.209.72.83"          
NEW_USER="cloudfinops_app"          # cloudfinops_app
NEW_PASS="0bB5QOnNdR45wGjjn2zllRMf"          # (from install script output)
NEW_DB="cloudfinops"

DUMP_DIR="/tmp/mongodb-migration-$(date +%Y%m%d-%H%M%S)"
# ------------------------------------

echo "=== CloudFinOps MongoDB Migration ==="
echo "Source: Atlas (cluster0.lykdg0n.mongodb.net)"
echo "Target: GCE VM ($NEW_HOST)"
echo ""

# Validate inputs
if [ -z "$NEW_HOST" ] || [ -z "$NEW_USER" ] || [ -z "$NEW_PASS" ]; then
  echo "ERROR: Please fill in NEW_HOST, NEW_USER, and NEW_PASS from the install script output"
  exit 1
fi

# Step 1: Check tools
echo "[1/5] Checking prerequisites..."
command -v mongodump >/dev/null 2>&1 || {
  echo "ERROR: mongodump not found. Install MongoDB Database Tools:"
  echo "  brew install mongodb-database-tools  (macOS)"
  echo "  apt install mongodb-database-tools   (Ubuntu)"
  exit 1
}
command -v mongorestore >/dev/null 2>&1 || {
  echo "ERROR: mongorestore not found."
  exit 1
}

# Step 2: Dump from Atlas
echo "[2/5] Dumping data from Atlas..."
mkdir -p "$DUMP_DIR"
mongodump \
  --uri="$ATLAS_URI/$ATLAS_DB" \
  --out="$DUMP_DIR" \
  --gzip \
  --numParallelCollections=4

echo "  Dump complete. Size: $(du -sh "$DUMP_DIR" | cut -f1)"

# List collections dumped
echo "  Collections:"
ls "$DUMP_DIR/$ATLAS_DB/" | sed 's/\..*$//' | sort -u | sed 's/^/    - /'

# Step 3: Restore to new server (mongorestore will fail if connection is bad)
echo "[3/5] Restoring data to GCE MongoDB..."
mongorestore \
  --uri="mongodb://${NEW_USER}:${NEW_PASS}@${NEW_HOST}:27017/?authSource=admin&directConnection=true" \
  --db="$NEW_DB" \
  --dir="$DUMP_DIR/$ATLAS_DB" \
  --gzip \
  --numParallelCollections=4 \
  --drop

echo ""
echo "[4/5] Restore complete."

# Step 5: Verify (via mongorestore output above — manual check on VM)
echo "[5/5] To verify counts, SSH into the VM and run:"
echo "  mongosh -u cloudfinops_app -p YOUR_PASS --authenticationDatabase admin cloudfinops --eval 'db.getCollectionNames().forEach(c => print(c, db[c].countDocuments({})))'"
echo ""

# Cleanup
echo "Migration dump preserved at: $DUMP_DIR"
echo "(Delete with: rm -rf $DUMP_DIR)"
echo ""
echo "=== Migration Complete ==="
echo ""
echo "NEW CONNECTION STRING for your backend:"
echo "  MONGODB_URI=mongodb://${NEW_USER}:${NEW_PASS}@${NEW_HOST}:27017/${NEW_DB}?authSource=admin&directConnection=true"
echo ""
echo "Next steps:"
echo "  1. Update backend/.env with the new MONGODB_URI"
echo "  2. Update Cloud Run secret/env var"
echo "  3. Test the application"
echo "  4. Run 04-setup-backups.sh on the VM"
