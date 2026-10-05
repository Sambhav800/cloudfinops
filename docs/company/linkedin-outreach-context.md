# LinkedIn Outreach Context — CloudFinOps

Use this document as system context when crafting LinkedIn messages, comments, and DMs for lead generation.

---

## About Us

**Company:** CloudFinOps (cloudfinops.com)
**What we do:** AI-powered cloud waste detection and cost optimization for AWS, Azure, and GCP.
**Stage:** Pre-revenue, 0 paying clients. Product is built and functional. Looking for first 2-3 pilot customers.
**Team:** Nishant (CTO, builds everything) + Sambhav (CEO, business/fundraising)
**Location:** India (Mohali)

---

## What Our Product Actually Does

1. **Free Bill Scanner** (no signup): Upload any cloud bill (PDF/CSV) → instant waste analysis with specific findings, savings estimates, and waste grade (A-F)
2. **Connected Scanning** (signup required): Connect AWS/Azure/GCP with read-only IAM role → continuous multi-signal resource optimization
3. **AI Agent (Clousy)**: Conversational AI that answers questions about cloud spend, finds waste, generates CLI remediation scripts

---

## Our Technical Differentiators (Use These in Conversations)

- **< 2% false positive rate** — 6-stage deterministic classification pipeline requiring 3+ corroborating signals before flagging anything as waste. Not just "CPU < 5% = zombie" like basic tools.
- **Zero false positives on protected resources** — DR standby instances, auto-scaling group members, blue/green deployments, backup-tagged resources are automatically protected via relationship graph analysis.
- **Multi-signal evidence** — CPU + Network + Disk I/O + Memory + Connections analyzed together. Single-metric anomalies never trigger false alarms.
- **Self-improving** — every user approval/dismissal permanently adjusts detection thresholds via adaptive learning (fleet P10 calibration + EMA feedback loop).
- **60-80% less AI spend** — Gemini AI only called for ambiguous cases (confidence 0.50-0.75). Deterministic engine handles everything else.
- **Read-only, zero-trust** — never gets write access to customer infrastructure. Generates scripts that users copy/paste into their own terminals.
- **Precise rightsizing** — doesn't just say "oversized." Recommends exact target instance types (e.g., "m5.4xlarge → m5.xlarge, save $460/mo") based on P95 utilization + 15% headroom.
- **Temporal intelligence** — detects monthly batch jobs, maintenance windows, seasonal patterns. Never flags a payroll batch server that idles 28 days between runs.
- **Commitment-aware** — knows about RI/SP coverage, never recommends terminating a resource that's covered by a committed discount.

---

## What Problems We Solve (Pain Points to Reference)

- "Why did our cloud bill spike 30% this month?" → anomaly detection with root cause
- "Which resources are actually idle vs. legitimately low-usage?" → multi-signal analysis eliminates guesswork
- "We have 500+ resources and no idea which ones are waste" → automated classification with confidence scores
- "Every tool we tried flags our DR instances as zombies" → relationship graph + tag detection prevents this
- "We don't have time to manually review every recommendation" → graduated severity (only surface high-confidence, high-cost findings)
- "How do we know the savings estimate is real?" → evidence-based with actual bill line items as proof

---

## Our Offer for Pilots

- **Free scan** — connect read-only IAM role (15 min setup), get full waste analysis with dollar amounts
- **No commitment** — results are yours regardless of whether you buy
- **Savings guarantee** — if we don't find meaningful waste, no engagement required
- **Zero risk** — read-only access, data processed in-memory, never stored permanently

---

## Competitive Positioning (How We Compare)

| Them | Us |
|------|-----|
| AWS Trusted Advisor | Only checks basic thresholds, misses context, floods you with low-value noise |
| Azure Advisor | Single-cloud, no multi-signal corroboration, high false positive rate |
| Vantage/CloudZero | Visibility/dashboards only — shows where you spend but not what's waste |
| Usage.ai | Commitment optimization only — doesn't detect zombie resources or governance issues |
| Cast AI | Kubernetes-only — doesn't cover VMs, databases, storage, networking |
| CloudFinOps | Full lifecycle: detect → classify → recommend → generate fix scripts. Multi-cloud. < 2% FP rate. |

