#!/bin/bash
set -euo pipefail

# ============================================================
# MongoDB 8.0 Community Edition Installation & Hardening
# Run this ON the VM after SSH-ing in:
#   gcloud compute ssh mongodb-server --zone=us-central1-a
# ============================================================

MONGO_VERSION="8.0"
MONGO_DB_NAME="cloudfinops"
MONGO_ADMIN_USER="cloudfinops_admin"
MONGO_ADMIN_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
MONGO_APP_USER="cloudfinops_app"
MONGO_APP_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

echo "=== MongoDB $MONGO_VERSION Installation ==="

# Step 1: Install MongoDB 8.0
echo "[1/6] Adding MongoDB repository..."
sudo apt-get update -qq
sudo apt-get install -y gnupg curl

curl -fsSL https://www.mongodb.org/static/pgp/server-${MONGO_VERSION}.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-${MONGO_VERSION}.gpg --dearmor

echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-${MONGO_VERSION}.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/${MONGO_VERSION} multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-${MONGO_VERSION}.list

sudo apt-get update -qq
sudo apt-get install -y mongodb-org

echo "[2/6] Configuring MongoDB..."

# Step 2: Configure MongoDB
sudo tee /etc/mongod.conf > /dev/null <<'EOF'
# MongoDB 8.0 Configuration for CloudFinOps (auth disabled for initial user creation)

storage:
  dbPath: /var/lib/mongodb
  wiredTiger:
    engineConfig:
      cacheSizeGB: 4
      journalCompressor: snappy
    collectionConfig:
      blockCompressor: snappy

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log
  logRotate: reopen

net:
  port: 27017
  bindIp: 127.0.0.1
  maxIncomingConnections: 200

processManagement:
  timeZoneInfo: /usr/share/zoneinfo
  fork: false

operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp
EOF

# Step 3: Setup logrotate
echo "[3/6] Setting up log rotation..."
sudo tee /etc/logrotate.d/mongodb > /dev/null <<'EOF'
/var/log/mongodb/mongod.log {
  daily
  rotate 7
  compress
  missingok
  notifempty
  sharedscripts
  postrotate
    /bin/kill -SIGUSR1 $(cat /var/lib/mongodb/mongod.lock 2>/dev/null) 2>/dev/null || true
  endscript
}
EOF

# Step 4: Start MongoDB (without auth first to create users)
echo "[4/6] Starting MongoDB and creating users..."
sudo systemctl daemon-reload
sudo systemctl enable mongod
sudo systemctl start mongod

sleep 3

# Create admin user
mongosh --quiet <<EOJS
use admin
db.createUser({
  user: "${MONGO_ADMIN_USER}",
  pwd: "${MONGO_ADMIN_PASS}",
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" },
    { role: "dbAdminAnyDatabase", db: "admin" },
    { role: "clusterMonitor", db: "admin" }
  ]
})
EOJS

# Create application user
mongosh --quiet <<EOJS
use admin
db.createUser({
  user: "${MONGO_APP_USER}",
  pwd: "${MONGO_APP_PASS}",
  roles: [
    { role: "readWrite", db: "${MONGO_DB_NAME}" },
    { role: "dbAdmin", db: "${MONGO_DB_NAME}" }
  ]
})
EOJS

# Step 5: Enable auth and open to network, then restart
echo "[5/6] Enabling authentication and restarting..."
sudo tee /etc/mongod.conf > /dev/null <<'EOF'
# MongoDB 8.0 Configuration for CloudFinOps (production)

storage:
  dbPath: /var/lib/mongodb
  wiredTiger:
    engineConfig:
      cacheSizeGB: 4
      journalCompressor: snappy
    collectionConfig:
      blockCompressor: snappy

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log
  logRotate: reopen

net:
  port: 27017
  bindIp: 0.0.0.0
  maxIncomingConnections: 200

processManagement:
  timeZoneInfo: /usr/share/zoneinfo
  fork: false

security:
  authorization: enabled

operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp
EOF

sudo systemctl restart mongod
sleep 3

# Verify auth works
mongosh --quiet -u "$MONGO_ADMIN_USER" -p "$MONGO_ADMIN_PASS" --authenticationDatabase admin --eval "db.adminCommand('ping')" \
  && echo "  Auth verification: SUCCESS" \
  || echo "  Auth verification: FAILED"

# Step 6: Setup swap (safety net for memory pressure)
echo "[6/6] Configuring swap..."
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# Optimize kernel for MongoDB
sudo tee /etc/sysctl.d/99-mongodb.conf > /dev/null <<'EOF'
vm.swappiness=1
net.core.somaxconn=65535
net.ipv4.tcp_keepalive_time=120
EOF
sudo sysctl --system > /dev/null 2>&1

# Print credentials
echo ""
echo "============================================"
echo "=== MongoDB Installation Complete ==="
echo "============================================"
echo ""
echo "SAVE THESE CREDENTIALS SECURELY:"
echo ""
echo "  Admin User:       $MONGO_ADMIN_USER"
echo "  Admin Password:   $MONGO_ADMIN_PASS"
echo ""
echo "  App User:         $MONGO_APP_USER"
echo "  App Password:     $MONGO_APP_PASS"
echo "  Database:         $MONGO_DB_NAME"
echo ""
echo "CONNECTION STRING (for backend .env):"
EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
echo "  MONGODB_URI=mongodb://${MONGO_APP_USER}:${MONGO_APP_PASS}@${EXTERNAL_IP}:27017/${MONGO_DB_NAME}?authSource=admin&directConnection=true"
echo ""
echo "Next step: Run 03-migrate-data.sh from your local machine"
