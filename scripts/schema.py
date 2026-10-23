"""Create the database schema by sending supabase/schema.sql to the Supabase Management API.

Needs in config.secret.json:  SUPABASE_ACCESS_TOKEN  (Account > Access Tokens)
Needs in config.public.json:  SUPABASE_URL          (project ref is derived from it)
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

public = json.loads((ROOT / "config.public.json").read_text())
secret = json.loads((ROOT / "config.secret.json").read_text())

ref = re.match(r"https://([a-z0-9]+)\.supabase\.co", public["SUPABASE_URL"]).group(1)
sql = (ROOT / "supabase" / "schema.sql").read_text()

req = urllib.request.Request(
    f"https://api.supabase.com/v1/projects/{ref}/database/query",
    data=json.dumps({"query": sql}).encode(),
    headers={
        "Authorization": f"Bearer {secret['SUPABASE_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    print("Schema applied:", resp.status)
