"""
AI Verifier — Gemini as verification layer, not classifier.

In the new architecture, AI is called ONLY for ambiguous cases (confidence 0.50-0.75)
where the deterministic engine is uncertain. This replaces the current approach of
sending ALL resources through Gemini.

Result: 60-80% reduction in Gemini API calls, faster scans, lower cost.

AI's role:
1. Confirm or challenge ambiguous verdicts with reasoning
2. Generate human-readable explanations for high-confidence verdicts
3. Detect edge cases the deterministic engine can't handle
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .evidence_collector import EvidenceBundle
from .severity import ResourceClassification, ResourceVerdict

logger = logging.getLogger(__name__)

# Only send resources in this confidence range to AI
AI_REVIEW_MIN_CONFIDENCE = 0.50
AI_REVIEW_MAX_CONFIDENCE = 0.75

# Maximum batch size for AI verification
AI_BATCH_SIZE = 10


@dataclass
class AIVerification:
    """Result of AI verification for a single resource."""

    resource_id: str
    ai_agrees: bool
    ai_classification: Optional[str] = None  # Only set if AI disagrees
    ai_reasoning: str = ""
    ai_confidence_adjustment: float = 0.0  # Positive = raise, negative = lower


class AIVerifier:
    """
    Verification-only AI layer.

    Only processes ambiguous cases — resources where the deterministic pipeline
    produced a confidence between 0.50 and 0.75.
    """

    def __init__(self, gemini_client: Any = None, model: str = "gemini-2.0-flash"):
        self.client = gemini_client
        self.model = model

    def filter_for_review(
        self, verdicts: List[ResourceVerdict]
    ) -> List[ResourceVerdict]:
        """
        Filter verdicts to only those needing AI verification.

        This is the gating function that reduces AI call volume by 60-80%.
        """
        return [
            v for v in verdicts
            if v.ai_verification_needed
            and AI_REVIEW_MIN_CONFIDENCE <= v.confidence <= AI_REVIEW_MAX_CONFIDENCE
        ]

    async def verify_batch(
        self,
        verdicts: List[ResourceVerdict],
        evidence: List[EvidenceBundle],
    ) -> List[AIVerification]:
        """
        Send ambiguous cases to AI for second opinion.

        AI sees the deterministic verdict and evidence, then confirms or challenges.
        This is NOT classification — the deterministic verdict stands unless AI
        provides clear contradicting reasoning.
        """
        if not self.client:
            logger.debug("AI verification skipped — no Gemini client configured")
            return []

        ambiguous = self.filter_for_review(verdicts)
        if not ambiguous:
            return []

        # Match verdicts with their evidence bundles
        evidence_map = {e.resource_id: e for e in evidence}
        pairs = [
            (v, evidence_map.get(v.resource_id))
            for v in ambiguous
            if v.resource_id in evidence_map
        ]

        if not pairs:
            return []

        # Process in batches
        results: List[AIVerification] = []
        for i in range(0, len(pairs), AI_BATCH_SIZE):
            batch = pairs[i:i + AI_BATCH_SIZE]
            batch_results = await self._verify_batch_internal(batch)
            results.extend(batch_results)

        return results

    async def _verify_batch_internal(
        self,
        pairs: List[tuple],
    ) -> List[AIVerification]:
        """
        Internal batch verification via Gemini.

        Constructs a verification prompt (not classification prompt) that asks
        AI to confirm or challenge each verdict with reasoning.
        """
        prompt = self._build_verification_prompt(pairs)

        try:
            response = await self._call_gemini(prompt)
            return self._parse_verification_response(response, pairs)
        except Exception as e:
            logger.warning(f"AI verification batch failed: {e}")
            # On failure, return "agrees" for all — deterministic verdict stands
            return [
                AIVerification(
                    resource_id=v.resource_id,
                    ai_agrees=True,
                    ai_reasoning="AI verification unavailable — deterministic verdict stands",
                )
                for v, _ in pairs
            ]

    def _build_verification_prompt(self, pairs: List[tuple]) -> str:
        """
        Build the verification prompt for Gemini.

        Key difference from current analyzer.py: this asks AI to VERIFY a verdict,
        not to independently classify. The burden of proof is on AI to CHALLENGE,
        not to agree.
        """
        resource_descriptions = []

        for i, (verdict, evidence) in enumerate(pairs, 1):
            signals_desc = []
            for s in verdict.corroborating_signals[:3]:
                signals_desc.append(f"  - {s.description}")

            desc = (
                f"Resource {i}: {evidence.resource_name if evidence else verdict.resource_id}\n"
                f"  Type: {evidence.resource_type if evidence else 'unknown'}\n"
                f"  Provider: {evidence.provider if evidence else 'unknown'}\n"
                f"  State: {evidence.provider_state.value if evidence else 'unknown'}\n"
                f"  Our verdict: {verdict.classification.value} (confidence: {verdict.confidence:.2f})\n"
                f"  Our reasoning: {verdict.waste_reason}\n"
                f"  Corroborating signals:\n" + "\n".join(signals_desc)
            )

            if evidence and evidence.tags:
                relevant_tags = {
                    k: v for k, v in list(evidence.tags.items())[:5]
                    if k.lower() not in ("name", "aws:cloudformation:stack-name")
                }
                if relevant_tags:
                    desc += f"\n  Tags: {relevant_tags}"

            resource_descriptions.append(desc)

        return f"""You are verifying resource classification verdicts from a deterministic optimization engine.

