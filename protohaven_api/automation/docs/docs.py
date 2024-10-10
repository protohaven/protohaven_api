"""Validate tool documentation to ensure we have what we need for
every tool we offer."""
import logging

import requests

from protohaven_api.integrations import airtable
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("validation.docs")


def probe(url, name, stats):
    """Send out a URL request for a tool to confirm it resolves"""
    url = url.strip()
    if url not in ("", "https://protohaven.org/wiki/tools//"):
        rep = requests.get(url, timeout=5.0)
        if (
            rep.status_code == 200
            and "This topic does not exist yet".encode("utf8") not in rep.content
        ):
            stats["ok"] += 1
        else:
            stats["error"].append(f"{name} ({url})")
    else:
        stats["missing"].append(f"{name} ({url})")


def write_stats(stats, title, max_per_segment=10):
    """Write a summary of missing or errored pages"""
    b = f"=== {title} ==="
    b += f"\n{stats['ok']} links resolved OK"
    b += f"\nMissing links for {len(stats['missing'])} tools; first {max_per_segment}:"
    for m in stats["missing"][:max_per_segment]:
        b += f"- {m}\n"
    b += f"\nFailed to resolve {len(stats['error'])} links for tools; first {max_per_segment}:"
    for m in stats["error"][:max_per_segment]:
        b += f"- {m}\n"
    return b


NONE_CLEARANCE_RECORD = "recZz04FDZ9zr1PVh"


def validate():
    """Validate all tool docs and clearance docs"""
    stats = {
        "tooldoc": {"missing": [], "error": [], "ok": 0},
        "clearance": {"missing": [], "error": [], "ok": 0},
    }
    tools = airtable.get_tools()
    log.info(  # pylint: disable=logging-not-lazy
        f"Checking links for {len(tools)} tools\n"
        + "Tools that do not require a clearance will be skipped.\n"
    )
    for i, tool in enumerate(tools):
        if i != 0 and i % 5 == 0:
            log.info(f"{i}/{len(tools)}")

        if (
            tool["fields"]["Clearance Required"] is None
            or NONE_CLEARANCE_RECORD in tool["fields"]["Clearance Required"]
        ):
            log.debug(f"SKIP {tool['fields']['Tool Name']} (no clearance needed)")
            continue
        name = tool["fields"]["Tool Name"]

        clearance_url = tool["fields"]["Clearance"]["url"]
        probe(clearance_url, name, stats["clearance"])

        tutorial_url = tool["fields"]["Docs"]["url"]
        probe(tutorial_url, name, stats["tooldoc"])

        # rep = requests.head(tutorial_url, timeout=5.0)
        # tutorial_exists = rep.status_code == 200

    return Msg.tmpl(
        "tool_documentation",
        target="#docs-automation",
        n=len(tools),
        tool_tutorials=write_stats(stats["tooldoc"], "Tool Tutorials"),
        clearance_docs=write_stats(stats["clearance"], "Clearance Docs"),
    )
