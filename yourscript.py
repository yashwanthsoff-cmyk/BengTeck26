# yourscript.py — Checkpoint-Native DX Entry Point Alias
# Allows running the application via both streamlit run yourscript.py and streamlit run app.py
import runpy
import sys
import os

# Invalidate cached modules under lib to ensure live code changes reload immediately
for mod in list(sys.modules.keys()):
    if mod.startswith("lib.") or mod == "lib":
        del sys.modules[mod]

app_path = os.path.join(os.path.dirname(__file__), "app.py")
runpy.run_path(app_path, run_name="__main__")
