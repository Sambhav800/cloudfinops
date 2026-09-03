---
pdf_options:
  margin: 25mm
  format: A4
  headerTemplate: '<div style="width:100%;font-size:8px;color:#6366f1;text-align:right;padding-right:25mm;">CloudFinOps Solutions Pvt. Ltd. | Confidential</div>'
  footerTemplate: '<div style="width:100%;font-size:8px;color:#999;text-align:center;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>'
  displayHeaderFooter: true
stylesheet: https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown.min.css
body_class: markdown-body
---

<div style="text-align:center;padding:60px 0 40px 0;">
<img src="../public/logo-main.png" width="220" />
<h1 style="margin-top:30px;font-size:32px;color:#1e293b;">INFRASTRUCTURE REQUIREMENTS</h1>
<h2 style="color:#6366f1;font-weight:500;margin-top:10px;">On Premise Deployment Specification</h2>
<p style="font-size:16px;color:#64748b;margin-top:20px;">CloudFinOps × IFFCO Kisan Finance</p>
<br/><br/>
<table style="margin:0 auto;text-align:left;font-size:14px;border:none;">
<tr><td style="color:#64748b;padding:4px 20px;">Document Version:</td><td>1.0</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Date:</td><td>June 2026</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Classification:</td><td style="color:#dc2626;">Confidential</td></tr>
<tr><td style="color:#64748b;padding:4px 20px;">Prepared by:</td><td>Nishant Jain, CTO</td></tr>
</table>
</div>

<div style="page-break-after: always;"></div>

## 1. DEPLOYMENT OVERVIEW

CloudFinOps is deployed as a **self contained Dockerized application** within IFFCO's internal infrastructure. The platform consists of three components running as Docker containers:

| Component | Technology | Image Size | Purpose |
|-----------|-----------|------------|---------|
| Frontend | Next.js 16 (Node 20) | ~350 MB | Web dashboard and user interface |
| Backend | FastAPI (Python 3.11) | ~450 MB | Scanning engine, AI verification, intelligence |
| Database | MongoDB 7.0 | ~700 MB | Persistent storage for resources, metrics, credentials |

**Key principle:** No external SaaS dependency. All data processing, storage, and visualization happens within IFFCO's network perimeter. The only outbound traffic is HTTPS calls to Azure management APIs for resource scanning.

<div style="page-break-after: always;"></div>

## 2. HARDWARE REQUIREMENTS

### Minimum Specification (POC: up to 500 resources)

| Resource | Specification |
|----------|--------------|
| CPU | 4 vCPUs (x86_64 architecture) |
| RAM | 8 GB |
| Storage | 50 GB SSD |
| Operating System | Ubuntu 22.04 LTS, RHEL 8+, or Windows Server 2022 with WSL2 |
| Container Runtime | Docker Engine 24+ or Podman 4+ |
| Network | 100 Mbps NIC with outbound internet access |

### Recommended Specification (Production: up to 5,000 resources)

| Resource | Specification |
|----------|--------------|
| CPU | 8 vCPUs (x86_64 architecture) |
| RAM | 16 GB |
| Storage | 100 GB NVMe SSD |
| Operating System | Ubuntu 22.04 LTS or RHEL 8+ |
| Container Runtime | Docker Engine 24+ with Docker Compose v2 |
| MongoDB | Dedicated replica set (3 nodes) for high availability |
| Network | 1 Gbps NIC |

### Kubernetes Deployment (Optional, for HA)

| Resource | Specification |
|----------|--------------|
| Cluster | 3 worker nodes: 4 vCPU, 8 GB RAM each |
| Ingress | NGINX Ingress Controller or Azure Application Gateway |
| Storage | Persistent Volume (50 GB minimum) for MongoDB |
| Namespace | Dedicated namespace: `cloudfinops` |
| Helm | v3.12+ for chart based deployment |

<div style="page-break-after: always;"></div>

## 3. NETWORK REQUIREMENTS

### Outbound Access (Required)

The platform requires outbound HTTPS (port 443) access to the following Azure endpoints:

| Destination | Purpose | Protocol |
|-------------|---------|----------|
| `login.microsoftonline.com` | Azure AD authentication for Service Principal | HTTPS 443 |
| `management.azure.com` | Azure Resource Manager (resource inventory and configuration) | HTTPS 443 |
| `monitor.azure.com` | Azure Monitor (CPU, memory, network, disk metrics) | HTTPS 443 |
| `prices.azure.com` | Azure Retail Pricing API (cost comparison data) | HTTPS 443 |
| `management.core.windows.net` | Azure Cost Management (billing and spend data) | HTTPS 443 |

### Optional Outbound (AI Verification)

| Destination | Purpose | Can Be Disabled? |
|-------------|---------|-----------------|
| `generativelanguage.googleapis.com` | Gemini AI for intelligent resource classification | Yes |

> **If Gemini access is not permitted:** The platform falls back to deterministic rule based classification. All scanning and waste detection continues to function. AI adds confidence scoring and natural language narratives but is not required for core functionality.

### Inbound Access

