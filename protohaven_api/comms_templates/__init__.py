"""Message template functions for CLI commands"""
from functools import lru_cache
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from protohaven_api.config import tznow  # pylint: disable=import-error


@lru_cache(maxsize=1)
def _env():
    loader = PackageLoader("protohaven_api.comms_templates")
    return (
        Environment(
            loader=loader,
            autoescape=select_autoescape(),
        ),
        loader,
    )


def get_all_templates():
    """Returns a list of all templates callable by `render()`"""
    return [e.replace(".jinja2", "") for e in _env()[0].list_templates()]


def render(template_name, **kwargs):
    """Returns a rendered template in two parts - subject and body.
    Template must be of the form:

    {% if subject %}Subject goes here!{% else %}Body begins{% endif %}

    HTML template is optionally indicated with {# html #} at the
    very start of the template.
    """
    fname = f"{template_name}.jinja2"
    e, l = _env()
    src, _, _ = l.get_source(e, fname)
    is_html = src.strip().startswith("{# html #}")
    tmpl = e.get_template(fname)
    return (
        tmpl.render(**kwargs, subject=True),
        tmpl.render(**kwargs, subject=False),
        is_html,
    )
