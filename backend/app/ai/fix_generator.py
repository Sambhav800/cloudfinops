"""Deterministic remediation command templates for supported cloud resources."""

import logging
import re
import shlex
from typing import Any, Dict, Final

logger = logging.getLogger(__name__)


UNSUPPORTED_FIX_TEMPLATE_MESSAGE: Final = (
    "No trusted remediation template is available for this action and resource."
)


class UnsupportedFixTemplateError(ValueError):
    """Raised when remediation inputs do not match a trusted command template."""

    def __init__(self) -> None:
        super().__init__(UNSUPPORTED_FIX_TEMPLATE_MESSAGE)


_PROVIDER_ALIASES: Final = {
    "aws": "aws",
    "azure": "azure",
}

_SERVICE_ALIASES: Final = {
    "aws": {
        "aws ec2 instance": "ec2_instance",
        "ec2 instance": "ec2_instance",
        "ec2": "ec2_instance",
        "aws ebs volume": "ebs_volume",
        "ebs volume": "ebs_volume",
        "ebs": "ebs_volume",
        "aws elastic ip": "elastic_ip",
        "elastic ip": "elastic_ip",
        "eip": "elastic_ip",
        "aws ebs snapshot": "snapshot",
        "aws ec2 snapshot": "snapshot",
        "ebs snapshot": "snapshot",
        "snapshot": "snapshot",
    },
    "azure": {
        "azure virtual machine": "virtual_machine",
        "azure vm": "virtual_machine",
        "virtual machine": "virtual_machine",
        "vm": "virtual_machine",
        "azure managed disk": "managed_disk",
        "managed disk": "managed_disk",
        "azure public ip address": "public_ip",
        "public ip address": "public_ip",
        "public ip": "public_ip",
        "azure network interface": "network_interface",
        "network interface": "network_interface",
        "nic": "network_interface",
        "azure snapshot": "snapshot",
        "snapshot": "snapshot",
    },
}

_AWS_ID_PATTERNS: Final = {
    "ec2_instance": re.compile(r"^i-(?:[0-9a-f]{8}|[0-9a-f]{17})$"),
    "ebs_volume": re.compile(r"^vol-(?:[0-9a-f]{8}|[0-9a-f]{17})$"),
    "elastic_ip": re.compile(r"^eipalloc-(?:[0-9a-f]{8}|[0-9a-f]{17})$"),
    "snapshot": re.compile(r"^snap-(?:[0-9a-f]{8}|[0-9a-f]{17})$"),
}
_AWS_REGION_PATTERN: Final = re.compile(
    r"^[a-z]{2}(?:-[a-z0-9]+){1,3}-[1-9][0-9]*$"
)
_AWS_SNAPSHOT_ARN_PATTERN: Final = re.compile(
    r"^arn:(?:aws|aws-us-gov|aws-cn):ec2:[a-z0-9-]+:[0-9]{12}:"
    r"snapshot/(snap-(?:[0-9a-f]{8}|[0-9a-f]{17}))$"
)
_SIZE_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SAFE_ARGUMENT_PATTERN: Final = re.compile(
    r"^[A-Za-z0-9/(][A-Za-z0-9._:/@+=,()\-]{0,511}$"
)