| Source | Port | Purpose |
|--------|------|---------|
| IFFCO internal users (browser) | 3000 (or 443 via reverse proxy) | Web dashboard access |

**No inbound connections from the internet are required.**

<div style="page-break-after: always;"></div>

## 4. ARCHITECTURE DIAGRAM

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:30px;margin:20px 0;">

**Internal Network Topology**

```
┌────────────────────────────────────────────────────────────────────┐
│                    IFFCO INTERNAL NETWORK                            │
│                                                                      │
│   ┌──────────────┐         ┌─────────────────────────────────┐     │
│   │              │  HTTPS  │      CloudFinOps Platform        │     │
│   │  IFFCO Users │ ──────► │                                  │     │
│   │  (Browsers)  │  :3000  │  ┌───────────┐  ┌───────────┐  │     │
│   │              │         │  │ Frontend  │  │  Backend  │  │     │
│   └──────────────┘         │  │ Next.js   │──│  FastAPI  │  │     │
│                             │  └───────────┘  └─────┬─────┘  │     │
│                             │                       │         │     │
│                             │                ┌──────▼──────┐  │     │
│                             │                │   MongoDB   │  │     │
│                             │                │  (internal) │  │     │
│                             │                └─────────────┘  │     │
│                             └──────────────────┬──────────────┘     │
│                                                │                     │
│                                     Outbound HTTPS :443              │
│                                                │                     │
└────────────────────────────────────────────────┼─────────────────────┘
                                                 │
                                                 ▼
                              ┌──────────────────────────────────┐
                              │       Azure Management APIs       │
                              │  (management.azure.com)           │
                              │  (monitor.azure.com)              │
                              │  (login.microsoftonline.com)      │
                              │  (prices.azure.com)               │
                              └──────────────────────────────────┘
```

</div>

<div style="page-break-after: always;"></div>

## 5. AZURE PERMISSIONS REQUIRED

### Service Principal Configuration

IFFCO Azure Admin creates a Service Principal with the following **read only** roles:

| Role | Scope | Purpose |
|------|-------|---------|
| `Reader` | Subscription | Read all resource metadata and configurations |
| `Cost Management Reader` | Subscription | Access actual billing and cost data |
| `Monitoring Reader` | Subscription | Access Azure Monitor metrics (CPU, memory, network) |

### Creation Commands

```bash
# Step 1: Create Service Principal with Reader role
az ad sp create-for-rbac \
  --name "CloudFinOps-Reader" \
  --role "Reader" \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>

# Step 2: Add Cost Management Reader role
az role assignment create \
  --assignee <APP_ID_FROM_STEP_1> \
  --role "Cost Management Reader" \
  --scope /subscriptions/<YOUR_SUBSCRIPTION_ID>

# Step 3: Add Monitoring Reader role
az role assignment create \
  --assignee <APP_ID_FROM_STEP_1> \
  --role "Monitoring Reader" \
  --scope /subscriptions/<YOUR_SUBSCRIPTION_ID>
```

### Security Guarantee: What This CANNOT Do

| Action | Permitted? |
|--------|-----------|
| Read resource metadata and configuration | Yes |
| Read cost and billing data | Yes |
| Read performance metrics (CPU, memory) | Yes |
| Create, modify, or delete any Azure resource | **No** |
| Access VM file systems or SSH into machines | **No** |
| Read secrets from Key Vault | **No** |
| Modify IAM or RBAC permissions | **No** |
| Access application data inside databases | **No** |
| Read blob or file content inside storage accounts | **No** |

<div style="page-break-after: always;"></div>

## 6. DEPLOYMENT PROCEDURE

### Step 1: Receive Docker Images

**Option A: Direct pull** (if container registry access is available)
```bash
docker pull cloudfinops/frontend:latest
docker pull cloudfinops/backend:latest
docker pull mongo:7
```

**Option B: Air gapped** (we provide .tar files via secure transfer)
```bash
docker load -i cloudfinops-frontend.tar
docker load -i cloudfinops-backend.tar
docker load -i mongo-7.tar
```

### Step 2: Configure Environment Variables

```bash
# MongoDB connection
MONGODB_URI=mongodb://mongo:27017/cloudfinops

# Authentication (provided by CloudFinOps)
CLERK_SECRET_KEY=<provided_during_onboarding>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<provided_during_onboarding>

# Encryption key for credential storage (generated by IFFCO)
ENCRYPTION_KEY=<32_byte_hex_key>

# Backend URL (internal reference)
NEXT_PUBLIC_BACKEND_URL=http://backend:8000

# Optional: AI Verification (remove line if not permitted)
GEMINI_API_KEY=<optional>
```

### Step 3: Launch Platform

```bash
docker compose up -d
```

### Step 4: Verify Health

```bash
# Frontend health
curl -s http://localhost:3000 | head -1

# Backend health
curl -s http://localhost:8000/health

# MongoDB connectivity
docker exec cloudfinops-mongo mongosh --eval "db.runCommand({ping:1})"
```

### Step 5: Access and Configure

1. Open browser: `http://<host-ip>:3000`
2. Login with provided credentials
3. Navigate to Settings → Add Azure Integration
4. Enter the Service Principal credentials (tenant_id, client_id, client_secret, subscription_id)
5. Click Scan

