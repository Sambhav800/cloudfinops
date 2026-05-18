# 🛡️ Zero-Key Client Onboarding Playbook
**For Enterprise Meetings (When the Client Says "No API Keys")**

## 1. The Pivot Script (Exactly What to Say)
When the CTO or CISO says: *"Sambhav, we love the product, but our security policies strictly forbid giving third-party tools Read-Only IAM keys to our live compute environment."*

**Your Response:**
> *"I completely understand, and frankly, you shouldn't hand over compute keys to a vendor on day one. That's exactly why we built our **Zero-Key Trust Funnel**.*
>
> *Instead of touching your live servers, we can do a massive cost-reduction scan using just your billing receipts. You can either manually drop a CSV export of your bill into our portal right now, or you can give us a highly restricted, 'Storage-Only' key that just reads the bucket where your bills are dropped.*
>
> *We will process that data entirely in-memory to find Ghost GPUs, CloudFront misconfigurations, and Cross-Cloud arbitrage opportunities without ever seeing your actual infrastructure."*

---

## 2. Option A: The "Manual Upload" (Instant Meeting Demo)
Use this if you want to show them savings *live during the meeting*.

**What to ask the client for:**
*"Can your DevOps or Finance lead quickly export last month's detailed billing report as a CSV or Excel file? We need the raw, line-item report, not just the high-level PDF summary."*

**Exact Formats Required by Cloud Provider:**
*   **AWS:** Ask for the **Cost and Usage Report (CUR)**.
    *   *Must contain columns like:* `lineItem/ProductCode`, `lineItem/UnblendedCost`, and ideally `lineItem/ResourceId`.
*   **Azure:** Ask for the **Cost Management Export**.
    *   *Must contain columns like:* `ServiceName`, `CostInBillingCurrency`, `ResourceId`.
*   **GCP:** Ask for a CSV export from their **BigQuery Billing Export** table.
    *   *Must contain columns like:* `Service description`, `Cost ($)`, `project name`.

**What CloudFinOps will instantly show them:**
1.  **GPU Arbitrage:** If they have `p4d` or `p5` instances, it will instantly show them how much they would save by moving to Lambda Labs.
2.  **Ghost GPUs:** It will group by `ResourceId` and flag any expensive GPUs that have $0 in data transfer/storage I/O (meaning they are powered on but doing no work).
3.  **CloudFront Traps:** If it's an AWS bill, it will detect if they are overpaying for `Lambda@Edge` and suggest `CloudFront Functions`.

---

## 3. Option B: The "Automated Sync" (The Compromise)
Use this if the client doesn't want to manually upload CSVs every month, but still refuses live compute access.

**Your Script:**
> *"If you want continuous monitoring without the manual work, just point us to the S3 bucket or Blob Container where your cloud provider automatically dumps your daily billing CSVs. We only need a strict 'Data Reader' role for that specific bucket. We cannot see your EC2 instances, databases, or application code."*

**Exactly What to Ask For (Send them this list):**

*   **For AWS Clients:**
    *   Tell them to create a bucket for AWS Cost and Usage Reports (CUR).
    *   Ask them to create an IAM User with this exact, strict policy:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "s3:GetBucketLocation",
            "s3:ListBucket",
            "s3:GetObject"
          ],
          "Resource": [
            "arn:aws:s3:::YOUR_BILLING_BUCKET_NAME",
            "arn:aws:s3:::YOUR_BILLING_BUCKET_NAME/*"
          ]
        }
      ]
    }
    ```
*   **For Azure Clients:**
    *   Ask them to assign the **"Storage Blob Data Reader"** role to a Service Principal, scoped *only* to the specific container holding their Cost Management exports.
*   **For GCP Clients:**
    *   Ask them to grant a Service Account the **"BigQuery Data Viewer"** role, scoped strictly to the dataset containing their Cloud Billing export.

**What CloudFinOps will do:**
Our background worker will wake up every 8 hours, securely download the new CSV from that bucket, run the GPU/Arbitrage AI analysis, and update their dashboard automatically.

---

## 4. The Upsell (Post-Meeting Strategy)
Once the meeting ends and they see the Dashboard populate with $50,000 in potential savings from just the CSV file, you deliver the final hook:

> *"As you can see, we found $50k in savings just by looking at your receipts. However, a CSV can't tell us if a server's CPU is running at 2% or 90%. If you grant us standard 'ReadOnlyAccess' to your live compute environment for a Deep Scan, our AI Watchdog will find the rest of the idle waste and generate the exact Terraform scripts your engineers need to delete it."*