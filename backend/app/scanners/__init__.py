from .aws import AWSScanner

__all__ = ["AWSScanner", "AzureScanner", "GCPScanner", "KubernetesScanner"]


def __getattr__(name: str):
    """Lazily load optional scanners so route imports stay lightweight."""
    if name == "AzureScanner":
        try:
            from .azure import AzureScanner
        except ImportError:
            return None
        return AzureScanner

    if name == "GCPScanner":
        try:
            from .gcp import GCPScanner
        except ImportError:
            return None
        return GCPScanner

    if name == "KubernetesScanner":
        try:
            from .kubernetes import KubernetesScanner
        except ImportError:
            return None
        return KubernetesScanner

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
