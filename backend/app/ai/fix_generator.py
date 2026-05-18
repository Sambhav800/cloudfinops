"""
AI Fix Script Generator
Uses Gemini AI to generate executable CLI commands for fixing cloud waste.
"""

import logging
import os
from typing import Dict, Any, Optional
import shlex

_USE_GOOGLE_GENAI = False
genai_client = None
try:
    from google import genai as genai_client
    _USE_GOOGLE_GENAI = True
except Exception:
    genai_client = None

from ..config import GEMINI_API_KEY, GEMINI_FIX_MODEL

logger = logging.getLogger(__name__)


class _GenAIResponseAdapter:
    """Expose a stable `.text` attribute for existing callsites."""

    def __init__(self, response: Any):
        self._response = response
        self.text = getattr(response, "text", "") or ""


class _AsyncGeminiModel:
    """Compat layer for `generate_content_async` using google.genai client."""

    def __init__(self, client: Any, model_name: str):
        self._client = client
        self._model_name = model_name

    async def generate_content_async(self, prompt: str) -> _GenAIResponseAdapter:
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        return _GenAIResponseAdapter(response)


def _shell_quote(value: Any) -> str:
    """Quote potentially untrusted values before inserting into shell commands."""
    return shlex.quote(str(value or ""))


class FixScriptGenerator:
    """
    AI-powered fix script generator using Google Gemini.
    Generates precise CLI commands to fix cloud waste issues.
    """
    
    def __init__(self):
        """Initialize Gemini AI client. Gracefully degrades if no API key."""
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured - fix generation will use fallback templates")
            self.model = None
        elif not _USE_GOOGLE_GENAI or genai_client is None:
            logger.warning("google-genai package unavailable - fix generation will use fallback templates")
            self.model = None
        else:
            self.client = genai_client.Client(api_key=GEMINI_API_KEY)
            self.model = _AsyncGeminiModel(self.client, GEMINI_FIX_MODEL)
    
    async def generate_delete_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Generate a CLI command to delete a specific resource.
        
        Args:
            provider: Cloud provider (AWS, Azure, GCP)
            service_type: Type of resource (VM, Disk, IP, etc.)
            resource_id: Unique resource identifier
            resource_name: Human-readable resource name
            region: Cloud region
            metadata: Additional context about the resource
            
        Returns:
            CLI command string to delete the resource
        """
        if not self.model:
            return self._generate_fallback_command(
                provider, service_type, resource_id, resource_name, region
            )
        
        prompt = f"""You are a cloud infrastructure expert. Generate a precise CLI command to delete the following resource.

**Resource Details:**
- Cloud Provider: {provider}
- Service Type: {service_type}
- Resource ID: {resource_id}
- Resource Name: {resource_name}
- Region: {region}
- Additional Info: {metadata}

**Requirements:**
1. Generate ONLY the exact CLI command, no explanations
2. Use the official CLI tool ({self._get_cli_tool(provider)})
3. Include proper flags for non-interactive deletion (--yes, --force, etc.)
4. Include region specification if required
5. For Azure: use resource ID format
6. For AWS: use resource ID with proper service prefix

**Output Format:**
Return ONLY the command, one line, ready to copy-paste.

