"""
CloudFinOps AI Agent — Production-grade Gemini Function Calling Agent.

Uses Gemini 3 Flash REST API with function calling to dynamically query
MongoDB and answer any question about the user's cloud infrastructure.

Direct REST API via httpx — avoids genai.protos compatibility issues.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional

import httpx

from ..config import GEMINI_API_KEY, GEMINI_AGENT_MODEL
from ..core.audit import log_audit_event
from ..core.agent_context import build_agent_system_prompt

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


# ---------------------------------------------------------------------------
# Session Manager — multi-turn conversation memory
# ---------------------------------------------------------------------------

class SessionManager:
    """In-memory session store for conversation history."""

    def __init__(self, max_sessions: int = 200, max_turns: int = 50):
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}
        self._max_sessions = max_sessions
        self._max_turns = max_turns

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        return list(self._sessions.get(session_id, []))

    def add_turn(self, session_id: str, role: str, parts: list):
        if session_id not in self._sessions:
            if len(self._sessions) >= self._max_sessions:
                oldest = next(iter(self._sessions))
                del self._sessions[oldest]
            self._sessions[session_id] = []

        self._sessions[session_id].append({"role": role, "parts": parts})

        # Keep history bounded
        if len(self._sessions[session_id]) > self._max_turns * 2:
            self._sessions[session_id] = self._sessions[session_id][-self._max_turns * 2:]

    def clear(self, session_id: str):
        self._sessions.pop(session_id, None)


_session_mgr = SessionManager()


# ---------------------------------------------------------------------------
# Tool Definitions (Gemini REST API format)
# ---------------------------------------------------------------------------

import pathlib
import sys
import os
_MCP_AVAILABLE = False
try:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    _MCP_AVAILABLE = True
except Exception:
    ClientSession = None
    stdio_client = None

    class StdioServerParameters:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

SYSTEM_PROMPT = """You are **Clousy**, the CloudFinOps AI Agent.

You are a production-grade FinOps intelligence agent connected to the user's live cloud infrastructure database. You have tools that query real-time data.

## Capabilities
- Answer ANY question about cloud resources, costs, and security
- Analyze spending patterns and identify optimization opportunities
- Provide specific, actionable recommendations with exact dollar amounts
- Compare resources, identify trends, detect anomalies
- Explain governance compliance and policy violations

