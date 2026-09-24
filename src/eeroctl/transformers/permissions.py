"""Transformers for the eero-api 8.0.1 permissions family.

Facade method (`eero.EeroClient`, eero-api 8.0.1 `client.py`):
    get_permissions(network_id=None) -> Dict[str, Any]  -- client.py:2369

Unlike most other phase-A facade methods, the shape here is documented at the
SDK layer (`eero/api/permissions.py:38-41`): "Returns `permissions` (a
per-capability mapping) and `role`." Phase A still keeps the envelope-only
`extract_permissions` as the primitive (consistent with every other
transformer module) but adds two small accessors for the two documented keys.
"""

from typing import Any, Dict, Optional

from .base import extract_data


def extract_permissions(raw: Dict[str, Any]) -> Any:
    """Unwrap the `data` field of a `get_permissions` envelope."""
    return extract_data(raw)


def extract_role(permissions_data: Any) -> Optional[str]:
    """Extract `data.role` (`eero/api/permissions.py:41`)."""
    if isinstance(permissions_data, dict):
        role = permissions_data.get("role")
        return str(role) if role is not None else None
    return None


def extract_capability_map(permissions_data: Any) -> Dict[str, Any]:
    """Extract `data.permissions`, the per-capability mapping (`permissions.py:41`)."""
    if isinstance(permissions_data, dict):
        capabilities = permissions_data.get("permissions")
        if isinstance(capabilities, dict):
            return capabilities
    return {}
