"""Message template functions for CLI commands"""
from dataclasses import dataclass, field
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


@dataclass
class Msg:
    """Msg handles rendering messaging information to a yaml file, for later
    processing with `protohaven_api.cli.send_comms`"""

    target: str
    subject: str
    body: str
    id: str = ""
    side_effect: dict = field(default_factory=dict)
    html: bool = False

    # These field saren't necessary for template rendering, but will be
    # assigned
    EXTRA_FIELDS = ("target", "id", "side_effect")

    @classmethod
    def tmpl(cls, tmpl, **kwargs):
        """Construct a `Msg` object via a template."""
        subject, body, is_html = render(tmpl, **kwargs)
        self_args = {k: v for k, v in kwargs.items() if k in cls.EXTRA_FIELDS}
        return cls(**self_args, subject=subject, body=body, html=is_html)

    def __iter__(self):
        """Calls of dict(msg) use this function"""
        return iter(
            [
                (k, v)
                for k, v in {
                    "target": self.target,
                    "subject": self.subject,
                    "body": self.body,
                    "id": self.id,
                    "side_effect": self.side_effect,
                    "html": self.html,
                }.items()
                if v
            ]
        )
