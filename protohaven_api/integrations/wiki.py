"""Functions for interfacing with the DokuWiki, hosted at https://protohaven.org/wiki"""
import time
from functools import lru_cache

import requests
from bs4 import BeautifulSoup


@lru_cache()
def fetch_shift_tasks_internal(ttl_hash=None):  # pylint: disable=unused-argument
    """Gets all content on the Shop Tech Central page related to on-duty tasks for techs"""
    rep = requests.get("https://protohaven.org/wiki/shoptechs/start", timeout=5.0)
    if rep.status_code != 200:
        raise RuntimeError("Couldn't read shop tech wiki")
    soup = BeautifulSoup(rep.content.decode("utf8"), features="html.parser")
    return soup


def get_wiki_section(soup, header_id):
    """Gets a particular section of a wiki page by its header"""
    return [
        elem.text.strip()
        for elem in soup.find(id=header_id)
        .findNext("div")
        .find_all("div", {"class": "li"})
    ]


def get_shop_tech_shift_tasks():
    """Gets the opening, on-shift, and closing tasks for techs.
    Uses ttl_hash to cache the result every hour.
    """
    soup = fetch_shift_tasks_internal(ttl_hash=round(time.time() / 3600))
    return {
        "opening": get_wiki_section(soup, "🌅_opening_shift_tasks_🌅"),
        "during": get_wiki_section(soup, "☀️_all_shift_tasks_☀️"),
        "closing": get_wiki_section(soup, "🌃_closing_shift_tasks_🌃"),
    }
