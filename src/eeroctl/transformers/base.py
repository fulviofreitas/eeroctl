"""Base transformer utilities for raw API responses."""

from typing import Any, Dict, List, Optional


def extract_data(raw: Dict[str, Any]) -> Any:
    """Extract the data field from a raw API response.

    Args:
        raw: Raw API response with meta and data fields

    Returns:
        The data field contents, or the raw dict if no data field
    """
    if not raw:
        return {}
    return raw.get("data", raw)


def extract_list(raw: Dict[str, Any], key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract a list from a raw API response.

    Handles various response formats:
    - {"meta": {...}, "data": [...]}
    - {"meta": {...}, "data": {"key": [...]}}
    - {"meta": {...}, "data": {"key": {"data": [...]}}}
    - {"meta": {...}, "data": {"data": [...]}}

    Args:
        raw: Raw API response
        key: Optional key to look for in the data field

    Returns:
        List of items
    """
    if not raw:
        return []

    data = raw.get("data", raw)

    # If data is already a list, return it
    if isinstance(data, list):
        return data

    # If data is a dict, look for the list
    if isinstance(data, dict):
        # Try the specific key first
        if key and key in data:
            result = data[key]
            # Handle nested structure: {"networks": {"count": N, "data": [...]}}
            if isinstance(result, dict) and "data" in result:
                nested = result["data"]
                if isinstance(nested, list):
                    return nested
            if isinstance(result, list):
                return result

        # Try common keys
        for k in ["data", "networks", "devices", "eeros", "profiles"]:
            if k in data:
                result = data[k]
                # Handle nested structure
                if isinstance(result, dict) and "data" in result:
                    nested = result["data"]
                    if isinstance(nested, list):
                        return nested
                if isinstance(result, list):
                    return result

    return []


def extract_id_from_url(url: Optional[str]) -> str:
    """Extract the ID from an API URL.

    Args:
        url: API URL like "/2.2/networks/3401709"

    Returns:
        The extracted ID or empty string
    """
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1]


def safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get a nested value from a dict.

    Args:
        data: The dictionary to search
        *keys: Path of keys to follow
        default: Default value if not found

    Returns:
        The value at the path or the default
    """
    result: Any = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default
