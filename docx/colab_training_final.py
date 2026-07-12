# Smart Vision System - Final Robust Colab Training Script
# This script is designed for Google Colab with a T4 GPU.

# 1. Install necessary libraries
!pip install ultralytics roboflow

import os
import yaml
import shutil
from roboflow import Roboflow
from ultralytics import YOLO

# 2. CLEAN UP: Delete old folders to prevent corruption
if os.path.exists("weapon-detection-1"):
    print("Cleaning up old dataset folder...")
    shutil.rmtree("weapon-detection-1")

# 3. Download dataset directly from Roboflow
rf = Roboflow(api_key="5jgnPDhEpqYl0Q2t58h2")
project = rf.workspace("ir-uz1qh").project("weapon-detection-jqd3x")
version = project.version(1)
dataset = version.download("yolov8")

# 4. ROBUST EXTRACTION: Use system unzip if Roboflow didn't extract correctly
dataset_path = dataset.location
zip_path = os.path.join(dataset_path, "roboflow.zip")

if os.path.exists(zip_path):
    print("Manually extracting using system unzip...")
    # Using shell command unzip which is more reliable for large datasets
    !unzip -q -o {zip_path} -d {dataset_path}
    os.remove(zip_path) # Clean up the zip after extraction
    print("Extraction successful.")

# 5. Find and fix the data.yaml paths for the cloud environment
yaml_file = os.path.join(dataset_path, "data.yaml")

if os.path.exists(yaml_file):
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)

    # Professional Path Reset for Google Colab
    data['path'] = dataset_path
    data['train'] = 'train/images'
    data['val'] = 'valid/images'
    data['test'] = 'test/images'

    with open(yaml_file, 'w') as f:
        yaml.dump(data, f)
    print(f"Successfully updated configuration at {yaml_file}")

# 6. Start High-Performance Training
# Optimized for T4 GPU: imgsz=640 (High Res) and batch=32 (Fast)
model = YOLO('yolov8n.pt')

model.train(
    data=yaml_file,
    epochs=50,
    imgsz=640,         # Full resolution
    batch=32,          # Maximize T4 GPU usage
    device=0,          # Force execution on GPU
    patience=15,       # Anti-overfitting
    close_mosaic=10,   # Final sharpening
    project='svs_weapon_detection',
    name='colab_run_final'
)

# 7. How to retrieve results:
# Your best weights will be at:
# /content/svs_weapon_detection/colab_run_final/weights/best.pt
