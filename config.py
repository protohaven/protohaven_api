import yaml

with open("config.yaml", "r") as f:
    cfg = yaml.safe_load(f)

def get_config():
    return cfg
