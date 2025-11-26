import yaml

def read_yaml(file_path: str, dict:str) -> dict:
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return data[str]