Example for Azure disk: `az disk delete --ids /subscriptions/.../resourceGroups/.../providers/Microsoft.Compute/disks/disk-name --yes`
Example for AWS volume: `aws ec2 delete-volume --volume-id vol-1234567890abcdef0 --region us-east-1`
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            script = response.text.strip()
            
            # Clean up the response (remove code block markers if present)
            script = script.replace("```bash", "").replace("```", "").strip()
            
            return script
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            # Fallback to template-based generation
            return self._generate_fallback_command(
                provider, service_type, resource_id, resource_name, region
            )
    
    async def generate_resize_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        current_size: str,
        recommended_size: str,
        region: str
    ) -> str:
        """
        Generate a CLI command to resize/downscale a resource.
        """
        if not self.model:
            return f"# Resize {resource_id} from {current_size} to {recommended_size} (AI unavailable)"
        
        prompt = f"""Generate a CLI command to resize this cloud resource to save costs.

**Resource:**
- Provider: {provider}
- Type: {service_type}
- ID: {resource_id}
- Current Size: {current_size}
- Recommended Size: {recommended_size}
- Region: {region}

Generate ONLY the command to change the size/SKU. Include --yes or --force flags.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            script = response.text.strip()
            script = script.replace("```bash", "").replace("```", "").strip()
            return script
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"# Error generating resize command: {e}"
    
    async def generate_stop_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str
    ) -> str:
        """
        Generate a CLI command to stop (deallocate) a resource.
        """
        if not self.model:
            return self._generate_fallback_stop_command(
                provider, service_type, resource_id, resource_name, region
            )
        
        prompt = f"""Generate a CLI command to stop/deallocate this cloud resource.

**Resource:**
- Provider: {provider}
- Type: {service_type}
- ID: {resource_id}
- Name: {resource_name}
- Region: {region}

Generate ONLY the command to stop/deallocate. For VMs, use deallocate to save costs.
"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            script = response.text.strip()
            script = script.replace("```bash", "").replace("```", "").strip()
            return script
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._generate_fallback_stop_command(
                provider, service_type, resource_id, resource_name, region
            )
    
    def _get_cli_tool(self, provider: str) -> str:
        """Get the CLI tool name for a provider."""
        tools = {
            "AWS": "AWS CLI (aws)",
            "Azure": "Azure CLI (az)",
            "GCP": "gcloud CLI"
        }
        return tools.get(provider, "CLI")
    
    def _generate_fallback_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str
    ) -> str:
        """
        Fallback template-based command generation if AI fails.
        """
        if provider == "Azure":
            safe_id = _shell_quote(resource_id)
            if "disk" in service_type.lower():
                return f"az disk delete --ids {safe_id} --yes"
            elif "ip" in service_type.lower():
                return f"az network public-ip delete --ids {safe_id}"
            elif "nic" in service_type.lower():
                return f"az network nic delete --ids {safe_id}"
            elif "vm" in service_type.lower() or "virtual machine" in service_type.lower():
                return f"az vm delete --ids {safe_id} --yes"
            else:
                return f"az resource delete --ids {safe_id}"
        
        elif provider == "AWS":
            safe_id = _shell_quote(resource_id)
            safe_region = _shell_quote(region)
            if "ebs" in service_type.lower() or "volume" in service_type.lower():
                return f"aws ec2 delete-volume --volume-id {safe_id} --region {safe_region}"
            elif "eip" in service_type.lower() or "elastic ip" in service_type.lower():
                return f"aws ec2 release-address --allocation-id {safe_id} --region {safe_region}"
            elif "snapshot" in service_type.lower():
                return f"aws ec2 delete-snapshot --snapshot-id {safe_id} --region {safe_region}"
            elif "ec2" in service_type.lower() or "instance" in service_type.lower():
                return f"aws ec2 terminate-instances --instance-ids {safe_id} --region {safe_region}"
            else:
                return f"# Manual deletion required for {service_type}: {safe_id}"
        
        return f"# Unsupported provider or service type: {provider} / {service_type}"
    
    def _generate_fallback_stop_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str
    ) -> str:
        """Fallback for stop commands."""
        if provider == "Azure":
            if "vm" in service_type.lower():
                return f"az vm deallocate --ids {_shell_quote(resource_id)}"
        elif provider == "AWS":
            if "ec2" in service_type.lower() or "instance" in service_type.lower():
                return (
                    f"aws ec2 stop-instances --instance-ids {_shell_quote(resource_id)} "
                    f"--region {_shell_quote(region)}"
                )
        
        return f"# Stop command not available for {service_type}"


# Singleton instance
_generator = None

def get_fix_generator() -> FixScriptGenerator:
    """Get or create the fix script generator instance."""
    global _generator
    if _generator is None:
        _generator = FixScriptGenerator()
    return _generator
