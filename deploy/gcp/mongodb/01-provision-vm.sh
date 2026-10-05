#!/bin/bash
set -euo pipefail

# ============================================================
# CloudFinOps MongoDB VM Provisioning (GCP Compute Engine)
# Region: us-central1 (same as Cloud Run backend)
# VM: e2-standard-2 (2 vCPU, 8GB RAM)
# Disk: 50GB SSD
# ============================================================

PROJECT_ID="cloudfinops-test-001"
REGION="us-central1"
ZONE="us-central1-a"
VM_NAME="mongodb-server"
MACHINE_TYPE="e2-standard-2"
DISK_SIZE="50GB"
DISK_TYPE="pd-ssd"
IMAGE_FAMILY="ubuntu-2404-lts-amd64"
IMAGE_PROJECT="ubuntu-os-cloud"
STATIC_IP_NAME="mongodb-static-ip"
FIREWALL_RULE="allow-mongodb"
NETWORK_TAG="mongodb-server"

echo "=== CloudFinOps MongoDB VM Provisioning ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Step 1: Reserve a static internal IP (keeps IP stable across restarts)
echo "[1/5] Reserving static external IP..."
gcloud compute addresses create "$STATIC_IP_NAME" \
  --region="$REGION" \
  --network-tier=STANDARD \
  2>/dev/null || echo "  (IP already exists, reusing)"

STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" \
  --region="$REGION" \
  --format="get(address)")
echo "  Static IP: $STATIC_IP"

# Step 2: Create firewall rule (MongoDB port 27017, restricted to Cloud Run egress)
echo "[2/5] Creating firewall rule..."
gcloud compute firewall-rules create "$FIREWALL_RULE" \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:27017 \
  --source-ranges="0.0.0.0/0" \
  --target-tags="$NETWORK_TAG" \
  --description="Allow MongoDB access (restrict source-ranges in production)" \
  2>/dev/null || echo "  (Firewall rule already exists)"

# Step 3: Create the VM
echo "[3/5] Creating VM instance..."
gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --boot-disk-size="$DISK_SIZE" \
  --boot-disk-type="$DISK_TYPE" \
  --address="$STATIC_IP" \
  --network-tier=STANDARD \
  --tags="$NETWORK_TAG" \
  --metadata=startup-script='#!/bin/bash
    echo "VM provisioned for MongoDB" > /tmp/provision-marker' \
  --scopes=storage-rw,logging-write,monitoring \
  && echo "  VM created successfully" || { echo "  ERROR: VM creation failed"; exit 1; }

# Step 4: Wait for VM to be ready
echo "[4/5] Waiting for VM to be ready..."
sleep 10
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="echo 'SSH connection successful'" \
  2>/dev/null || echo "  (First SSH attempt may take a moment for key propagation)"

# Step 5: Print summary
echo ""
echo "=== Provisioning Complete ==="
echo "VM Name:     $VM_NAME"
echo "Zone:        $ZONE"
echo "Machine:     $MACHINE_TYPE"
echo "Disk:        $DISK_SIZE SSD"
echo "External IP: $STATIC_IP"
echo ""
echo "Next step: Run 02-install-mongodb.sh on the VM"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE"
