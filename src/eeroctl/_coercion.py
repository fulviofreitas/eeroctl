"""Numeric coercion utilities for raw Eero API fields.

The Eero Cloud API occasionally changes field shapes between numeric scalars
and dicts (e.g., ``uptime`` changed from ``3600`` to ``{"seconds": 3600, ...}``).
This module provides ``coerce_numeric`` to normalise both shapes at the
transformer and formatter layers, keeping downstream callers clean.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Keys tried in order when coercing a dict to a number.
_DICT_NUMERIC_KEYS = ("seconds", "value", "current", "total", "count")

# Deduplicated set of (field_name, sorted_keys_tuple) for which we have
# already emitted a DEBUG log so we don't spam on repeated calls.
_logged_unknown: set[tuple[str, tuple[str, ...]]] = set()


def coerce_numeric(
    value: object,
    field_name: str = "<unknown>",
) -> Optional[Union[int, float]]:
    """Coerce a raw API field value to a numeric type.

    Handles the case where the Eero API changes a numeric field to a dict
    (e.g. ``uptime`` going from ``3600`` to ``{"seconds": 3600, "human": "1h"}``).

    Coercion rules:
    - ``int`` / ``float``  — returned as-is (cast to ``int`` when the value is
      an exact integer so callers doing ``// 3600`` arithmetic keep working).
    - ``str``              — parsed via ``float()``; ``None`` on ``ValueError``.
    - ``dict``             — tries keys ``seconds``, ``value``, ``current``,
      ``total``, ``count`` in order; recursively coerces the first hit.
      Logs once at DEBUG for unknown dicts (deduped by field name + key set).
    - ``None`` / other     — returns ``None``.

    Args:
        value: The raw field value from the API response.
        field_name: Name of the field being coerced (used in log messages).

    Returns:
        A numeric value (``int`` or ``float``), or ``None`` when coercion fails.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        # bool is a subclass of int — treat as non-numeric.
        return None

    if isinstance(value, (int, float)):
        # Preserve int identity for downstream integer arithmetic.
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    if isinstance(value, str):
        try:
            parsed = float(value)
            return int(parsed) if parsed.is_integer() else parsed
        except ValueError:
            return None

    if isinstance(value, dict):
        for key in _DICT_NUMERIC_KEYS:
            if key in value:
                return coerce_numeric(value[key], field_name=f"{field_name}.{key}")

        # None of the known keys matched — log once per (field, key-set) pair.
        key_tuple = tuple(sorted(value.keys()))
        log_key = (field_name, key_tuple)
        if log_key not in _logged_unknown:
            _logged_unknown.add(log_key)
            logger.debug(
                "coerce_numeric: could not extract number from dict for field %r "
                "(keys=%r) — returning None",
                field_name,
                key_tuple,
            )
        return None

    return None