---

## Messaging Principles

1. **Never lead with product.** Lead with their problem or ask for their expertise.
2. **Demonstrate knowledge, don't claim it.** Instead of "we're the best tool," say something insightful about cloud waste that shows we understand their world.
3. **Be specific, not generic.** "Your Snowflake + AWS combo likely has $X in unoptimized data transfer" beats "we help reduce cloud costs."
4. **Respect seniority.** VPs and Directors don't want to be sold to. They want to learn something or be asked intelligent questions.
5. **The free scan is the closer, not the opener.** Build rapport first, then offer value.
6. **Social proof beats features.** "We found $4,200/month in waste for a 200-resource AWS account in 5 minutes" beats a feature list.

---

## Approach Framework (3-Step)

### Step 1: Content Engagement (Day 0)
- Comment on their posts with genuine, insightful thoughts
- Reference cloud/infra cost topics when relevant
- Position ourselves as someone who THINKS about this space, not sells in it

### Step 2: Warm DM (Day 2-5)
- Reference the post/comment interaction
- Ask about THEIR experience with a specific challenge
- Make it about their expertise, not our product
- Example: "How has [specific thing at their company] affected your cloud cost governance?"

### Step 3: Value Offer (Only After They Engage)
- Once they respond about cloud costs/infra challenges, offer the free scan
- Frame as "curious what it would find on your setup" not "buy our product"
- Make it zero-pressure: "Happy to share results with your team either way"

---

## Industry Talking Points (Use in Comments/DMs)

- 28-35% of cloud spend is wasted globally ($45B+ annually)
- Companies with 200+ cloud resources typically have 15-25% zombie/idle resources they don't know about
- The average "zombie" EC2 instance costs $70-150/month and runs for 6+ months before anyone notices
- Auto-scaling doesn't prevent waste — it prevents under-provisioning. Over-provisioning is the bigger problem.
- Most tools use single-metric thresholds (CPU < 5%). This produces 10-15% false positive rates. Multi-signal analysis (CPU + network + disk + connections together) drops it below 2%.
- Reserved Instance coverage gaps are the #1 source of cloud overspend for companies in the ₹20L-₹1Cr/month range.
- GPU instances are the fastest-growing waste category — a single idle p4d.24xlarge costs $32/hour ($23,000/month).

---

## Target Customer Profile

- **Company size:** 50-500 employees
- **Cloud spend:** ₹5L - ₹1Cr/month (sweet spot: ₹20L-₹50L)
- **Who to target:** VP Engineering, CTO, Head of DevOps/Platform, Head of Infrastructure
- **Industries:** SaaS, FinTech, InsurTech, E-commerce, AI/ML startups, Healthcare IT
- **Signals they're a good fit:**
  - Bio mentions "cloud," "AWS," "GCP," "infrastructure," "cost optimization," "DevOps"
  - Company is cloud-native or recently migrated
  - Growing engineering team (more people = more resource sprawl)
  - Posts about scaling challenges, infrastructure decisions, cost management

---

## Active Leads / Conversations (Don't Duplicate Outreach)

- Thurman Brown — call scheduled Mon-Wed
- Talgan Kumar Rao — email sent, awaiting reply
- Siddarth (DrDroid) — founder in adjacent space
- IFFCO Kisan Finance — POC discussion ongoing
- Rajan Agarwal (Zinnia, VP Engineering) — approaching via content engagement first

---

## Things NOT to Say

- "We're the best/leading/top cloud optimization platform" (we're pre-revenue, don't claim market leadership)
- "Our AI agent autonomously fixes your infrastructure" (we don't execute — we recommend and generate scripts)
- "We guarantee X% savings" (we can't guarantee without seeing their infra first)
- Anything that implies write access to their cloud
- Generic buzzwords without specifics ("leverage AI to optimize your cloud journey")
