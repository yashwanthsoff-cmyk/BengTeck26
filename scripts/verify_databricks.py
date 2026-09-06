import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config
import requests
import json

sys.stdout.reconfigure(encoding='utf-8')

print('=' * 60)
print('DATABRICKS VERIFICATION')
print('=' * 60)

# Test 1: Check Catalog
print('\n[1/5] Checking Unity Catalog...')
headers = {'Authorization': f'Bearer {config.DATABRICKS_TOKEN}'}
url = f'{config.DATABRICKS_HOST}/api/2.1/unity-catalog/catalogs/{config.DATABRICKS_CATALOG}'
r = requests.get(url, headers=headers)
if r.status_code == 200:
    print(f'  ✅ Catalog {config.DATABRICKS_CATALOG} exists')
else:
    print(f'  ❌ Catalog error: {r.status_code} - {r.text[:100]}')

# Test 2: Check Schema
print('\n[2/5] Checking Schema...')
url = f'{config.DATABRICKS_HOST}/api/2.1/unity-catalog/schemas/{config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}'
r = requests.get(url, headers=headers)
if r.status_code == 200:
    print(f'  ✅ Schema {config.DATABRICKS_SCHEMA} exists')
else:
    print(f'  ❌ Schema error: {r.status_code} - {r.text[:100]}')

# Test 3: Check Volume File
print('\n[3/5] Checking Checkpoint Export File...')
url = f'{config.DATABRICKS_HOST}/api/2.0/fs/files/Volumes/{config.DATABRICKS_CATALOG}/{config.DATABRICKS_SCHEMA}/raw_exports/checkpoints_export.json'
r = requests.head(url, headers=headers)
if r.status_code == 200:
    print(f'  ✅ File exists: /Volumes/{config.DATABRICKS_CATALOG}/{config.DATABRICKS_SCHEMA}/raw_exports/checkpoints_export.json')
    
    # Get file size
    r = requests.get(url, headers=headers)
    data = json.loads(r.content)
    print(f'  ✅ File size: {len(r.content)} bytes')
    print(f'  ✅ Checkpoints in file: {len(data)}')
    for cp in data:
        print(f"    - {cp.get('checkpoint_id', 'unknown')}")
else:
    print(f'  ❌ File error: {r.status_code}')
    print(f'  Expected path: /Volumes/{config.DATABRICKS_CATALOG}/{config.DATABRICKS_SCHEMA}/raw_exports/checkpoints_export.json')

# Test 4: Check Delta Tables
print('\n[4/5] Checking Delta Tables...')
url = f'{config.DATABRICKS_HOST}/api/2.1/unity-catalog/tables?catalog_name={config.DATABRICKS_CATALOG}&schema_name={config.DATABRICKS_SCHEMA}'
r = requests.get(url, headers=headers)
if r.status_code == 200:
    tables = r.json().get('tables', [])
    print(f'  ✅ Found {len(tables)} Delta tables:')
    for t in tables[:10]:
        print(f"    - {t.get('name')}")
    if len(tables) > 10:
        print(f'    ... and {len(tables) - 10} more')
else:
    print(f'  ❌ Tables error: {r.status_code}')

# Test 5: Check SQL Warehouse
print('\n[5/5] Checking SQL Warehouse...')
url = f'{config.DATABRICKS_HOST}/api/2.0/sql/warehouses/{config.DATABRICKS_WAREHOUSE_ID}'
r = requests.get(url, headers=headers)
if r.status_code == 200:
    wh = r.json()
    print(f"  ✅ SQL Warehouse: {wh.get('name', 'unknown')}")
    print(f"  ✅ Status: {wh.get('state', 'unknown')}")
    print(f"  ✅ Type: {wh.get('warehouse_type', 'unknown')}")
else:
    print(f'  ❌ Warehouse error: {r.status_code}')

print('\n' + '=' * 60)
print('VERIFICATION COMPLETE')
print('=' * 60)
