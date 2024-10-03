"""Pages for staff"""

import json
import logging

import markdown
from dateutil import parser as dateparser
from flask import Blueprint, current_app
from flask_sock import Sock

from protohaven_api.integrations import comms, gpt
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("staff", __name__, template_folder="templates")

log = logging.getLogger("handlers.staff")


@page.route("/staff", methods=["GET"])
@require_login_role(Role.STAFF, Role.BOARD_MEMBER)
def staff_static():
    """Staff internal page"""
    return current_app.send_static_file("svelte/staff.html")


@page.route("/staff/_app/immutable/<typ>/<path>")
@require_login_role(Role.STAFF, Role.BOARD_MEMBER)
def staff_static_files(typ, path):
    """Return svelte compiled static pages for staff page"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/staff/discord_member_channels", methods=["GET"])
@require_login_role(Role.STAFF, Role.BOARD_MEMBER)
def discord_channels():
    """Returns all member channels by name"""
    return [c[1] for c in comms.get_member_channels()]


def summarizer_ws(ws):
    """Fetch discord messages in a given interval of time and summarize them"""
    data = json.loads(ws.receive())
    start_date = dateparser.parse(data["start_date"])
    end_date = dateparser.parse(data["end_date"])
    channels = set(data["channels"])
    channels = {c for c in comms.get_member_channels() if c[1] in channels}
    summaries = []
    for channel_id, channel_name in channels:
        msgs = []
        for msg in comms.get_channel_history(channel_id, start_date, end_date):
            msgs.append(msg)
            ws.send(
                json.dumps(
                    {
                        "type": "individual",
                        "ref": msg["ref"],
                        "channel": channel_name,
                        "created_at": msg["created_at"].isoformat(),
                        "images": msg["images"],
                        "videos": msg["videos"],
                        "content": msg["content"],
                        "author": msg["author"],
                    }
                )
            )
        summary = gpt.summarize_message_history(
            [f"{m['created_at']} {m['author']}: {m['content']}" for m in msgs]
        )
        ws.send(
            json.dumps(
                {"type": "channel_summary", "channel": channel_name, "content": summary}
            )
        )
        summaries.append((channel_name, summary))

    final_summary = gpt.summary_summarizer(
        [f"{name}:\n{summary}\n\n" for name, summary in summaries]
    )
    summary_html = markdown.markdown(final_summary)
    ws.send(json.dumps({"type": "final_summary", "content": summary_html}))
    log.info("Done")
    ws.close()


def setup_sock_routes(app):
    """Set up all websocket routes; called by main.py"""
    sock = Sock(app)
    sock.route("/staff/summarize_discord")(summarizer_ws)
