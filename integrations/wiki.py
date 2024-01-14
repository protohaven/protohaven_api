import requests
import time
from bs4 import BeautifulSoup
from functools import lru_cache

@lru_cache()
def fetch_shift_tasks_internal(ttl_hash=None): 
    rep = requests.get("https://protohaven.org/wiki/shoptechs/start")
    if rep.status_code != 200:
        raise Exception("Couldn't read shop tech wiki")
    soup = BeautifulSoup(rep.content.decode("utf8"), features="html.parser")
    return soup

def get_wiki_section(soup, header_id):
    return [elem.text.strip()
            for elem in
            soup.find(id=header_id)
            .findNext("div")
            .find_all("div", {"class": "li"})]

def get_shop_tech_shift_tasks():
    soup = fetch_shift_tasks_internal(ttl_hash=round(time.time()/3600))
    # TODO handle internal text
    return dict(
        opening = get_wiki_section(soup, "🌅_opening_shift_tasks_🌅"),
        during = get_wiki_section(soup, "☀️_all_shift_tasks_☀️"),
        closing = get_wiki_section(soup, "🌃_closing_shift_tasks_🌃"),
        )