<div style="page-break-after: always;"></div>

## 7. DOCKER COMPOSE CONFIGURATION

```yaml
version: "3.8"

services:
  frontend:
    image: cloudfinops/frontend:latest
    ports:
      - "3000:8080"
    environment:
      - NEXT_PUBLIC_BACKEND_URL=http://backend:8000
      - NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
      - CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
      - MONGODB_URI=${MONGODB_URI}
    depends_on:
      - backend
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp

  backend:
    image: cloudfinops/backend:latest
    ports:
      - "8000:8080"
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
    depends_on:
      - mongo
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp

  mongo:
    image: mongo:7
    volumes:
      - cloudfinops_data:/data/db
    ports:
      - "127.0.0.1:27017:27017"
    restart: unless-stopped
    command: --wiredTigerCacheSizeGB 2

volumes:
  cloudfinops_data:
    driver: local
```

<div style="page-break-after: always;"></div>

## 8. OPERATIONS AND MAINTENANCE

### Backup Schedule

| Task | Frequency | Method |
|------|-----------|--------|
| Database backup | Daily (automated via cron) | `mongodump` to local backup directory |
| Configuration backup | Weekly | Export `.env` and `docker-compose.yml` |
| Image snapshot | Before each update | `docker save` current running images |

### Update Procedure

```bash
# 1. Backup current state
docker exec cloudfinops-mongo mongodump --out /backup/pre-update

# 2. Pull or load new images
docker compose pull   # (or docker load for air-gapped)

# 3. Restart with new images
docker compose up -d

# 4. Verify health
curl http://localhost:8000/health
```

### Monitoring

| Endpoint | Expected Response | Check Frequency |
|----------|-------------------|-----------------|
| `http://localhost:3000` | HTTP 200 | Every 60 seconds |
| `http://localhost:8000/health` | `{"status": "ok"}` | Every 60 seconds |
| MongoDB ping | `{"ok": 1}` | Every 60 seconds |

### Log Access

```bash
# View backend logs
docker logs cloudfinops-backend --tail 100

# View frontend logs
docker logs cloudfinops-frontend --tail 100

# View MongoDB logs
docker logs cloudfinops-mongo --tail 100
```

<div style="page-break-after: always;"></div>

## 9. SECURITY CONTROLS

| Control | Implementation |
|---------|---------------|
| Container isolation | Each service runs in its own container with no shared filesystem |
| Read only filesystem | Containers mounted as read only; tmpfs for ephemeral writes |
| No privileged mode | Containers run as non root user without elevated capabilities |
| Credential encryption | All stored credentials encrypted with AES 256 GCM |
| Network segmentation | MongoDB only accessible from backend container (127.0.0.1 bound) |
| No inbound internet | Platform requires zero inbound connections from outside IFFCO network |
| Audit logging | Every user action, scan event, and API call logged with timestamp |
| Image provenance | All Docker images signed and provided with SHA 256 checksums |

<div style="page-break-after: always;"></div>

## 10. SUPPORT

| Aspect | Commitment |
|--------|-----------|
| Deployment support | CloudFinOps CTO available via call during initial setup |
| Issue response time | 4 hours during business hours (Monday to Friday, 9 AM to 7 PM IST) |
| Critical issues | 1 hour response for platform down scenarios |
| Updates | Monthly release with detailed changelog; IFFCO controls update timing |
| Escalation path | Direct access to CTO (Nishant Jain) for critical issues |
| Documentation | Full API documentation and admin guide provided post deployment |

---

## FREQUENTLY ASKED QUESTIONS

**What happens if outbound internet connectivity is lost?**

The dashboard continues to function with cached data. Existing findings and recommendations remain accessible. New scans will queue and execute once Azure API connectivity is restored.

**Can we restrict which resource groups are scanned?**

Yes. Scope the Service Principal role assignment to specific resource groups instead of the entire subscription. The platform will only see and scan resources within those groups.

**Is the AI (Gemini) mandatory for the platform to function?**

No. Without Gemini, the platform uses deterministic rule based classification which covers all core scanning and waste detection. AI adds natural language reports and higher confidence scoring but is entirely optional.

**Can we deploy on Kubernetes instead of Docker Compose?**

Yes. We provide Helm charts for AKS or any Kubernetes deployment. Same container images, same environment variables, with added benefits of auto scaling and pod health management.

**How are platform updates delivered in an air gapped environment?**

Updated Docker image `.tar` files are provided via secure file transfer (SFTP or physical media). Run `docker load` followed by `docker compose up -d` to apply updates.

**What is the data retention policy?**

Configurable. Default: 90 days of scan history, 30 days of metrics. Older data is automatically purged. Backups follow IFFCO's internal retention policy.

---

<div style="text-align:center;margin-top:40px;padding:20px;">
<img src="../public/logo-main.png" width="140" />
<p style="color:#64748b;margin-top:15px;font-size:13px;">
CloudFinOps Solutions Pvt. Ltd.<br/>
Nishant Jain, CTO<br/>
https://cloudfinops.solutions
</p>
</div>
