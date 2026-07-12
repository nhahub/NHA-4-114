# Smart Vision System - Colab Training Script
!pip install ultralytics

import zipfile
import os
import yaml
from ultralytics import YOLO

# 1. Extract
print("Extracting...")
with zipfile.ZipFile('weapon_dataset.zip', 'r') as zip_ref:
    zip_ref.extractall('.')

# 2. Fix data.yaml
with open('weapon-detection-1/data.yaml', 'r') as f:
    data = yaml.safe_load(f)

data['path'] = '/content/weapon-detection-1'
data['train'] = 'train/images'
data['val'] = 'valid/images'
data['test'] = 'test/images'

with open('weapon-detection-1/data.yaml', 'w') as f:
    yaml.dump(data, f)

# 3. Train
model = YOLO('yolov8n.pt')
model.train(
    data='weapon-detection-1/data.yaml',
    epochs=50,
    imgsz=640,
    batch=16,
    device=0,
    patience=15,
    close_mosaic=10,
    project='svs_weapon_detection'
)
