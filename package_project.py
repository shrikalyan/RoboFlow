"""
Package RoboFlow Project into RoboFlow_Stochastic_Warehouse_Optimizer.zip
"""
import zipfile
import os

project_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_dir)

files_to_zip = [
    "app.py",
    "requirements.txt",
    "README.md",
    "test_roboflow.py",
    os.path.join("templates", "index.html"),
    os.path.join("static", "style.css"),
    os.path.join("static", "script.js")
]

zip_paths = [
    os.path.join(project_dir, "RoboFlow_Stochastic_Warehouse_Optimizer.zip"),
    os.path.join(parent_dir, "RoboFlow_Stochastic_Warehouse_Optimizer.zip")
]

for zp in zip_paths:
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in files_to_zip:
            full_path = os.path.join(project_dir, rel_path)
            if os.path.exists(full_path):
                # Archive name inside zip
                arcname = os.path.join("RoboFlow", rel_path)
                zf.write(full_path, arcname)
                print(f"Added {rel_path} -> {arcname}")
            else:
                print(f"WARNING: {full_path} not found!")
    print(f"[OK] Created ZIP archive: {zp} ({os.path.getsize(zp)} bytes)")

if __name__ == "__main__":
    pass
