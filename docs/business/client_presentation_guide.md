# Client Presentation Playbook

Here is a summary of the approach you should take:

## 1. Own the $100k Number with Confidence
Do not walk the number back. Tell them: "We fed your 146-row spreadsheet into the CloudFinOps pricing engine. Based on the $2,000,000 baseline spend you provided, the cross-cloud arbitrage model calculates an immediate 5.0% saving ($100,000/mo) if we migrate those workloads to Google Cloud (GCP)."

## 2. How to explain "GENERIC"
They will ask what "Detected: GENERIC" means. Your exact response: "The spreadsheet you provided was a high-level financial summary. It didn't contain the machine-level SKUs (like m5.large or Premium_SSD) that our AI uses for 1-to-1 resource mapping. Because of that, the engine correctly classified your infrastructure as a Generic Cloud Workload and bucketed it into 'Other'."

## 3. How to explain the math (The 5%)
If they ask how you calculated exactly $100,000 on a generic bill: Your exact response: "Our engine tracks global list-price averages across the big three clouds. For generic compute workloads, AWS is the 1.0 baseline. Azure runs at ~1.02 (+2%). GCP consistently runs at a baseline of ~0.95 (-5%) due to sustained use discounts and cheaper bandwidth. Applying that 0.95 multiplier to your $2M spend mathematically yields $1.9M."

## 4. The Upsell Strategy (Crucial)
Use this report as "bait" to get better data. Tell them: "This $100k proves that a migration is financially viable. However, this is a baseline estimate based on public averages. If you really want to guarantee exactly how many pennies you will save, your DevOps team needs to export a Detailed Cost and Usage CSV (with Resource IDs and SKUs). Give me that file, our AI will run a surgical line-by-line analysis, and we will lock in the final dollar amount."