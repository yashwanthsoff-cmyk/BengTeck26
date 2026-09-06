# lib/entire_adapter.py
"""
Adapter for Entire CLI checkpoint output.
Provides uniform access to checkpoint attributes across various Entire CLI output formats.
"""
import subprocess
import json
from typing import Any, Dict, List

class EntireAdapter:
    """Base adapter interface for reading checkpoints."""
    def read_checkpoints(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

class CheckpointListJsonAdapter(EntireAdapter):
    """Adapter for 'entire checkpoint list --json' output."""
    def __init__(self, raw_json: str):
        if not raw_json or not raw_json.strip():
            self.data = []
        else:
            self.data = json.loads(raw_json)
    
    def read_checkpoints(self) -> List[Dict[str, Any]]:
        if isinstance(self.data, list):
            return self.data
        return [self.data] if self.data else []

class CheckpointExplainAdapter(EntireAdapter):
    """Adapter for 'entire checkpoint explain <id> --json' output."""
    def __init__(self, checkpoint_id: str):
        self.checkpoint_id = checkpoint_id
    
    def read_checkpoints(self) -> List[Dict[str, Any]]:
        result = subprocess.run(
            ["entire", "checkpoint", "explain", self.checkpoint_id, "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        return [data] if not isinstance(data, list) else data

def make_adapter(raw_json: str = None, checkpoint_id: str = None) -> EntireAdapter:
    """Factory function returning the appropriate adapter."""
    if checkpoint_id:
        return CheckpointExplainAdapter(checkpoint_id)
    return CheckpointListJsonAdapter(raw_json or "[]")
