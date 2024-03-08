"""Message template functions for communicating maintenance details"""

import random

from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("protohaven_api.maintenance"),
    autoescape=select_autoescape(),
)

SALUTATIONS = [
    "Greetings techs!",
    "Hey there, techs!",
    "Salutations, techs!",
    "Hello techs!",
    "Howdy techs!",
    "Yo techs!",
    "Good day, techs!",
    "Hiya techs!",
    "Ahoy techs!",
    "Hey ho, techs!",
    "Beep boop, hello fellow techs!",
]

CLOSINGS = [
    "Keep sparking those creative circuits!",
    "For adventure and maker glory!",
    "Stay wired!",
    "Onwards to innovation!",
    "May your creativity be boundless!",
    "Stay charged and keep on making!",
    "Let's make some sparks!",
    "May your projects shine brighter than LEDs!",
    "Let's keep the gears turning and the ideas flowing!",
    "Until our next digital rendezvous, stay charged up!",
    "Dream it, plan it, do it!",
    "Innovation knows no boundaries - keep pushing forward!",
    "Every project is a step closer to greatness - keep going!",
    "Always be innovating!",
    "Stay curious, stay inspired, and keep making a difference!",
    "Remember - every circuit starts with a single connection. Keep connecting!",
    "Your passion fuels progress — keep the fire burning!",
    "You're not just making things, you're making history — keep on crafting!",
]

MAX_NEW_TASKS = 3
MAX_STALE_TASKS = 3


def daily_tasks_summary(new_tasks, stale_tasks, stale_thresh):
    """Generate a summary of violation and suspension state, if there is any"""
    subject = random.choice(SALUTATIONS)
    stale_tasks.sort(key=lambda k: k["days_ago"], reverse=True)
    return subject, env.get_template("tech_daily_tasks.jinja2").render(
        closing=random.choice(CLOSINGS),
        new_count=len(new_tasks),
        stale_count=len(stale_tasks),
        new_tasks=new_tasks[:MAX_NEW_TASKS],
        stale_thresh=stale_thresh,
        stale_tasks=stale_tasks[:MAX_STALE_TASKS],
    )
