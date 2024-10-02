"""Message templates for CLI commands that generate notifications"""
from protohaven_api.comms_templates import render
from protohaven_api.config import exec_details_footer


def discord_role_change_dm(logs, discord_id):
    """Generate message for techs about classes with open seats"""
    not_associated = True in ["not associated with a Neon account" in l for l in logs]
    return render(
        "discord_role_change_dm",
        logs=logs,
        n=len(logs),
        discord_id=discord_id,
        not_associated=not_associated,
    )


def not_associated_warning(discord_id):
    """Generate message about user not being associated with Neon"""
    return render("not_associated", discord_id=discord_id)


def nick_change_summary(changes, notified):
    """Generate summary of Discord actions taken"""
    m = len(notified)
    notified = list(notified)
    if m > 30:
        notified = notified[:30] + ["..."]
    return render(
        "discord_nick_change_summary",
        changes=list(changes),
        n=len(changes),
        notified=notified,
        m=m,
        footer=exec_details_footer(),
    )


def discord_role_change_summary(user_log, roles_assigned, roles_revoked):
    """Generate summary of Discord actions taken"""
    return render(
        "discord_role_change_summary",
        users=list(user_log.keys()),
        n=len(user_log),
        roles_assigned=roles_assigned,
        roles_revoked=roles_revoked,
        footer=exec_details_footer(),
    )
