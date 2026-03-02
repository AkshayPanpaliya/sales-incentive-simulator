"""
config_loader.py
----------------
Configuration loader for the Sales Incentive Compensation Simulator.

Reads ``config/incentive_plan.json`` (or a caller-specified path), validates
that all required top-level keys are present, and caches the result in a
module-level variable so the file is only parsed once per process lifetime.

Raises
------
ConfigValidationError
    If the configuration file is missing required keys or cannot be parsed.
FileNotFoundError
    If the configuration file does not exist at the resolved path.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ConfigValidationError(Exception):
    """Raised when the incentive-plan configuration fails validation."""


# ---------------------------------------------------------------------------
# Module-level cache – populated on first successful load
# ---------------------------------------------------------------------------
_config_cache: dict[str, Any] | None = None

# Keys that must exist at the top level of the JSON document.
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "effective_from",
        "tiers",
        "accelerator",
        "roles",
        "regions",
        "product_categories",
        "customer_segments",
    }
)

# Sub-keys required within each tier entry
_REQUIRED_TIER_KEYS: frozenset[str] = frozenset(
    {"threshold_min", "threshold_max", "commission_rate"}
)

# Default path relative to the project root
_DEFAULT_CONFIG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "incentive_plan.json"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: str | None = None) -> dict[str, Any]:
    """
    Load and validate the incentive-plan configuration.

    The configuration is cached after the first successful load.  Pass a
    different *path* only when you explicitly need to reload from a different
    file (e.g. in tests); the cache is **not** invalidated automatically.

    Parameters
    ----------
    path : str or None, optional
        Absolute or relative path to the JSON config file.  Defaults to
        ``config/incentive_plan.json`` relative to the project root.

    Returns
    -------
    dict
        Parsed and validated configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If the resolved file does not exist.
    ConfigValidationError
        If required keys are absent or tier entries are malformed.
    json.JSONDecodeError
        If the file cannot be parsed as valid JSON.
    """
    global _config_cache

    # Return cached config when available and no explicit path override.
    if _config_cache is not None and path is None:
        logger.debug("Returning cached incentive-plan configuration.")
        return _config_cache

    resolved_path: str = path or _DEFAULT_CONFIG_PATH

    if not os.path.isfile(resolved_path):
        raise FileNotFoundError(
            f"Configuration file not found: '{resolved_path}'.  "
            "Ensure 'config/incentive_plan.json' exists in the project root."
        )

    logger.info("Loading configuration from '%s'.", resolved_path)

    with open(resolved_path, encoding="utf-8") as fh:
        config: dict[str, Any] = json.load(fh)

    _validate_config(config)

    if path is None:
        _config_cache = config
        logger.info(
            "Configuration v%s loaded and cached (effective from %s).",
            config.get("version"),
            config.get("effective_from"),
        )

    return config


def reset_cache() -> None:
    """
    Clear the module-level configuration cache.

    Useful in tests that need to reload the configuration from a different
    path between test cases.
    """
    global _config_cache
    _config_cache = None
    logger.debug("Configuration cache cleared.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_config(config: dict[str, Any]) -> None:
    """
    Validate the top-level structure and critical sub-structures of *config*.

    Parameters
    ----------
    config : dict
        Raw parsed JSON dictionary.

    Raises
    ------
    ConfigValidationError
        On any structural or value-level problem.
    """
    # ── Top-level keys ──────────────────────────────────────────────────────
    missing_keys: set[str] = _REQUIRED_KEYS - set(config.keys())
    if missing_keys:
        raise ConfigValidationError(
            f"Configuration is missing required top-level keys: {sorted(missing_keys)}"
        )

    # ── Tiers ───────────────────────────────────────────────────────────────
    tiers = config["tiers"]
    if not isinstance(tiers, list) or len(tiers) == 0:
        raise ConfigValidationError(
            "'tiers' must be a non-empty list of tier objects."
        )
    for i, tier in enumerate(tiers):
        missing_tier_keys = _REQUIRED_TIER_KEYS - set(tier.keys())
        if missing_tier_keys:
            raise ConfigValidationError(
                f"Tier at index {i} is missing keys: {sorted(missing_tier_keys)}"
            )
        if tier["threshold_min"] >= tier["threshold_max"]:
            raise ConfigValidationError(
                f"Tier at index {i}: threshold_min ({tier['threshold_min']}) "
                f"must be less than threshold_max ({tier['threshold_max']})."
            )
        if not (0.0 <= tier["commission_rate"] <= 1.0):
            raise ConfigValidationError(
                f"Tier at index {i}: commission_rate must be in [0, 1], "
                f"got {tier['commission_rate']}."
            )

    # ── Accelerator ─────────────────────────────────────────────────────────
    accel = config["accelerator"]
    if "threshold" not in accel or "rate" not in accel:
        raise ConfigValidationError(
            "'accelerator' must contain 'threshold' and 'rate' keys."
        )

    # ── Roles ───────────────────────────────────────────────────────────────
    if not isinstance(config["roles"], dict) or len(config["roles"]) == 0:
        raise ConfigValidationError("'roles' must be a non-empty dict.")

    # ── Lists ───────────────────────────────────────────────────────────────
    for list_key in ("regions", "product_categories", "customer_segments"):
        if not isinstance(config[list_key], list) or len(config[list_key]) == 0:
            raise ConfigValidationError(
                f"'{list_key}' must be a non-empty list."
            )

    logger.debug("Configuration validation passed.")
