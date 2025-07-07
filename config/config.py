import yaml

def get_config(file_path: str):
    file_yaml = open(file_path, "r", encoding="utf-8")
    config = yaml.load(file_yaml, Loader=yaml.FullLoader)
    return config

