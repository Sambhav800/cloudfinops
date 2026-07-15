"""
AI Analysis Engine for CloudFinOps.
Uses Google Gemini Flash models to VERIFY and OVERRIDE scanner classifications.

This is the REAL brain of the system. The scanner collects raw metadata.
This engine feeds ALL metadata to Gemini and gets independent per-resource
verdicts, verified costs, governance insights, and alerts.
"""

import json
import logging
import math
import asyncio
import re
import os
from typing import List, Dict, Any, Optional, Tuple

_USE_GOOGLE_GENAI = False
genai_client = None
genai_types = None
try:
    from google import genai as genai_client
    from google.genai import types as genai_types
    _USE_GOOGLE_GENAI = True
except Exception:
    genai_client = None
    genai_types = None

from ..config import GEMINI_API_KEY, GEMINI_VERIFY_MODEL

logger = logging.getLogger(__name__)

# Use fast flash model for verification
GEMINI_MODEL = GEMINI_VERIFY_MODEL
logger.info(f"[AI Module] _USE_GOOGLE_GENAI={_USE_GOOGLE_GENAI}, GEMINI_MODEL={GEMINI_MODEL}")
# Batch size for resource verification — keep small to avoid response truncation
VERIFICATION_BATCH_SIZE = int(os.getenv("GEMINI_VERIFICATION_BATCH_SIZE", "15"))


class _GenAIResponseAdapter:
    """Expose a stable `.text` attribute for existing analyzer code/tests."""

    def __init__(self, response: Any):
        self._response = response
        self.text = getattr(response, "text", "") or ""


class _AsyncGeminiModel:
    """Compat layer that mimics `generate_content_async` from deprecated SDK."""

    def __init__(self, client: Any, model_name: str):
        self._client = client
        self._model_name = model_name

    async def generate_content_async(
        self,
        prompt: str,
        generation_config: Optional[Any] = None,
    ) -> _GenAIResponseAdapter:
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=generation_config,
        )
        resp = _GenAIResponseAdapter(response)
        # Debug: log if response is empty
        if not resp.text or not resp.text.strip():
            # Try to extract blocking/safety info
            block_reason = getattr(response, 'prompt_feedback', None)
            candidates = getattr(response, 'candidates', [])
            finish_reason = None
            if candidates:
                finish_reason = getattr(candidates[0], 'finish_reason', None)
            logger.warning(f"⚠️ Gemini response is EMPTY. block_reason={block_reason}, finish_reason={finish_reason}, model={self._model_name}")
        return resp


