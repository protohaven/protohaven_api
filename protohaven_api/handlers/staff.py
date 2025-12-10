"""Pages for staff"""

import json
import logging
from dataclasses import asdict, dataclass

import markdown
from flask import Blueprint, current_app
from flask_sock import Sock

from protohaven_api.config import safe_parse_datetime
from protohaven_api.integrations import comms, gpt
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import require_login_role

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


@dataclass
class OpsItem:
    timescale: str
    category: str
    label: str
    details: str
    source: str
    url: str

@page.route("/staff/ops_summary")
@require_login_role(Role.STAFF, Role.BOARD_MEMBER)
def ops_summary():
    """Fetch data from many places and provide a summary of operational state"""
    items = [
          OpsItem(
              category="Financial",
              timescale="last 12 months",
              label="Asset sale",
              details="X assets not yet listed, Y listed but not sold, Z sold",
              source="Asana",
              url="TODO",
          ),
          OpsItem(
              category="Financial",
              timescale="YYYY",
              label="Budget",
              details="$X of $Y (NN%) of operational budget spent for YYYY. $Z in expenses remains unitemized",
              source="Divvy",
              url="TODO",
          ),
          OpsItem(
              category="Equipment",
              timescale="ongoing",
              label="Downtime",
              details="X red tagged more than 7 days, Y yellow-tagged more than 14 days, Z in blue (setup) state",
              source="Airtable",
              url="https://airtable.com/appbIlORlmbIxNU1L/tblalZYdLVoTICzE6/",
          ),
          OpsItem(
              category="Equipment",
              timescale="ongoing",
              label="Reporting",
              details="N/R tool state tag discrepancies corrected (digital vs physical)",
              source="Airtable",
              url="https://airtable.com/appbIlORlmbIxNU1L/tblalZYdLVoTICzE6/",
          ),
          OpsItem(
              category="Safety",
              timescale="ongoing",
              label="Safety training",
              details="X days since last volunteer safety training",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Safety",
              timescale="ongoing",
              label="Staff safety",
              details="X days since last HazCom / QFT",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Safety",
              timescale="ongoing",
              label="Substances",
              details="X days since Last SDS review",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Techs and Instructors",
              timescale="ongoing",
              label="Tech applications and onboarding",
              details="Tech applications and onboarding",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Techs and Instructors",
              timescale="ongoing",
              label="Tech shifts at risk",
              details="Tech shifts at risk of no availability",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Techs and Instructors",
              timescale="ongoing",
              label="Stuck volunteer projects",
              details="Stuck volunteer projects",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Techs and Instructors",
              timescale="ongoing",
              label="Techs due for review",
              details="Techs due for review",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Instructors",
              timescale="ongoing",
              label="Stuck instructor applications",
              details="Stuck instructor applications",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Instructors",
              timescale="ongoing",
              label="Clearance coverage",
              details="Clearance coverage",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Instructors",
              timescale="ongoing",
              label="Stuck class proposals",
              details="Stuck class proposals",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Inventory",
              timescale="ongoing",
              label="Stuck purchase requests",
              details="Stuck purchase requests",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Inventory",
              timescale="ongoing",
              label="Low inventory",
              details="Low inventory",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Inventory",
              timescale="ongoing",
              label="Absent inventory",
              details="Absent inventory",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Inventory",
              timescale="ongoing",
              label="Last inventory review",
              details="Last inventory review",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Inventory",
              timescale="ongoing",
              label="Stuck storage violations",
              details="Stuck storage violations",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Documentation",
              timescale="ongoing",
              label="Tool docs requiring approval",
              details="Tool docs requiring approval, but stuck in review",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Documentation",
              timescale="ongoing",
              label="Missing clearance docs",
              details="Missing clearance docs",
              source="internal",
              url="TODO",
          ),
          OpsItem(
              category="Documentation",
              timescale="ongoing",
              label="Missing tool tutorials",
              details="Missing tool tutorials",
              source="internal",
              url="TODO",
          ),
      ]
    return [asdict(i) for i in items]



def summarizer_ws(ws):
    """Fetch discord messages in a given interval of time and summarize them"""
    data = json.loads(ws.receive())
    start_date = safe_parse_datetime(data["start_date"])
    end_date = safe_parse_datetime(data["end_date"])
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
