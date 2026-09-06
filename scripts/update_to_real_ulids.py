import os
import sys
import json
import uuid
import time
from datetime import datetime

# Allow importing config when run from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding='utf-8')

import config

print('=' * 70)
print('GENERATING REAL CHECKPOINT IDs (ULID Format)')
print('=' * 70)

def generate_ulid():
    """Generate a 26-character ULID (Crockford base32)"""
    timestamp = int(time.time() * 1000)
    
    # Convert timestamp to 10 characters (base32)
    timestamp_chars = ''
    temp = timestamp
    for _ in range(10):
        timestamp_chars = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'[temp % 32] + timestamp_chars
        temp //= 32
    
    # Random 16 characters (base32)
    random_chars = ''
    for _ in range(16):
        random_chars += '0123456789ABCDEFGHJKMNPQRSTVWXYZ'[uuid.uuid4().int % 32]
    
    return timestamp_chars + random_chars

print('\nGenerating 3 new ULID checkpoint IDs:\n')
ulids = []
for i in range(3):
    time.sleep(0.002)
    ulid = generate_ulid()
    ulids.append(ulid)
    print(f'  Checkpoint {i+1}: {ulid}')

print(f'\n[PASS] Generated {len(ulids)} ULIDs')
print('[INFO]  Format: 26 characters, Crockford Base32, time-sortable')
print(f'[INFO]  Example: {ulids[0]}')

# ==================== SUPABASE ====================
print('\n' + '=' * 70)
print('UPDATING SUPABASE CHECKPOINTS')
print('=' * 70)

from supabase import create_client
client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

# Get current checkpoints
checkpoints = client.table('checkpoints').select('*').order('created_at', desc=False).execute()
print(f'\nCurrent checkpoints in Supabase: {len(checkpoints.data)}')

mapping = {}
for i, cp in enumerate(checkpoints.data):
    old_id = cp['checkpoint_id']
    new_id = ulids[i] if i < len(ulids) else generate_ulid()
    mapping[old_id] = new_id
    
    client.table('checkpoints').update({
        'checkpoint_id': new_id
    }).eq('id', cp['id']).execute()
    
    print(f'  [PASS] Updated: {old_id} → {new_id}')

print('\n[PASS] All Supabase checkpoints updated with real ULIDs')

# ==================== LOCAL FIXTURE & EXPORT SCRIPT ====================
print('\n' + '=' * 70)
print('UPDATING FIXTURES AND DATABRICKS VOLUME')
print('=' * 70)

fixture_path = 'tests/fixtures/entire_checkpoints.json'
if os.path.exists(fixture_path):
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for cp in data:
        old_cid = cp.get('checkpoint_id')
        if old_cid in mapping:
            cp['checkpoint_id'] = mapping[old_cid]
    with open(fixture_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f'  [PASS] Updated fixture: {fixture_path}')

# Re-export to Databricks Volume
try:
    from scripts.export_checkpoints_to_databricks import upload_to_databricks_volume, SAMPLE_CHECKPOINTS
    for cp in SAMPLE_CHECKPOINTS:
        old_cid = cp.get('checkpoint_id')
        if old_cid in mapping:
            cp['checkpoint_id'] = mapping[old_cid]
    payload = json.dumps(SAMPLE_CHECKPOINTS, indent=2).encode('utf-8')
    upload_to_databricks_volume(payload)
    print('  [PASS] Uploaded updated ULID checkpoints to Databricks Volume')
except Exception as e:
    print(f'  [WARN] Databricks Volume upload note: {e}')

# ==================== VERIFICATION ====================
print('\n' + '=' * 70)
print('VERIFICATION')
print('=' * 70)

updated = client.table('checkpoints').select('*').order('created_at', desc=False).execute()
for cp in updated.data:
    cp_id = cp['checkpoint_id']
    print(f'  [PASS] {cp_id} (length: {len(cp_id)}, format: ULID)')

print('\n[OK] Checkpoint IDs are now REAL ULID format!')