_AZURE_SUBSCRIPTION_ID = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_AZURE_RESOURCE_GROUP = r"[a-z0-9._()\-]{1,90}"
_AZURE_RESOURCE_NAME = r"[a-z0-9._()\-]{1,80}"
_AZURE_ID_PATTERNS: Final = {
    "virtual_machine": re.compile(
        rf"^/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        rf"/resourcegroups/{_AZURE_RESOURCE_GROUP}"
        rf"/providers/microsoft\.compute/virtualmachines/{_AZURE_RESOURCE_NAME}$",
        re.IGNORECASE,
    ),
    "managed_disk": re.compile(
        rf"^/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        rf"/resourcegroups/{_AZURE_RESOURCE_GROUP}"
        rf"/providers/microsoft\.compute/disks/{_AZURE_RESOURCE_NAME}$",
        re.IGNORECASE,
    ),
    "public_ip": re.compile(
        rf"^/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        rf"/resourcegroups/{_AZURE_RESOURCE_GROUP}"
        rf"/providers/microsoft\.network/publicipaddresses/{_AZURE_RESOURCE_NAME}$",
        re.IGNORECASE,
    ),
    "network_interface": re.compile(
        rf"^/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        rf"/resourcegroups/{_AZURE_RESOURCE_GROUP}"
        rf"/providers/microsoft\.network/networkinterfaces/{_AZURE_RESOURCE_NAME}$",
        re.IGNORECASE,
    ),
    "snapshot": re.compile(
        rf"^/subscriptions/{_AZURE_SUBSCRIPTION_ID}"
        rf"/resourcegroups/{_AZURE_RESOURCE_GROUP}"
        rf"/providers/microsoft\.compute/snapshots/{_AZURE_RESOURCE_NAME}$",
        re.IGNORECASE,
    ),
}


def _plain_text(value: Any, *, maximum_length: int) -> str:
    """Return a bounded string without control characters or surrounding whitespace."""
    if not isinstance(value, str):
        raise UnsupportedFixTemplateError()

    if not value or value != value.strip() or len(value) > maximum_length:
        raise UnsupportedFixTemplateError()

    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise UnsupportedFixTemplateError()

    return value


def _provider_key(provider: str) -> str:
    normalized = _plain_text(provider, maximum_length=32).casefold()
    try:
        return _PROVIDER_ALIASES[normalized]
    except KeyError as error:
        raise UnsupportedFixTemplateError() from error


def _service_key(provider: str, service_type: str) -> str:
    normalized = _plain_text(service_type, maximum_length=128).casefold()
    try:
        return _SERVICE_ALIASES[provider][normalized]
    except KeyError as error:
        raise UnsupportedFixTemplateError() from error


def _safe_argument(value: str, *, maximum_length: int = 512) -> str:
    argument = _plain_text(value, maximum_length=maximum_length)
    if not _SAFE_ARGUMENT_PATTERN.fullmatch(argument):
        raise UnsupportedFixTemplateError()
    return shlex.quote(argument)


def _aws_resource_id(resource_id: str, service: str) -> str:
    maximum_length = 256 if service == "snapshot" else 64
    identifier = _plain_text(resource_id, maximum_length=maximum_length)
    if service == "snapshot":
        arn_match = _AWS_SNAPSHOT_ARN_PATTERN.fullmatch(identifier)
        if arn_match:
            identifier = arn_match.group(1)

    pattern = _AWS_ID_PATTERNS.get(service)
    if pattern is None or not pattern.fullmatch(identifier):
        raise UnsupportedFixTemplateError()
    return _safe_argument(identifier, maximum_length=64)


def _aws_region(region: str) -> str:
    normalized = _plain_text(region, maximum_length=32)
    if not _AWS_REGION_PATTERN.fullmatch(normalized):
        raise UnsupportedFixTemplateError()
    return _safe_argument(normalized, maximum_length=32)


def _azure_resource_id(resource_id: str, service: str) -> str:
    identifier = _plain_text(resource_id, maximum_length=512)
    pattern = _AZURE_ID_PATTERNS.get(service)
    if pattern is None or not pattern.fullmatch(identifier):
        raise UnsupportedFixTemplateError()
    return _safe_argument(identifier)


def _target_size(recommended_size: str) -> str:
    target = _plain_text(recommended_size, maximum_length=64)
    if not _SIZE_PATTERN.fullmatch(target):
        raise UnsupportedFixTemplateError()
    return _safe_argument(target, maximum_length=64)


