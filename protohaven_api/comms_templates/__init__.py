"""Message template functions for CLI commands"""
from urllib.parse import quote
from functools import lru_cache

from jinja2 import Environment, PackageLoader, select_autoescape

from protohaven_api.config import tznow  # pylint: disable=import-error

@lru_cache(maxsize=1)
def _env():
    return Environment(
        loader=PackageLoader("protohaven_api.comms_templates"),
        autoescape=select_autoescape(),
    )

def render(template_name, **kwargs):
    """Returns a rendered template in two parts - subject and body.
    Template must be of the form:

    {% if subject %}Subject goes here!{% else %}Body begins{% endif %}
    """
    tmpl = _env().get_template(f"{template_name}.jinja2")
    return (
        tmpl.render(**kwargs, subject=True),
        tmpl.render(**kwargs, subject=False),
    )
