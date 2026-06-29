"""
CloudFinOps ADK Root Agent — Autonomous FinOps Engine.

This is the entry point for `adk web` and `adk run`.
Defines a 5-stage SequentialAgent pipeline:
  1. Router → classifies intent
  2. MultiCloud Scanner → parallel AWS/Azure/GCP scanning
  3. Synthesizer → merges and prioritizes findings
  4. Remediation Loop → generates scripts + safety critic validation
  5. Executive Reporter → CTO-grade summary

Run with:
  adk web backend/app/adk
  adk run backend/app/adk
"""
from google.adk.agents import SequentialAgent

from .agents.router import router_agent
from .agents.scanners import parallel_scanner
from .agents.synthesizer import synthesizer_agent
from .agents.remediation import remediation_loop
from .agents.reporter import reporter_agent

root_agent = SequentialAgent(
    name="FinOps_Orchestrator",
    sub_agents=[
        router_agent,
        parallel_scanner,
        synthesizer_agent,
        remediation_loop,
        reporter_agent,
    ],
)
