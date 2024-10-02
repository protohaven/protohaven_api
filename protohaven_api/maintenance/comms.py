"""Message template functions for communicating maintenance details"""

import random

from protohaven_api.comms_templates import render

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
    "What's up, techs!",
    "Greetings and salutations, techs!",
    "Hi techs, ready to make something?",
    "Hey there, tech wizards!",
    "Top of the morning, techs!",
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
    "From concept to creation, keep the momentum!",
    "Invent, iterate, and inspire — the maker's trifecta!",
]

MAX_STALE_TASKS = 3


def daily_tasks_summary(new_tasks):
    """Generate a summary of violation and suspension state, if there is any"""
    return render(
        "tech_daily_tasks",
        salutation=random.choice(SALUTATIONS),
        closing=random.choice(CLOSINGS),
        new_count=len(new_tasks),
        new_tasks=new_tasks,
    )


def tech_leads_summary(stale_tasks, stale_thresh):
    """Generate a summary of tale tasks"""
    stale_tasks.sort(key=lambda k: k["days_ago"], reverse=True)
    return render(
        "tech_leads_maintenance_status",
        stale_count=len(stale_tasks),
        stale_thresh=stale_thresh,
        stale_tasks=stale_tasks[:MAX_STALE_TASKS],
    )
