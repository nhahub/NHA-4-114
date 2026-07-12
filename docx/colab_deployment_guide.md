# Google Colab High-Performance Training Guide
**Smart Vision System for Small Businesses**

## Overview
Due to the strict hardware constraints of the local deployment environment (2GB VRAM, 8GB RAM), the training phase of the custom Weapon Detection YOLOv8 model requires a cloud-based approach. Google Colab provides access to NVIDIA Tesla T4 GPUs (16GB VRAM), which are ideal for high-resolution (640px) batch processing without causing Out Of Memory (OOM) failures.

This document outlines the academic workflow for deploying the training data and running the custom training pipeline on Google Colab, ensuring the model's progress is safely persisted to Google Drive.

## Step 1: Prepare the Dataset
1. First, ensure you have the dataset compressed into a ZIP file. If you have downloaded it locally using the `dataset_manager.py`, run the following PowerShell command in your project root to compress it:
   ```powershell
   Compress-Archive -Path 'weapon-detection-1' -DestinationPath 'weapon_dataset.zip'
   ```
2. Upload `weapon_dataset.zip` to your Google Drive for faster extraction within Colab, or upload it directly to the Colab instance.

## Step 2: Colab Environment Setup
1. Create a new Google Colab Notebook.
2. Navigate to **Runtime > Change runtime type** and select **T4 GPU**.
3. Mount your Google Drive to ensure your training checkpoints are saved permanently:
   ```python
   from google.colab import drive
   drive.mount('/content/drive')
   ```

## Step 3: Run the Training Script
We have provided a fully modular script designed specifically for Colab persistence: `colab_training_resumable.py`.
1. Upload `docx/colab_training_resumable.py` to your Colab notebook environment, or copy its contents into a notebook cell.
2. The script will automatically:
   - Download the YOLOv8 dependencies.
   - Connect to Roboflow to grab the latest dataset (if you prefer that over the ZIP).
   - Check your Google Drive for an existing `last.pt` checkpoint to resume from (to protect against Colab disconnects).
   - Begin training at `imgsz=640` and `batch=32` utilizing the full 16GB VRAM of the T4 GPU.
3. Run the script and let the training complete. 

## Step 4: Exporting the Final Weights
Once the 50 epochs (or your specified amount) are complete, the optimized weights will automatically be saved to your Google Drive.
1. Navigate to your Google Drive: `MyDrive/SVS_Project/svs_weapon_detection/weights/`
2. Download `best.pt`.
3. Place the downloaded file into the local deployment directory at `models/weapon_final.pt`.

You are now ready to run real-time inference locally utilizing the optimized FP16 architecture provided by the `WeaponDetector` class.
