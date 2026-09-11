"""lib/contract_schema.py — Draft-7 JSON Schema and Validation for Agent Resume Contracts.
Implements Gap 1 of Feature 4 (Resume Contract):
Enforces pre-export/pre-save schema validation with graceful presence checking fallback.
"""
from typing import Dict, List, Any

# Draft-7 JSON Schema for Resume Contracts
RESUME_CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ResumeContract",
    "type": "object",
    "required": [
        "checkpoint_id",
        "session_id",
        "generated_at",
        "version",
        "unresolved_requirements",
        "do_not_retry",
        "flagged_gaps",
        "integrity_check"
    ],
    "properties": {
        "checkpoint_id": {"type": "string"},
        "session_id": {"type": "string"},
        "generated_at": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "template": {"type": "string"},
        "contract_purpose": {"type": "string"},
        "synthesis_weights": {"type": "object"},
        "conflicts": {"type": "array"},
        "unresolved_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "status"],
                "properties": {
                    "text": {"type": "string"},
                    "status": {"type": "string"},
                    "priority": {"type": ["integer", "string", "null"]}
                }
            }
        },
        "do_not_retry": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["reason_abandoned"],
                "properties": {
                    "reason_abandoned": {"type": ["string", "null"]},
                    "suggested_alternative": {"type": ["string", "null"]},
                    "used_fallback_source": {"type": "boolean"}
                }
            }
        },
        "flagged_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause": {"type": ["string", "null"]}
                }
            }
        },
        "integrity_check": {
            "type": "object",
            "required": ["integrity_score"],
            "properties": {
                "integrity_score": {"type": ["number", "null"], "minimum": 0.0, "maximum": 1.0},
                "reason": {"type": ["string", "null"]}
            }
        },
        "degraded": {"type": "boolean"},
        "degraded_reasons": {
            "type": "array",
            "items": {"type": "string"}
        },
        "failure_reason": {"type": ["string", "null"]},
        "release_readiness": {"type": "object"},
        "summary": {"type": "object"},
        "schema_valid": {"type": "boolean"},
        "validation_errors": {"type": "array"}
    }
}


def validate_contract_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validates contract payload against Draft-7 JSON schema.
    If jsonschema is unavailable, falls back to presence checking of required fields.
    Never crashes callers — returns a structured validation result.
    """
    errors: List[str] = []
    warning: str = None

    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(RESUME_CONTRACT_SCHEMA)
        raw_errors = list(validator.iter_errors(payload))
        if raw_errors:
            for err in raw_errors:
                field = ".".join([str(p) for p in err.path]) if err.path else "root"
                errors.append(f"{field}: {err.message}")
            return {
                "valid": False,
                "errors": sorted(errors),
                "warning": None
            }
        return {
            "valid": True,
            "errors": [],
            "warning": None
        }
    except ImportError:
        # Graceful fallback: check required top-level keys
        warning = "jsonschema package not found; validated required top-level keys only."
        for key in RESUME_CONTRACT_SCHEMA["required"]:
            if key not in payload:
                errors.append(f"root: '{key}' is a required property")
        return {
            "valid": len(errors) == 0,
            "errors": sorted(errors),
            "warning": warning
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Schema validation internal error: {str(e)}"],
            "warning": "Exception raised during schema validation."
        }