## Rules
1. ALWAYS call the appropriate tool(s) before answering. Never guess data.
2. If you need multiple perspectives, call multiple tools.
3. Use markdown: tables for resource lists, bold for key numbers, bullets for recommendations.
4. Include specific dollar amounts ($X.XX) and resource names.
5. Be concise but thorough. Prioritize actionable insights.
6. If unclear, ask for clarification instead of guessing.
7. Be specific: "Delete zombie-forgotten-vm to save $17.34/mo"
8. For trends, describe direction and magnitude.
9. Use conversation history for context.
10. If asked about Multi-Cloud, check cross-cloud comparisons to see if GCP or Azure is cheaper.
11. If asked about GPUs, ML, or AI costs, check GPU Intelligence for Ghost GPUs, MIG options, and arbitrage.
12. If no data found, say so and suggest running a scan."""


# ---------------------------------------------------------------------------
# The Agent
# ---------------------------------------------------------------------------

class CloudFinOpsAgent:
    """Production AI Agent using Gemini REST API with function calling over MCP."""

    def __init__(self, db_client, user_id: str):
        self.db = db_client
        self.user_id = user_id

    # -------------------------------------------------------------------
    # MCP Integration
    # -------------------------------------------------------------------

    def _get_mcp_params(self) -> StdioServerParameters:
        """Returns the startup configuration for the MCP Server process."""
        if not _MCP_AVAILABLE:
            raise RuntimeError("MCP package is not installed in this environment")
        # Find the backend directory path dynamically
        backend_dir = pathlib.Path(__file__).parent.parent.parent.absolute()
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        backend_path = str(backend_dir)
        if existing_pythonpath:
            pythonpath_entries = [entry for entry in existing_pythonpath.split(os.pathsep) if entry]
            if backend_path not in pythonpath_entries:
                env["PYTHONPATH"] = os.pathsep.join([backend_path, *pythonpath_entries])
        else:
            env["PYTHONPATH"] = backend_path
        
        # We start the FastMCP python server module
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.ai.mcp_server"],
            env=env,
            cwd=backend_path,
        )

    def _mcp_to_gemini_tools(self, mcp_tools) -> list:
        """
        Dynamically converts JSON schema from MCP tools to Gemini's strict REST format.
        Crucially strips the `user_id` parameter to prevent Gemini from hallucinating or guessing it.
        """
        gemini_tools = []
        for t in mcp_tools:
            gem_tool = {
                "name": t.name,
                "description": t.description or "",
            }

            if not t.inputSchema or "properties" not in t.inputSchema:
                gem_tool["parameters"] = {"type": "OBJECT", "properties": {}}
                gemini_tools.append(gem_tool)
                continue

            properties = t.inputSchema["properties"].copy()
            required = t.inputSchema.get("required", []).copy()

            # Security Sandbox: Remove user_id from the AI's visibility
            if "user_id" in properties:
                del properties["user_id"]
            if "user_id" in required:
                required.remove("user_id")

            # Convert JSON schema types to Gemini UPPERCASE types
            def _convert_node(node):
                if isinstance(node, dict):
                    new_node = {}
                    for k, v in node.items():
                        if k == "type" and isinstance(v, str):
                            # e.g., "integer" -> "INTEGER", "object" -> "OBJECT"
                            if v.lower() == "object":
                                new_node[k] = "OBJECT"
                            elif v.lower() == "string":
                                new_node[k] = "STRING"
                            elif v.lower() == "integer":
                                new_node[k] = "INTEGER"
                            elif v.lower() == "boolean":
                                new_node[k] = "BOOLEAN"
                            elif v.lower() == "number":
                                new_node[k] = "NUMBER"
                            elif v.lower() == "array":
                                new_node[k] = "ARRAY"
                            else:
                                new_node[k] = v.upper()
                        else:
                            new_node[k] = _convert_node(v)
                    return new_node
                elif isinstance(node, list):
                    return [_convert_node(x) for x in node]
                return node

            parameters = {
                "type": "OBJECT",
                "properties": _convert_node(properties)
            }
            if required:
                parameters["required"] = required

            gem_tool["parameters"] = parameters
            gemini_tools.append(gem_tool)

        return gemini_tools

    # -------------------------------------------------------------------
    # Gemini REST API Call
    # -------------------------------------------------------------------

    async def _call_gemini(self, contents: list, dynamic_tool_declarations: list, system_prompt: str):
        """Call Gemini REST API (non-streaming)."""
        url = f"{GEMINI_API_BASE}/models/{GEMINI_AGENT_MODEL}:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": contents,
            "tools": [{"function_declarations": dynamic_tool_declarations}],
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "generation_config": {
                "temperature": 0.3,
                "max_output_tokens": 4096,
            }
        }

        max_retries = 3
        base_delay = 2.0

        async with httpx.AsyncClient(timeout=60.0, transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0")) as client:
            for attempt in range(max_retries + 1):
                resp = await client.post(url, json=payload)

                if resp.status_code == 429:
                    if attempt < max_retries:
                        retry_after = resp.headers.get("retry-after")
                        delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                        logger.warning(f"Gemini 429 rate limit — retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        resp.raise_for_status()

                resp.raise_for_status()
                return resp.json()

    async def _stream_gemini(self, contents: list, dynamic_tool_declarations: list, system_prompt: str):
        """Call Gemini REST API (streaming)."""
        url = f"{GEMINI_API_BASE}/models/{GEMINI_AGENT_MODEL}:streamGenerateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": contents,
            "tools": [{"function_declarations": dynamic_tool_declarations}],
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "generation_config": {
                "temperature": 0.3,
                "max_output_tokens": 4096,
            }
        }

        max_retries = 3
        base_delay = 2.0

        async with httpx.AsyncClient(timeout=60.0, transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0")) as client:
            for attempt in range(max_retries + 1):
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 429:
                        if attempt < max_retries:
                            retry_after = response.headers.get("retry-after")
                            delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                            logger.warning(f"Gemini 429 rate limit — retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            response.raise_for_status()
                    
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        yield chunk
                return

    # -------------------------------------------------------------------
    # Chat — the main entry point
    # -------------------------------------------------------------------

    async def chat(self, message: str, session_id: str):
        """Process a user message using MCP dynamically."""
        if not GEMINI_API_KEY:
            yield "data: {\"type\": \"error\", \"content\": \"I'm offline — GEMINI_API_KEY is not configured in the backend .env file.\"}\n\n"
            return
        if not _MCP_AVAILABLE:
            yield "data: {\"type\": \"error\", \"content\": \"MCP dependency missing in backend environment. Install mcp to enable Clousy tools.\"}\n\n"
            return

        system_prompt = f"{SYSTEM_PROMPT}\n\n{await build_agent_system_prompt(self.user_id, self.db, message)}"

        # Build contents from session history + new message
        history = _session_mgr.get_history(session_id)
        contents = history + [{"role": "user", "parts": [{"text": message}]}]

        # Log the audit event for compliance
        try:
            await log_audit_event(
                user_id=self.user_id,
                action_type="AI_CHAT",
                resource_target="clousy_agent",
                metadata={"message_length": len(message), "session_id": session_id}
            )
        except Exception as e:
            logger.error(f"Audit log failed: {e}")

        try:
            # 1. Start the MCP Client session on demand for this interaction
            server_params = self._get_mcp_params()
            
            # The async context managers will automatically close the MCP node process when done.
            async with stdio_client(server_params) as (mcp_read, mcp_write):
                async with ClientSession(mcp_read, mcp_write) as mcp_session:
                    
                    # 2. Handshake and fetch tools
                    await mcp_session.initialize()
                    mcp_tools_msg = await mcp_session.list_tools()
                    
                    # 3. Securely map schemas for Gemini
                    dynamic_tools = self._mcp_to_gemini_tools(mcp_tools_msg.tools)
                    
                    max_iterations = 6
                    iteration = 0

                    while iteration < max_iterations:
                        iteration += 1

                        if iteration > 1:
                            await asyncio.sleep(1.5)

                        # Always do tool calling via non-streaming first
                        data = await self._call_gemini(contents, dynamic_tools, system_prompt)

                        candidates = data.get("candidates", [])
                        if not candidates:
                            # Instead of returning a string, yield it since the new route expects a stream
                            yield "data: {\"type\": \"error\", \"content\": \"I couldn't generate a response. Please try again.\"}\n\n"
                            return

                        parts = candidates[0].get("content", {}).get("parts", [])
                        fn_calls = [p for p in parts if "functionCall" in p]

                        if not fn_calls:
                            # -------------------------------------------------------------
                            # Final generation: no tool calls requested.
                            # Use text from this generation response directly to avoid
                            # fragile provider stream framing differences.
                            # -------------------------------------------------------------
                            yield "data: {\"type\": \"start_stream\"}\n\n"

                            text_fragments = [
                                part.get("text", "")
                                for part in parts
                                if isinstance(part, dict) and isinstance(part.get("text"), str)
                            ]
                            full_text = "".join(text_fragments).strip()

                            if not full_text:
                                logger.warning("Gemini returned no text parts for session %s", session_id)
                                yield f"data: {json.dumps({'type': 'error', 'content': 'I could not generate a text response. Please try again.'})}\n\n"
                                return

                            payload = json.dumps({"type": "chunk", "content": full_text})
                            yield f"data: {payload}\n\n"

                            # Save to session history memory
                            _session_mgr.add_turn(session_id, "user", [{"text": message}])
                            _session_mgr.add_turn(session_id, "model", [{"text": full_text}])
                            
                            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
                            return

                        # 4. Route Execution securely to MCP Server
                        fn_response_parts = []
                        for fc_part in fn_calls:
                            fc = fc_part["functionCall"]
                            fn_name = fc["name"]
                            fn_args = fc.get("args", {})
                            
                            # Safely inject the actual user context
                            fn_args["user_id"] = self.user_id
                            
                            logger.info(f"MCP Client executing: {fn_name}({json.dumps(fn_args)})")
                            
                            # Yield 'thinking' progress to frontend
                            display_name = fn_name.replace("_", " ").title()
                            thought_markdown = f"> 🧠 **Thinking:** I need to use {display_name}...\n\n"
                            yield f"data: {json.dumps({'type': 'chunk', 'content': thought_markdown})}\n\n"
                            
                            try:
                                # Send standardized MCP call
                                mcp_result = await mcp_session.call_tool(fn_name, arguments=fn_args)
                                # mcp_result.content is a list of TextContent objects. We extract the text string.
                                result_text = mcp_result.content[0].text if mcp_result.content else ""
                                
                                # JSON parse it if it looks like JSON to keep Gemini's response formatting clean
                                try:
                                    result_data = json.loads(result_text)
                                except Exception:
                                    result_data = result_text

                            except Exception as e:
                                logger.error(f"MCP Tool execution failed: {e}")
                                result_data = {"error": str(e)}

                            fn_response_parts.append({
                                "functionResponse": {
                                    "name": fn_name,
                                    "response": {"result": result_data}
                                }
                            })

                        contents.append({"role": "model", "parts": parts})
                        contents.append({"role": "user", "parts": fn_response_parts})

                    yield "data: {\"type\": \"error\", \"content\": \"I'm taking too long to process this. Please try a simpler question.\"}\n\n"
                    return

        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e.response.status_code} {e.response.text}")
            yield f"data: {json.dumps({'type': 'error', 'content': 'AI service error. Please try again.'})}\n\n"
        except Exception as e:
            logger.error(f"Agent MCP processing error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Internal tool error: {str(e)}'})}\n\n"