class AIAnalyzer:
    """
    AI-powered analyzer using Google Gemini Flash models for real cloud verification.
    
    Pipeline:
    1. Scanner collects raw metadata (instance states, metrics, attachments)
    2. This engine sends FULL metadata to Gemini in batches
    3. Gemini independently classifies each resource with reasoning
    4. Gemini verifies costs, generates governance insights and alerts
    5. Conflict resolution: if scanner and AI disagree, AI verdict wins
    """
    
    def __init__(self):
        """Initialize Gemini AI client."""
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured - AI analysis will use fallback rules")
            self.client = None
            self.model = None
        elif not _USE_GOOGLE_GENAI or genai_client is None:
            logger.warning("google-genai package unavailable - AI analysis will use fallback rules")
            self.client = None
            self.model = None
        else:
            self.client = genai_client.Client(api_key=GEMINI_API_KEY)
            self.model = _AsyncGeminiModel(self.client, GEMINI_MODEL)
            logger.info(f"🤖 AIAnalyzer initialized with model: {GEMINI_MODEL} (SDK: google-genai)")

    def _build_generation_config(
        self,
        temperature: float,
        top_p: float,
        max_output_tokens: int,
        response_mime_type: str,
    ) -> Any:
        if not _USE_GOOGLE_GENAI or genai_types is None:
            raise RuntimeError("google-genai package unavailable")
        return genai_types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            parsed = float(value or 0)
        except (TypeError, ValueError):
            return 0.0
        return parsed if math.isfinite(parsed) else 0.0

    def _bounded_real_savings(self, resource: Dict[str, Any], raw_savings: Any) -> float:
        cost = max(self._safe_float(resource.get("cost")), 0.0)
        if cost <= 0:
            return 0.0

        metadata = resource.get("metadata") or {}
        cost_source = str(metadata.get("cost_source") or resource.get("cost_source") or "").lower()
        if cost_source != "actual":
            return 0.0

        savings = max(self._safe_float(raw_savings), 0.0)
        return round(min(savings, cost), 2)

    def _verdict_savings(self, merged: List[Dict[str, Any]], verdict: Dict[str, Any]) -> float:
        idx = verdict.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(merged):
            return 0.0
        return self._bounded_real_savings(merged[idx], verdict.get("ai_savings", 0))

    @staticmethod
    def _is_permanent_model_error(error_msg: str) -> bool:
        return (
            "404" in error_msg
            and (
                "not found" in error_msg
                or "not supported for generatecontent" in error_msg
            )
        )

    def _disable_ai_for_scan(self, reason: str) -> None:
        logger.warning("Gemini verification disabled for this scan: %s", reason)
        self.client = None
        self.model = None

    # =========================================================================
    # MAIN ENTRY POINT — Called by routes.py after scanner finishes
    # =========================================================================

    async def verify_and_analyze(
        self,
        resources: List[Dict[str, Any]],
        provider: str = "aws"
    ) -> Dict[str, Any]:
        """
        Full AI verification pipeline.
        
        1. Send all resources with FULL metadata to Gemini
        2. Get per-resource AI verdicts (status, reasoning, savings)
        3. Verify costs and generate governance/alerts
        4. Compare with scanner's classification
        5. Return final verified results
        """
        if not self.client or not self.model:
            logger.info("No Gemini API key - using enhanced rule-based fallback")
            return self._get_fallback_analysis(resources)

        try:
            total_resources = len(resources)
            logger.info(f"🧠 Starting AI verification for {total_resources} {provider.upper()} resources using {GEMINI_MODEL}")

            # Step 1: Compress metadata (strip huge blobs)
            prepared = self._prepare_compressed_metadata(resources)
            
            # Step 2: Send to Gemini in batches and collect verdicts
            all_verdicts = []
            num_batches = math.ceil(len(prepared) / VERIFICATION_BATCH_SIZE)
            
            rate_limit_failures = 0
            
            for batch_idx in range(num_batches):
                if rate_limit_failures >= 2:
                    logger.error("🛑 Circuit breaker triggered: Stopping AI verification due to repeated rate limits.")
                    break
                    
                start = batch_idx * VERIFICATION_BATCH_SIZE
                end = start + VERIFICATION_BATCH_SIZE
                batch = prepared[start:end]
                
                logger.info(f"🔍 Verifying batch {batch_idx + 1}/{num_batches} ({len(batch)} resources)")
                verdicts = await self._verify_batch(batch, provider)
                if not verdicts:
                    rate_limit_failures += 1
                all_verdicts.extend(verdicts)
                if batch_idx < num_batches - 1:
                    # Spread requests to avoid bursty quota throttling.
                    await asyncio.sleep(0.8)
            
            logger.info(f"✅ Gemini returned {len(all_verdicts)} verdicts for {total_resources} resources")
            
            # Step 3: Merge AI verdicts back into resources
            merged = self._merge_verdicts(resources, all_verdicts)
            
            # Step 4: Calculate conflict stats
            conflicts = self._count_conflicts(resources, all_verdicts)
            conflict_rate = conflicts / max(total_resources, 1)
            
            logger.info(
                f"📊 Conflict resolution: {conflicts}/{total_resources} "
                f"resources changed ({conflict_rate:.0%})"
            )
            
            # Step 5: Get cost verification, governance insights, and alerts from Gemini
            logger.info("💰 Running cost verification + governance + alerts analysis...")
            cost_governance = await self._verify_costs_and_governance(merged, all_verdicts, provider)
            
            # Step 6: Build final analysis from AI-verified data
            return self._build_final_analysis(merged, all_verdicts, conflict_rate, cost_governance)

        except Exception as e:
            logger.error(f"🔴 Gemini AI verification failed: {e}")
            logger.info("Falling back to enhanced rule-based analysis")
            return self._get_fallback_analysis(resources)

    # =========================================================================
    # LEGACY ENTRY POINT — kept for backward compatibility
    # =========================================================================

    async def analyze_resources(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy method — redirects to verify_and_analyze."""
        return await self.verify_and_analyze(resources)

    # =========================================================================
    # METADATA PREPARATION — Send EVERYTHING to Gemini
    # =========================================================================

    def _prepare_compressed_metadata(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare resources for Gemini with COMPRESSED metadata to save tokens.
        Strips huge nested objects like full security group rules, CloudFront origins, etc.
        """
        prepared = []
        for idx, r in enumerate(resources):
            entry = {
                "index": idx,
                "name": r.get("resource_name", "unknown"),
                "type": r.get("service_type", "unknown"),
                "scanner_status": r.get("status", "unknown"),
                "cost": r.get("cost", 0),
                "region": r.get("region", "unknown"),
                "created_by": r.get("created_by", "unknown"),
            }
            
            # Compress metadata
            metadata = r.get("metadata") or r.get("metrics_data") or {}
            if metadata:
                compressed_meta = {}
                keys_to_keep = [
                    'state',
                    'size_gb',
                    'avg_cpu',
                    'cpu_avg',
                    'instance_type',
                    'association_id',
                    'last_used',
                    'volume_type',
                    'engine',
                    'is_gpu_instance',
                    'gpu_memory_utilization_pct',
                    'gpu_sm_occupancy_pct',
                    'gpu_optimization_insight',
                ]
                for k in keys_to_keep:
                    if k in metadata:
                        compressed_meta[k] = metadata[k]
                
                # Keep simple string/number fields, avoid massive lists/dicts
                for k, v in metadata.items():
                    if len(compressed_meta) >= 15:
                        break
                    if k not in keys_to_keep and isinstance(v, (str, int, float, bool)) and len(str(v)) < 200:
                        compressed_meta[k] = v
                        
                entry["metadata"] = compressed_meta

            cost_source = ""
            if isinstance(metadata, dict):
                cost_source = str(metadata.get("cost_source") or "")
            cost_source = cost_source or str(r.get("cost_source") or "")
            entry["cost_source"] = cost_source or "unknown"
            
            # Include tags cleanly
            tags = r.get("tags") or (metadata.get("tags") if metadata else None) or {}
            if tags and isinstance(tags, dict):
                # Keep only simple keys like Owner, Env, Project
                clean_tags = {k: v for k, v in tags.items() if isinstance(v, str) and len(v) < 50}
                if clean_tags:
                    entry["tags"] = clean_tags
            
            # Include waste info if scanner already flagged it
            if r.get("waste_reason"):
                entry["scanner_waste_reason"] = r.get("waste_reason")
            if r.get("waste_type"):
                entry["scanner_waste_type"] = r.get("waste_type")
            if r.get("confidence_score"):
                entry["scanner_confidence"] = r.get("confidence_score")
            if r.get("cloud_resource_id"):
                entry["cloud_resource_id"] = r.get("cloud_resource_id")
            
            prepared.append(entry)
        
        return prepared

    # =========================================================================
    # GEMINI VERIFICATION — Per-resource AI verdicts (THE CORE)
    # =========================================================================

    async def _verify_batch(
        self,
        batch: List[Dict[str, Any]],
        provider: str
    ) -> List[Dict[str, Any]]:
        """
        Send a batch of resources to Gemini Flash for independent verification.
        Returns per-resource verdicts.
        """
        if not self.model:
            return []

        prompt = f"""You are the #1 FinOps engineer in the world. You are reviewing {len(batch)} {provider.upper()} cloud resources with their FULL raw metadata from the cloud API.

**YOUR JOB:** Independently analyze EVERY SINGLE resource and classify it. Do NOT blindly trust the scanner's status (scanner_status field). Look at the ACTUAL metadata to make your own decision.

**CLASSIFICATION RULES (be precise — only flag what the data proves):**
- "active" = Resource is genuinely in use OR properly serving its purpose
  * IMPORTANT: If scanner_status is "healthy" the scanner already verified this with real metrics — do NOT override to zombie unless you see clear contradicting evidence in the metadata
  * Newly created resources (< 7 days old) should generally be "active" unless clearly abandoned
- "zombie" = Resource exists but is definitively NOT doing useful work:
  * EC2/VM: stopped/deallocated for extended period AND no dev/test/staging tags
  * VMs with avg CPU < 2% AND network < 5MB over 7+ days (scanner already checks this)
  * Containers: no running tasks for 30+ days
  * DO NOT classify running VMs as zombie just because CPU is below 10% — they may run scheduled jobs or serve low-traffic APIs
- "idle" = Temporarily unused with clear evidence of intentional pause (dev/test/staging tags present)
- "waste" = Clearly wasted money with zero value:
  * Unattached disks/volumes = waste
  * Unassociated Elastic/Public IPs = waste
  * Load balancers with no backend targets = waste
  * Unattached network interfaces = waste
  * Orphaned snapshots older than 90 days = waste
- "oversized" = Running and useful but using significantly more capacity than needed:
  * VM/EC2 with avg CPU consistently < 15% over 7+ days AND could run on a smaller instance
  * Disks with very low IOPS relative to provisioned capacity
  * Premium SKU storage accounts with low transaction volumes
  * Provide specific downsizing recommendation in ai_action

**IMPORTANT: Trust the scanner's metrics-based classification. The scanner uses 7-day CPU/network averages which are MORE reliable than guessing from metadata. Only reclassify if you see clear contradicting evidence.**

**COST RULES:**
- Use only the numeric `cost` value supplied by the scanner.
- Treat `cost_source="actual"` as exact provider billing data.
- If `cost_source` is not "actual" or `cost` is 0, classify the resource normally but set `ai_savings` to 0.
- Never invent dollar amounts, public cloud list prices, hourly rates, GB-month rates, or default monthly prices.
- For oversized resources with actual cost, `ai_savings` must be no more than the supplied resource cost.
- Default VPCs/subnets/route tables and security groups usually have no direct recurring charge; classify based on usage/security but do not assign savings unless actual cost is supplied.

**RESOURCES TO ANALYZE (analyze ALL of them, not just some):**
```json
{json.dumps(batch, indent=1, default=str)}
```

**OUTPUT FORMAT — Return a JSON array with ONE entry per resource:**
```json
[
  {{
    "index": <int matching resource index>,
    "ai_status": "active|zombie|idle|waste|oversized",
    "ai_reasoning": "<clear 1-2 sentence explanation of WHY this classification>",
    "ai_savings": <float: monthly USD savings if eliminated/downsized. $0 if active>,
    "ai_severity": "none|low|medium|high|critical",
    "ai_action": "<specific CLI command or action to take. 'No action needed' if active>"
  }}
]
```

**MANDATORY:** You MUST return exactly {len(batch)} entries, one for each resource. Do NOT skip any. Return ONLY valid JSON array."""

        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                response = await self.model.generate_content_async(
                    prompt,
                    generation_config=self._build_generation_config(
                        temperature=0.15,
                        top_p=0.95,
                        max_output_tokens=65536,
                        response_mime_type="application/json",
                    ),
                )
                
                content = response.text
                
                # Debug: log first 500 chars of raw response
                logger.info(f"[Gemini Raw] len={len(content) if content else 0}, preview={repr(content[:500]) if content else 'EMPTY'}")
                
                # Guard: Gemini sometimes returns empty text (safety filter, blocked content)
                if not content or not content.strip():
                    logger.warning(f"Gemini returned empty response for batch of {len(batch)} (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(base_delay * (attempt + 1))
                        continue
                    return []
                
                verdicts = self._parse_json_response(content)
                
                if isinstance(verdicts, dict):
                    # Handle wrapped responses
                    for key in ("verdicts", "resources", "results", "analysis"):
                        if key in verdicts:
                            verdicts = verdicts[key]
                            break
                
                if not isinstance(verdicts, list):
                    verdicts = [verdicts]
                
                logger.info(f"   → Gemini returned {len(verdicts)} verdicts for batch of {len(batch)}")
                
                # Log verdict summary
                status_counts = {}
                for v in verdicts:
                    s = v.get("ai_status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1
                logger.info(f"   → Verdict breakdown: {status_counts}")
                
                return verdicts
                
            except json.JSONDecodeError as e:
                logger.error(f"Gemini returned malformed JSON (batch attempt {attempt + 1}): {e}")
                logger.error(f"[Gemini Content Dump] {repr(content[:1000]) if content else 'NONE'}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay)
                    continue
                return []
                
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = "429" in error_msg or "quota" in error_msg or "resource exhausted" in error_msg

                if self._is_permanent_model_error(error_msg):
                    self._disable_ai_for_scan(str(e))
                    return []
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Parse retry_delay from error message if present
                    delay_match = re.search(r"retry_delay.*?seconds:\s*(\d+)", error_msg, re.IGNORECASE | re.DOTALL)
                    api_delay = int(delay_match.group(1)) if delay_match else 0
                    
                    sleep_time = max(api_delay, base_delay * (2 ** attempt))
                    sleep_time = min(sleep_time, 120)  # Cap at 120s
                    logger.warning(f"⏳ Gemini rate limit hit (Attempt {attempt + 1}/{max_retries}). Waiting {sleep_time}s...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(f"❌ Gemini batch verification failed after {attempt + 1} attempts: {e}")
                    return []
                    
        # Inter-batch delay to prevent bursting
        await asyncio.sleep(2.0)
        return []

    def _parse_json_response(self, content: str) -> Any:
        """Parse JSON from Gemini response with fallback for malformed output."""
        # Try standard parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Fallback: strip markdown code fences
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Fallback: fix trailing commas (common LLM issue)
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Fallback: extract JSON array/object from surrounding text
        match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Fallback: repair truncated JSON array (response cut off by max_output_tokens)
        # Find the last complete JSON object and close the array
        bracket_pos = cleaned.find('[')
        if bracket_pos >= 0:
            # Find the last complete object ending with }
            last_brace = cleaned.rfind('}')
            if last_brace > bracket_pos:
                truncated_fix = cleaned[bracket_pos:last_brace + 1] + ']'
                try:
                    return json.loads(truncated_fix)
                except json.JSONDecodeError:
                    pass
        
        # Give up — re-raise
        raise json.JSONDecodeError("Could not parse Gemini response as JSON", content, 0)

    # =========================================================================
    # COST VERIFICATION + GOVERNANCE + ALERTS (NEW)
    # =========================================================================

    async def _verify_costs_and_governance(
        self,
        merged: List[Dict[str, Any]],
        verdicts: List[Dict[str, Any]],
        provider: str
    ) -> Dict[str, Any]:
        """
        Second Gemini call: verify total costs, generate governance policies, and alerts.
        """
        if not self.client:
            return self._get_fallback_cost_governance(merged)

        # Build a cost summary for Gemini to verify
        total_scanner_cost = sum(self._bounded_real_savings(r, r.get("cost", 0)) for r in merged)
        waste_resources = [v for v in verdicts if v.get("ai_status") in ("zombie", "waste", "idle", "oversized")]
        total_ai_savings = sum(self._verdict_savings(merged, v) for v in waste_resources)
        
        # Build resource type summary
        type_costs = {}
        for r in merged:
            stype = r.get("service_type", "Unknown")
            cost = self._bounded_real_savings(r, r.get("cost", 0))
            type_costs[stype] = type_costs.get(stype, 0) + cost
        
        # Build verdicts summary OUTSIDE f-string to avoid dict/set confusion
        # Truncate to top 100 to prevent context window overflow (400 Bad Request)
        verdicts_summary = []
        for v in verdicts[:100]:
            verdicts_summary.append({
                "resource": v.get("index"),
                "status": v.get("ai_status"),
                "savings": self._verdict_savings(merged, v),
                "action": v.get("ai_action", "")
            })
        verdicts_json = json.dumps(verdicts_summary, indent=1)
        type_costs_json = json.dumps(type_costs, indent=2, default=str)
        
        prompt = f"""You are a senior FinOps consultant producing a comprehensive cloud infrastructure report.

**CLOUD PROVIDER:** {provider.upper()}
**TOTAL RESOURCES:** {len(merged)}
**SCANNER REPORTED TOTAL COST:** ${total_scanner_cost:.2f}/month
**AI-IDENTIFIED WASTE RESOURCES:** {len(waste_resources)}
**AI SAVINGS FROM ACTUAL-COST RESOURCES ONLY:** ${total_ai_savings:.2f}/month

**COST BREAKDOWN BY SERVICE TYPE:**
```json
{type_costs_json}
```

**AI VERDICTS SUMMARY:**
```json
{verdicts_json}
```

**PRODUCE THE FOLLOWING (return as JSON object):**

1. **verified_total_cost**: Must equal the scanner reported total cost. Do not estimate or adjust it.
2. **verified_savings**: Must equal the AI savings from actual-cost resources only. Do not estimate savings for resources without actual cost.
3. **per_service_costs**: Array of {{service_type, monthly_cost, resource_count, waste_count}} for each service
4. **governance_findings**: Array of governance issues found:
   - Untagged resources (no Owner/Team/Environment tag)
   - Resources in non-approved regions (shadow IT)
   - Missing encryption on EBS/storage
   - Overly permissive security groups (0.0.0.0/0 ingress)
   - No backup/snapshot policies
   - IAM users with old credentials
   Each finding: {{type, severity, finding, affected_count, recommendation}}
5. **alerts**: Array of urgent alerts that need immediate attention:
   - Security risks (open ports, public access)
   - Cost spikes (any resource costing >$100/mo that's waste)
   - Compliance violations
   - Resource limit warnings
   Each alert: {{severity: "info|warning|critical", title, description, affected_resources}}
6. **cost_trend_assessment**: Brief assessment of spending patterns and forecast
7. **governance_data**: A strictly typed JSON object mapping to the frontend governance dashboard:
   {{
     "score": {{ "value": <int 0-100>, "trend": "up|down|stable", "rating": "Good|Fair|Critical" }},
     "tagging": {{ "missingTags": <int untagged>, "costImpact": <float waste amount>, "assets": [{{ "name": "id", "missing": ["Owner", "Env"] }}] }},
     "budget": {{ "projectedSpend": <float>, "budgetLimit": <float limit>, "burnRate": <int 0-100 percent>, "status": "Safe|Critical", "alert": "A brief warning" }},
     "officeHours": {{ "savings": <float>, "enabled": true, "recommendation": "Turn off dev VMs at night" }},
     "policies": [
        {{ "id": "pol-1", "name": "S3 Public Block", "status": "Pass|Fail", "severity": "Critical|High|Medium|Low", "reason": "S3 is public", "framework": "ISO27001" }}
     ]
   }}

Return ONLY valid JSON."""

        max_retries = 3
        base_delay = 5.0
        
        for attempt in range(max_retries):
            try:
                response = await self.model.generate_content_async(
                    prompt,
                    generation_config=self._build_generation_config(
                        temperature=0.2,
                        top_p=0.95,
                        max_output_tokens=8192,
                        response_mime_type="application/json",
                    ),
                )
                
                result = json.loads(response.text)
                result["verified_total_cost"] = round(total_scanner_cost, 2)
                result["verified_savings"] = round(total_ai_savings, 2)
                governance_data = result.get("governance_data")
                if isinstance(governance_data, dict):
                    budget = governance_data.get("budget")
                    if isinstance(budget, dict):
                        budget["projectedSpend"] = round(total_scanner_cost, 2)
                    office_hours = governance_data.get("officeHours")
                    if isinstance(office_hours, dict):
                        office_hours["savings"] = round(total_ai_savings, 2)
                    tagging = governance_data.get("tagging")
                    if isinstance(tagging, dict):
                        tagging["costImpact"] = min(
                            self._safe_float(tagging.get("costImpact")),
                            round(total_ai_savings, 2),
                        )
                logger.info(f"💰 Cost verification: scanner=${total_scanner_cost:.2f}, AI=${result.get('verified_total_cost', 0):.2f}")
                logger.info(f"🏛️ Governance findings: {len(result.get('governance_findings', []))}")
                logger.info(f"🚨 Alerts generated: {len(result.get('alerts', []))}")
                logger.info(f"DEBUG: AI Keys returned: {list(result.keys())}")
                if "governance_data" in result:
                    logger.info("DEBUG: governance_data found in AI response")
                else:
                    logger.error("DEBUG: governance_data MISSING from AI response")
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = "429" in error_msg or "quota" in error_msg or "resource exhausted" in error_msg

                if self._is_permanent_model_error(error_msg):
                    self._disable_ai_for_scan(str(e))
                    return self._get_fallback_cost_governance(merged)
                
                if is_rate_limit and attempt < max_retries - 1:
                    delay_match = re.search(r"retry_delay.*?seconds:\s*(\d+)", error_msg, re.IGNORECASE | re.DOTALL)
                    api_delay = int(delay_match.group(1)) if delay_match else 0
                    
                    sleep_time = max(api_delay, base_delay * (2 ** attempt))
                    sleep_time = min(sleep_time, 120)
                    logger.warning(f"⏳ Gemini cost verification rate limit (Attempt {attempt + 1}/{max_retries}). Waiting {sleep_time}s...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(f"❌ Cost/governance verification failed after {attempt + 1} attempts: {e}")
                    return self._get_fallback_cost_governance(merged)
        
        return self._get_fallback_cost_governance(merged)

    def _get_fallback_cost_governance(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback cost/governance when Gemini is unavailable."""
        total_cost = sum(r.get("cost", 0) for r in resources)
        return {
            "verified_total_cost": total_cost,
            "verified_savings": 0,
            "per_service_costs": [],
            "governance_findings": [],
            "alerts": [],
            "cost_trend_assessment": "Unable to assess — AI not available",
            "governance_data": {
                "score": {"value": 0, "trend": "stable", "rating": "Critical"},
                "tagging": {"missingTags": 0, "costImpact": 0, "assets": []},
                "budget": {"projectedSpend": total_cost, "budgetLimit": 0, "burnRate": 0, "status": "Safe", "alert": "No AI insights available."},
                "officeHours": {"savings": 0, "enabled": False, "recommendation": "Scan failed to verify."},
                "policies": []
            }
        }

    # =========================================================================
    # MERGE & CONFLICT RESOLUTION
    # =========================================================================

    def _merge_verdicts(
        self,
        resources: List[Dict[str, Any]],
        verdicts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge AI verdicts back into resource dicts.
        AI verdict OVERRIDES scanner's status.
        """
        verdict_map = {}
        for v in verdicts:
            idx = v.get("index")
            if idx is not None:
                verdict_map[idx] = v
        
        merged = []
        for idx, resource in enumerate(resources):
            r = dict(resource)
            v = verdict_map.get(idx)
            
            if v:
                ai_status = v.get("ai_status", "").lower()
                scanner_status = r.get("status", "").lower()

                status_map = {
                    "active": "healthy",
                    "zombie": "zombie",
                    "idle": "idle",
                    "waste": "waste",
                    "oversized": "oversized",
                }

                ai_mapped = status_map.get(ai_status, r.get("status", "healthy"))

                if scanner_status in ("healthy", "active", "underutilized", "moderate", "oversized"):
                    # Scanner used real metrics to classify (healthy/underutilized/moderate/
                    # oversized are all metrics-confirmed). AI should NOT override these.
                    r["ai_verified"] = True
                    r["ai_status"] = ai_status
                    r["ai_reasoning"] = v.get("ai_reasoning", "")
                    r["ai_action"] = v.get("ai_action", "none")

                    if ai_status == "oversized":
                        r["status"] = "oversized"
                        r["waste_type"] = "oversized"
                        r["waste_reason"] = v.get("ai_reasoning", "")
                        r["ai_savings"] = self._bounded_real_savings(r, v.get("ai_savings", 0))
                        r["ai_severity"] = v.get("ai_severity", "medium")
                        r["confidence_score"] = 0.75
                    else:
                        r["ai_savings"] = 0
                        r["ai_severity"] = "none"
                        if not r.get("waste_reason"):
                            r["waste_reason"] = None
                        if not r.get("waste_type"):
                            r["waste_type"] = None
                        r["confidence_score"] = 0.0
                elif scanner_status == "unknown":
                    # Scanner had insufficient data — trust AI classification
                    r["status"] = ai_mapped
                    r["ai_verified"] = True
                    r["ai_status"] = ai_status
                    r["ai_reasoning"] = v.get("ai_reasoning", "")
                    r["ai_savings"] = self._bounded_real_savings(r, v.get("ai_savings", 0))
                    r["ai_severity"] = v.get("ai_severity", "none")
                    r["ai_action"] = v.get("ai_action", "none")

                    if ai_status in ("zombie", "waste", "idle", "oversized"):
                        r["waste_reason"] = v.get("ai_reasoning", r.get("waste_reason", ""))
                        r["waste_type"] = "oversized" if ai_status == "oversized" else ai_status
                        r["confidence_score"] = 0.85
                    else:
                        r["waste_reason"] = None
                        r["waste_type"] = None
                        r["confidence_score"] = 0.0
                else:
                    # Scanner already classified (zombie/waste/non_compliant) — keep it,
                    # but enrich with AI reasoning
                    r["ai_verified"] = True
                    r["ai_status"] = ai_status
                    r["ai_reasoning"] = v.get("ai_reasoning", "")
                    r["ai_savings"] = self._bounded_real_savings(r, v.get("ai_savings", 0))
                    r["ai_severity"] = v.get("ai_severity", "none")
                    r["ai_action"] = v.get("ai_action", "none")
            else:
                r["ai_verified"] = False
            
            merged.append(r)
        
        return merged

    def _count_conflicts(
        self,
        original: List[Dict[str, Any]],
        verdicts: List[Dict[str, Any]]
    ) -> int:
        """Count how many resources AI classified differently from scanner."""
        verdict_map = {v.get("index"): v for v in verdicts if v.get("index") is not None}
        conflicts = 0
        
        for idx, resource in enumerate(original):
            v = verdict_map.get(idx)
            if not v:
                continue
            
            scanner_status = (resource.get("status") or "").lower()
            ai_status = (v.get("ai_status") or "").lower()
            
            scanner_is_waste = scanner_status in ("zombie", "waste", "stopped", "idle")
            ai_is_waste = ai_status in ("zombie", "waste", "idle", "oversized")
            
            if scanner_is_waste != ai_is_waste:
                conflicts += 1
                logger.info(
                    f"   ⚡ Conflict: '{resource.get('resource_name')}' "
                    f"scanner={scanner_status} → AI={ai_status} "
                    f"({v.get('ai_reasoning', '')})"
                )
        
        return conflicts

    # =========================================================================
    # BUILD FINAL ANALYSIS OUTPUT
    # =========================================================================

    def _build_final_analysis(
        self,
        merged: List[Dict[str, Any]],
        verdicts: List[Dict[str, Any]],
        conflict_rate: float,
        cost_governance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the final analysis dict from AI-verified resources."""

        total_spend = sum(self._bounded_real_savings(r, r.get("cost", 0)) for r in merged)

        potential_savings = sum(
            self._verdict_savings(merged, v) for v in verdicts
            if v.get("ai_status") in ("zombie", "waste", "idle", "oversized")
        )
        
        # Build waste distribution from AI verdicts
        waste_by_type = {}
        for v in verdicts:
            status = v.get("ai_status", "")
            savings = self._verdict_savings(merged, v)
            if status in ("zombie", "waste", "idle", "oversized") and savings > 0:
                category_map = {
                    "zombie": "Zombie Resources",
                    "waste": "Wasted Resources",
                    "idle": "Idle Resources",
                    "oversized": "Oversized Resources",
                }
                cat = category_map.get(status, status)
                waste_by_type[cat] = waste_by_type.get(cat, 0) + savings
        
        waste_distribution = [
            {"category_name": k, "value": round(v, 2)}
            for k, v in waste_by_type.items()
        ]
        
        # Build recommendations from ALL AI verdicts (not just top few)
        recommendations = []
        for v in verdicts:
            if v.get("ai_status") in ("zombie", "waste", "idle", "oversized"):
                action = v.get("ai_action", "Review this resource")
                if action and action.lower() not in ("none", "no action needed", "no action", "n/a"):
                    idx = v.get("index", 0)
                    resource_name = "Unknown"
                    resource_type = "Cloud Resource"
                    if idx < len(merged):
                        resource_name = merged[idx].get("resource_name", "Unknown")
                        resource_type = merged[idx].get("service_type", "Cloud Resource")
                    
                    recommendations.append({
                        "resource_name": resource_name,
                        "resource_type": resource_type,
                        "type": "cost_optimization",
                        "action": action,
                        "potential_savings": self._verdict_savings(merged, v),
                        "severity": v.get("ai_severity", "medium"),
                        "ai_reasoning": v.get("ai_reasoning", ""),
                        "ai_status": v.get("ai_status", ""),
                    })
        
        # Sort recommendations by savings (highest first)
        recommendations.sort(key=lambda x: x.get("potential_savings", 0), reverse=True)
        
        # AI confidence
        ai_confidence = max(60, min(98, int(92 - (conflict_rate * 40))))
        
        # Carbon footprint
        active_count = sum(1 for v in verdicts if v.get("ai_status") == "active")
        carbon_estimate = round(active_count * 10.5, 2)
        
        waste_count = sum(
            1 for v in verdicts
            if v.get("ai_status") in ("zombie", "waste", "idle", "oversized")
        )
        
        logger.info(f"🧠 AI VERIFICATION RESULTS ({GEMINI_MODEL}):")
        logger.info(f"   Total resources: {len(merged)}")
        logger.info(f"   Active: {active_count}")
        logger.info(f"   Waste/Zombie/Idle/Oversized: {waste_count}")
        logger.info(f"   Total spend: ${total_spend:.2f}")
        logger.info(f"   Potential savings: ${potential_savings:.2f}")
        logger.info(f"   Recommendations: {len(recommendations)}")
        logger.info(f"   Governance findings: {len(cost_governance.get('governance_findings', []))}")
        logger.info(f"   Alerts: {len(cost_governance.get('alerts', []))}")
        logger.info(f"   AI confidence: {ai_confidence}%")
        
        return {
            "total_spend": round(total_spend, 2),
            "potential_savings": round(potential_savings, 2),
            "carbon_footprint_kg": carbon_estimate,
            "active_resources_count": len(merged),
            "ai_confidence_score": ai_confidence,
            "waste_distribution": waste_distribution,
            "recommendations": recommendations,
            "verified_resources": merged,
            "conflict_rate": conflict_rate,
            # NEW: cost governance data
            "per_service_costs": cost_governance.get("per_service_costs", []),
            "governance_findings": cost_governance.get("governance_findings", []),
            "alerts": cost_governance.get("alerts", []),
            "cost_trend_assessment": cost_governance.get("cost_trend_assessment", ""),
            "governance_data": cost_governance.get("governance_data", None)
        }

    # =========================================================================
    # FALLBACK — Enhanced rule-based analysis
    # =========================================================================

    def _get_fallback_analysis(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced rule-based fallback when Gemini is not available."""
        logger.info("📊 Running enhanced rule-based analysis (fallback mode)")
        
        total_spend = 0
        recommendations = []
        waste_categories = {}
        
        for resource in resources:
            cost = self._safe_float(resource.get("cost", 0))
            total_spend += self._bounded_real_savings(resource, cost)
            
            name = resource.get("resource_name", "unknown")
            stype = resource.get("service_type", "").lower()
            status = resource.get("status", "").lower()
            metadata = resource.get("metadata") or {}
            tags = resource.get("tags") or metadata.get("tags") or {}
            
            waste_reason = None
            severity = "medium"
            savings = cost
            bounded_cost = self._bounded_real_savings(resource, cost)
            
            # EC2: Stopped instances
            if "ec2" in stype and "instance" in stype and status in ("zombie", "stopped"):
                is_dev = any(
                    t in str(tags).lower()
                    for t in ("dev", "test", "staging", "sandbox")
                )
                if not is_dev:
                    waste_reason = f"EC2 instance '{name}' is stopped with no dev/test tags — likely zombie"
                    severity = "high"
                    waste_categories["Zombie VMs"] = waste_categories.get("Zombie VMs", 0) + bounded_cost
            
            # EC2: Running but low CPU
            elif "ec2" in stype and "instance" in stype and status == "active":
                avg_cpu = metadata.get("avg_cpu_7d")
                if avg_cpu is not None and avg_cpu < 10:
                    waste_reason = f"EC2 '{name}' has avg CPU {avg_cpu}% over 7 days — likely zombie"
                    severity = "high"
                    waste_categories["Zombie VMs"] = waste_categories.get("Zombie VMs", 0) + bounded_cost
            
            # EBS: Unattached volumes
            elif "ebs" in stype or "volume" in stype:
                state = metadata.get("state", "")
                if status in ("zombie", "waste") or state == "available":
                    waste_reason = f"EBS volume '{name}' ({metadata.get('size_gb', '?')}GB) is not attached to any instance"
                    severity = "medium"
                    waste_categories["Orphaned Disks"] = waste_categories.get("Orphaned Disks", 0) + bounded_cost
            
            # Elastic IPs: Unassociated
            elif "elastic ip" in stype or "eip" in stype:
                if status in ("zombie", "waste") or not metadata.get("association_id"):
                    waste_reason = f"Elastic IP '{name}' is not associated"
                    severity = "medium"
                    savings = self._bounded_real_savings(resource, cost)
                    waste_categories["Unused IPs"] = waste_categories.get("Unused IPs", 0) + savings
            
            # Security Groups: Overly permissive
            elif "security group" in stype:
                rules = metadata.get("rules_count", 0)
                if metadata.get("has_open_ingress"):
                    waste_reason = f"Security group '{name}' has 0.0.0.0/0 ingress — security risk"
                    severity = "critical"
                    savings = 0
            
            # Generic: scanner already flagged
            elif status in ("zombie", "waste"):
                waste_reason = resource.get("waste_reason", f"Resource '{name}' flagged as {status}")
                waste_categories["Other Waste"] = waste_categories.get("Other Waste", 0) + bounded_cost
            
            if waste_reason:
                recommendations.append({
                    "resource_name": name,
                    "resource_type": resource.get("service_type", "Cloud Resource"),
                    "type": "cost_optimization",
                    "action": waste_reason,
                    "potential_savings": self._bounded_real_savings(resource, savings),
                    "severity": severity,
                    "ai_reasoning": waste_reason,
                    "ai_status": "waste",
                })
        
        waste_distribution = [
            {"category_name": k, "value": round(v, 2)}
            for k, v in waste_categories.items()
        ]
        
        potential_savings = sum(r.get("potential_savings", 0) for r in recommendations)
        
        return {
            "total_spend": round(total_spend, 2),
            "potential_savings": round(potential_savings, 2),
            "carbon_footprint_kg": round(len(resources) * 10.5, 2),
            "active_resources_count": len(resources),
            "ai_confidence_score": 55,
            "waste_distribution": waste_distribution,
            "recommendations": recommendations,
            "verified_resources": resources,
            "conflict_rate": 0.0,
            "per_service_costs": [],
            "governance_findings": [],
            "alerts": [],
            "cost_trend_assessment": "Fallback mode — AI not available",
        }
