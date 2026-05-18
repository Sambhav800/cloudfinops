# CloudFinOps

AI-Powered Cloud Waste & Governance Manager.

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Project
- Azure Service Principal

### 2. Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Setup Frontend

```bash
npm install
npm run dev
```

---

## ☁️ Azure Configuration (Critical)

To enable **Real Cost Data** fetching (instead of estimates), you must grant your Service Principal the following permission:

**Role:** `Cost Management Reader`  
**Scope:** Subscription Level

### 🔑 How to Assign via Azure Portal:

1. Go to **Subscriptions**.
2. Select your subscription.
3. Click **Access control (IAM)** on the left menu.
4. Click **+ Add** → **Add role assignment**.
5. Search for and select **Cost Management Reader**.
6. Click **Next**.
7. Keep "User, group, or service principal" selected.
8. Click **+ Select members** and search for your Service Principal (App Registration name).
9. Click **Select**, then **Review + assign**.

> [!NOTE]
> Without this role, the scanner will still work but will show **ESTIMATED** costs only, and the daily spend chart will be empty.

---

## 🛠️ Features

- **Waste Detection:** Zombie VMs, Orphaned Disks, Unused IPs.
- **Real Cost Tracking:** Integrates with Azure Cost Management API.
- **AI Governance:** Auto-generates policies based on infrastructure patterns.
- **Shadow IT Detection:** Flags resources in unapproved regions.