For each resource below, our engine has produced a verdict with limited confidence (0.50-0.75).
Your job: CONFIRM or CHALLENGE each verdict. Only challenge if you see clear evidence
the engine missed — not just uncertainty.

IMPORTANT RULES:
- Default to CONFIRM unless you have specific contradicting evidence
- A stopped resource being flagged as waste is CORRECT unless tags/context suggest DR/maintenance
- Low CPU + low network + low disk = waste. This is correct. Don't challenge without reason.
- If you cannot determine either way, CONFIRM (trust the deterministic engine)

Resources to verify:
{chr(10).join(resource_descriptions)}

For each resource, respond in this exact format:
RESOURCE_<number>: CONFIRM|CHALLENGE
REASONING: <one sentence explanation>
ADJUSTMENT: <float between -0.15 and +0.15, 0.0 if confirm>
"""

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API. Abstracted for testability."""
        if not self.client:
            return ""

        # Uses the same pattern as analyzer.py but with lower temperature
        import httpx

        if isinstance(self.client, str):
            # Client is an API key
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    params={"key": self.client},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 1024,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        return ""

    def _parse_verification_response(
        self,
        response: str,
        pairs: List[tuple],
    ) -> List[AIVerification]:
        """Parse Gemini's verification response."""
        results: List[AIVerification] = []

        if not response:
            return [
                AIVerification(resource_id=v.resource_id, ai_agrees=True)
                for v, _ in pairs
            ]

        lines = response.strip().split("\n")
        current_resource_idx = 0
        current_agrees = True
        current_reasoning = ""
        current_adjustment = 0.0

        for line in lines:
            line = line.strip()

            if line.startswith("RESOURCE_"):
                # Parse verdict
                if "CHALLENGE" in line.upper():
                    current_agrees = False
                else:
                    current_agrees = True

            elif line.startswith("REASONING:"):
                current_reasoning = line[len("REASONING:"):].strip()

            elif line.startswith("ADJUSTMENT:"):
                try:
                    adj_str = line[len("ADJUSTMENT:"):].strip()
                    current_adjustment = float(adj_str)
                    current_adjustment = max(-0.15, min(0.15, current_adjustment))
                except (ValueError, TypeError):
                    current_adjustment = 0.0

                # Emit result for this resource
                if current_resource_idx < len(pairs):
                    verdict, _ = pairs[current_resource_idx]
                    results.append(AIVerification(
                        resource_id=verdict.resource_id,
                        ai_agrees=current_agrees,
                        ai_reasoning=current_reasoning,
                        ai_confidence_adjustment=current_adjustment,
                    ))
                    current_resource_idx += 1
                    current_agrees = True
                    current_reasoning = ""
                    current_adjustment = 0.0

        # Fill in any missing results
        while len(results) < len(pairs):
            verdict, _ = pairs[len(results)]
            results.append(AIVerification(
                resource_id=verdict.resource_id,
                ai_agrees=True,
                ai_reasoning="No AI response for this resource",
            ))

        return results

    def apply_verifications(
        self,
        verdicts: List[ResourceVerdict],
        verifications: List[AIVerification],
    ) -> List[ResourceVerdict]:
        """
        Apply AI verification results back to verdicts.

        AI can adjust confidence by ±0.15 but CANNOT override the classification
        if it was above 0.70 confidence from the deterministic engine.
        """
        verification_map = {v.resource_id: v for v in verifications}

        for verdict in verdicts:
            ai_result = verification_map.get(verdict.resource_id)
            if not ai_result:
                continue

            # Apply confidence adjustment
            if ai_result.ai_confidence_adjustment != 0:
                verdict.confidence = max(0.0, min(1.0,
                    verdict.confidence + ai_result.ai_confidence_adjustment
                ))

            # Store AI reasoning in the verdict for UI display
            if ai_result.ai_reasoning:
                verdict.context_factors.append(f"AI: {ai_result.ai_reasoning}")

            # If AI challenges, mark for human review
            if not ai_result.ai_agrees:
                verdict.requires_human_review = True

        return verdicts
