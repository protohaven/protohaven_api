"""Form submission methods"""
from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

config = get_config()["forms"]


def submit_google_form(form_name, data):
    """Submit a google form; see config.yaml for form names"""
    params = {config[form_name]["keys"][k]: v for k, v in data.items()}
    # Included by default on all google forms
    params["submit"] = "Submit"
    params["usp"] = "pp_url"
    return get_connector().google_form_submit(
        config[form_name]["base_url"] + "formResponse", params=params
    )
