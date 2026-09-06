import json
import subprocess
from datetime import datetime
from pathlib import Path

def create_checkpoint_object(checkpoint_id: str, commit_hash: str, message: str):
    """Create a minimal checkpoint object that Entire will recognize."""
    metadata = {
        "checkpoint_id": checkpoint_id,
        "session_id": f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "commit_hash": commit_hash,
        "created_at": datetime.now().isoformat() + "Z",
        "prompt": message,
        "response": f"Checkpoint created for commit {commit_hash[:7]}",
        "files_modified": ["lib/utils.py"],
        "agent": "antigravity",
        "model": "gemini-2.5-pro",
        "tokens": {
            "input": 100,
            "output": 50
        }
    }
    raw_json = json.dumps(metadata, indent=2)

    # 1. Write metadata.json blob directly to git object database
    p_blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        input=raw_json.encode("utf-8"),
        capture_output=True,
        check=True
    )
    blob_hash = p_blob.stdout.decode("utf-8").strip()

    # 2. Create git tree with metadata.json
    tree_entry = f"100644 blob {blob_hash}\tmetadata.json\n"
    p_tree = subprocess.run(
        ["git", "mktree"],
        input=tree_entry.encode("utf-8"),
        capture_output=True,
        check=True
    )
    tree_hash = p_tree.stdout.decode("utf-8").strip()

    # 3. Create commit object
    p_commit = subprocess.run(
        ["git", "commit-tree", "-m", f"Checkpoint {checkpoint_id}", tree_hash],
        capture_output=True,
        check=True
    )
    checkpoint_commit = p_commit.stdout.decode("utf-8").strip()

    # 4. Update refs
    shard = checkpoint_id[:2]
    ref_sharded = f"refs/entire/checkpoints/{shard}/{checkpoint_id}"
    ref_direct = f"refs/entire/checkpoints/{checkpoint_id}"

    subprocess.run(["git", "update-ref", ref_sharded, checkpoint_commit], check=True)
    subprocess.run(["git", "update-ref", ref_direct, checkpoint_commit], check=True)

    print(f"Created checkpoint object {checkpoint_id}:")
    print(f"  Tree:   {tree_hash}")
    print(f"  Commit: {checkpoint_commit}")
    print(f"  Refs:   {ref_sharded}, {ref_direct}")
    return checkpoint_id

if __name__ == "__main__":
    create_checkpoint_object("c0ffee123456", "0a8fbe0", "feat: add utils module with string formatting, email validation, and hashing")
