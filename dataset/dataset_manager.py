import os
import yaml
from pathlib import Path
from roboflow import Roboflow

class DatasetManager:
    """
    Manages the lifecycle of the AI datasets, including downloading from Roboflow,
    validating structure, and ensuring compatibility with the training pipeline.
    """

    def __init__(self, api_key: str, workspace: str, project_name: str, version: int):
        self.rf = Roboflow(api_key=api_key)
        self.workspace_name = workspace
        self.project_name = project_name
        self.version_num = version
        self.dataset_dir = None

    def download_dataset(self, model_type="yolov8", target_dir="weapon-detection-1"):
        """Downloads the dataset from Roboflow."""
        print(f"Connecting to Roboflow workspace: {self.workspace_name}...")
        project = self.rf.workspace(self.workspace_name).project(self.project_name)
        version = project.version(self.version_num)
        
        print(f"Downloading version {self.version_num} for {model_type}...")
        self.dataset = version.download(model_type, location=target_dir)
        self.dataset_dir = Path(self.dataset.location)
        print(f"Dataset downloaded to: {self.dataset_dir}")
        return self.dataset_dir

    def validate_dataset(self, data_yaml_path="weapon-detection-1/data.yaml"):
        """Validates the structure of the dataset and the data.yaml file."""
        yaml_path = Path(data_yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"data.yaml not found at {yaml_path}")

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        print("--- Dataset Configuration ---")
        print(f"Classes: {data.get('names', [])}")
        print(f"Number of classes (nc): {data.get('nc')}")
        
        # Check paths
        splits = ['train', 'val', 'test']
        for split in splits:
            if split in data:
                # Roboflow sometimes uses relative paths like ../train/images
                # We want to ensure they resolve correctly relative to the project root
                # if we are running the script from root.
                print(f"Check path for {split}: {data[split]}")
        
        return data

    def fix_yaml_paths(self, data_yaml_path="weapon-detection-1/data.yaml"):
        """Ensures paths in data.yaml are absolute or correctly relative to project root."""
        yaml_path = Path(data_yaml_path).resolve()
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        root = yaml_path.parent
        data['path'] = str(root) # Set base path for YOLOv8
        
        # Normalize internal paths
        if 'train' in data and not data['train'].startswith(str(root)):
             data['train'] = "train/images"
        if 'val' in data and not data['val'].startswith(str(root)):
             data['val'] = "valid/images"
        if 'test' in data and not data['test'].startswith(str(root)):
             data['test'] = "test/images"

        with open(yaml_path, 'w') as f:
            yaml.dump(data, f)
        
        print(f"Updated paths in {yaml_path}")

if __name__ == "__main__":
    # Example usage for graduation project
    # SECURITY: Never hardcode API keys in production or version control.
    API_KEY = os.getenv("ROBOFLOW_API_KEY")
    if not API_KEY:
        print("Error: ROBOFLOW_API_KEY environment variable is missing.")
        print("Please set it before running this script.")
        exit(1)

    manager = DatasetManager(
        api_key=API_KEY,
        workspace="ir-uz1qh",
        project_name="weapon-detection-jqd3x",
        version=1
    )
    
    # In a real workflow, we might skip download if it exists
    if not Path("weapon-detection-1").exists():
        manager.download_dataset()
    
    manager.validate_dataset()
    manager.fix_yaml_paths()
