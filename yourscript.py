# yourscript.py — Checkpoint-Native DX Entry Point Alias
# Allows running the application via both streamlit run yourscript.py and streamlit run app.py
import runpy
import sys
import os

app_path = os.path.join(os.path.dirname(__file__), "app.py")
runpy.run_path(app_path, run_name="__main__")
