"""Message templates for CLI commands that generate notifications"""
from jinja2 import Environment, PackageLoader, select_autoescape

from protohaven_api.config import exec_details_footer

env = Environment(
    loader=PackageLoader("protohaven_api.role_automation"),
    autoescape=select_autoescape(),
)


def discord_role_change_dm(logs, discord_id):
    """Generate message for techs about classes with open seats"""
    subject = "**Your Discord Roles Are Changing:**"
    not_associated = True in ["not associated with a Neon account" in l for l in logs]
    return subject, env.get_template("discord_role_change_dm.jinja2").render(
        logs=logs,
        n=len(logs),
        discord_id=discord_id,
        not_associated=not_associated,
    )


def discord_role_change_summary(user_log, roles_assigned, roles_revoked):
    """Generate summary of Discord actions taken"""
    subject = "**Discord Role Automation Summary:**"
    return (
        subject,
        env.get_template("discord_role_change_summary.jinja2").render(
            users=list(user_log.keys()),
            n=len(user_log),
            roles_assigned=roles_assigned,
            roles_revoked=roles_revoked,
        )
        + exec_details_footer(),
    )
