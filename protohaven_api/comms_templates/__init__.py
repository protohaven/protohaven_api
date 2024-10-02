"""Message template functions for CLI commands"""
from functools import lru_cache
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from protohaven_api.config import tznow  # pylint: disable=import-error


@lru_cache(maxsize=1)
def _env():
    return Environment(
        loader=PackageLoader("protohaven_api.comms_templates"),
        autoescape=select_autoescape(),
    )


def get_all_templates():
    """Returns a list of all templates callable by `render()`"""
    return [e.replace(".jinja2", "") for e in _env().list_templates()]


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
