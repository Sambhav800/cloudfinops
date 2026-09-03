# MongoDB Migration Runbook: Atlas → GCE VM

**Estimated time:** 20-30 minutes  
**Cost:** ~$60/month from GCP credits ($2500 credits = 40+ months runway)

---

## Prerequisites

- [x] gcloud CLI authenticated (`gcloud auth login`)
- [ ] MongoDB Database Tools installed locally (`mongodump`, `mongorestore`)

Install if needed:
```bash
brew install mongodb-database-tools
```

---

## Step 1: Provision the VM (from your local machine)

```bash
cd deploy/gcp/mongodb
chmod +x *.sh
./01-provision-vm.sh
```

This creates:
- Static IP in us-central1
- Firewall rule for port 27017
- e2-standard-2 VM (2 vCPU, 8GB RAM, 50GB SSD)

**Save the Static IP** that gets printed — you'll need it later.

---

## Step 2: Install MongoDB on the VM

SSH into the VM:
```bash
gcloud compute ssh mongodb-server --zone=us-central1-a
```

Once on the VM, copy and run the install script:
```bash
# From within the SSH session on the VM:
curl -sL https://raw.githubusercontent.com/YOUR_REPO/main/deploy/gcp/mongodb/02-install-mongodb.sh | bash
```

Or copy the file to the VM first:
```bash
# From your local machine:
gcloud compute scp deploy/gcp/mongodb/02-install-mongodb.sh mongodb-server:~ --zone=us-central1-a

# Then SSH in and run:
gcloud compute ssh mongodb-server --zone=us-central1-a
chmod +x 02-install-mongodb.sh
./02-install-mongodb.sh
```

**IMPORTANT: Save the credentials printed at the end!** You'll need:
- App user password
- The full connection string

---

## Step 3: Migrate Data (from your local machine)

Edit `03-migrate-data.sh` and fill in:
- `NEW_HOST` — the static IP from Step 1
- `NEW_USER` — `cloudfinops_app`
- `NEW_PASS` — password from Step 2

Then run:
```bash
./03-migrate-data.sh
```

The script will:
1. Dump all data from Atlas (compressed)
2. Restore to the new VM
3. Print document counts from both servers for verification

---

## Step 4: Update Application Config

### Local development:
```bash
# In backend/.env, replace the MONGODB_URI line:
MONGODB_URI=mongodb://cloudfinops_app:YOUR_PASS@YOUR_IP:27017/cloudfinops?authSource=admin&directConnection=true
```

### Cloud Run (production):
```bash
gcloud run services update cloudfinops-backend \
  --region=us-central1 \
  --update-env-vars="MONGODB_URI=mongodb://cloudfinops_app:YOUR_PASS@YOUR_IP:27017/cloudfinops?authSource=admin&directConnection=true"
```

---

## Step 5: Verify Application

1. Start your backend locally:
   ```bash
   cd backend && source venv/bin/activate && uvicorn app.main:app --reload
   ```
2. Check the dashboard loads with real data
3. Test a scan operation
4. Verify all collections have correct counts

---

## Step 6: Setup Automated Backups

SSH into the VM:
```bash
gcloud compute ssh mongodb-server --zone=us-central1-a
```

Edit `04-setup-backups.sh` with your credentials, then run it. This sets up:
- Daily backups at 3:30 AM UTC to GCS
- 7-day retention (auto-deleted)
- Manual backup command: `sudo /opt/mongodb-backup.sh`

---

## Step 7: (Optional) Restrict Firewall

Once everything works, lock down the firewall to only allow your Cloud Run service:

```bash
# Get Cloud Run egress IP range (if using VPC connector)
# Or restrict to your VM's own VPC:
gcloud compute firewall-rules update allow-mongodb \
  --source-ranges="YOUR_CLOUD_RUN_VPC_RANGE"
```

---

## Rollback Plan

If anything goes wrong, you can instantly switch back to Atlas:
```bash
# Just restore the original URI in backend/.env:
MONGODB_URI=mongodb+srv://sambhav_db_user:yp4TFmgeJzOvyYR4@cluster0.lykdg0n.mongodb.net/?appName=Cluster0
```

Atlas data is read-only (credits exhausted) but still accessible for reads until the cluster is deleted.

---

## Monthly Cost Breakdown

| Resource | Monthly Cost |
|----------|-------------|
| e2-standard-2 VM | ~$49 |
| 50GB SSD disk | ~$8.50 |
| GCS backup bucket | ~$1 |
| Network egress (minimal) | ~$1 |
| **Total** | **~$60/mo** |

With $2,500 GCP credits: **~40 months of free hosting**

---

## Monitoring

Check VM health:
```bash
gcloud compute ssh mongodb-server --zone=us-central1-a -- "mongosh -u cloudfinops_admin -p YOUR_ADMIN_PASS --authenticationDatabase admin --eval 'db.serverStatus().connections'"
```

Check backup status:
```bash
gsutil ls gs://cloudfinops-mongodb-backups/ | tail -5
```