class FixScriptGenerator:
    """Generate CLI commands exclusively from trusted, deterministic templates."""

    async def generate_delete_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Generate a trusted deletion command for a supported resource."""
        try:
            _ = resource_name, metadata
            provider_name = _provider_key(provider)
            service = _service_key(provider_name, service_type)

            if provider_name == "aws":
                identifier = _aws_resource_id(resource_id, service)
                safe_region = _aws_region(region)
                templates = {
                    "ec2_instance": (
                        f"aws ec2 terminate-instances --instance-ids {identifier} "
                        f"--region {safe_region}"
                    ),
                    "ebs_volume": (
                        f"aws ec2 delete-volume --volume-id {identifier} "
                        f"--region {safe_region}"
                    ),
                    "elastic_ip": (
                        f"aws ec2 release-address --allocation-id {identifier} "
                        f"--region {safe_region}"
                    ),
                    "snapshot": (
                        f"aws ec2 delete-snapshot --snapshot-id {identifier} "
                        f"--region {safe_region}"
                    ),
                }
                return templates[service]

            identifier = _azure_resource_id(resource_id, service)
            templates = {
                "virtual_machine": f"az vm delete --ids {identifier} --yes",
                "managed_disk": f"az disk delete --ids {identifier} --yes",
                "public_ip": f"az network public-ip delete --ids {identifier}",
                "network_interface": f"az network nic delete --ids {identifier}",
                "snapshot": f"az snapshot delete --ids {identifier}",
            }
            return templates[service]
        except UnsupportedFixTemplateError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise UnsupportedFixTemplateError() from error
        except Exception as error:
            logger.error("Unexpected trusted delete template failure", exc_info=True)
            raise UnsupportedFixTemplateError() from error

    async def generate_resize_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        current_size: str,
        recommended_size: str,
        region: str,
    ) -> str:
        """Generate a trusted resize command for a supported virtual machine."""
        try:
            _ = current_size
            provider_name = _provider_key(provider)
            service = _service_key(provider_name, service_type)
            if service not in {"ec2_instance", "virtual_machine"}:
                raise UnsupportedFixTemplateError()

            target = _target_size(recommended_size)
            if provider_name == "aws":
                identifier = _aws_resource_id(resource_id, service)
                safe_region = _aws_region(region)
                return (
                    f"aws ec2 modify-instance-attribute --instance-id {identifier} "
                    f"--instance-type Value={target} --region {safe_region}"
                )

            identifier = _azure_resource_id(resource_id, service)
            return f"az vm resize --ids {identifier} --size {target}"
        except UnsupportedFixTemplateError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise UnsupportedFixTemplateError() from error
        except Exception as error:
            logger.error("Unexpected trusted resize template failure", exc_info=True)
            raise UnsupportedFixTemplateError() from error

    async def generate_stop_command(
        self,
        provider: str,
        service_type: str,
        resource_id: str,
        resource_name: str,
        region: str,
    ) -> str:
        """Generate a trusted stop/deallocate command for a supported VM."""
        try:
            _ = resource_name
            provider_name = _provider_key(provider)
            service = _service_key(provider_name, service_type)
            if service not in {"ec2_instance", "virtual_machine"}:
                raise UnsupportedFixTemplateError()

            if provider_name == "aws":
                identifier = _aws_resource_id(resource_id, service)
                safe_region = _aws_region(region)
                return (
                    f"aws ec2 stop-instances --instance-ids {identifier} "
                    f"--region {safe_region}"
                )

            identifier = _azure_resource_id(resource_id, service)
            return f"az vm deallocate --ids {identifier}"
        except UnsupportedFixTemplateError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise UnsupportedFixTemplateError() from error
        except Exception as error:
            logger.error("Unexpected trusted stop template failure", exc_info=True)
            raise UnsupportedFixTemplateError() from error


_generator: FixScriptGenerator | None = None


def get_fix_generator() -> FixScriptGenerator:
    """Get or create the deterministic fix script generator singleton."""
    global _generator
    if _generator is None:
        _generator = FixScriptGenerator()
    return _generator
