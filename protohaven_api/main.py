"""Collect various blueprints and start the flask server - also the discord bot"""
from flask import Flask  # pylint: disable=import-error

from protohaven_api.config import get_config
from protohaven_api.handlers.admin import page as admin_pages
from protohaven_api.handlers.auth import page as auth_pages
from protohaven_api.handlers.index import page as index_pages
from protohaven_api.handlers.instructor import page as instructor_pages
from protohaven_api.handlers.onboarding import page as onboarding_pages
from protohaven_api.handlers.shop_tech import page as shop_tech_pages
from protohaven_api.handlers.tech_lead import page as tech_lead_pages
from protohaven_api.integrations import discord_bot

app = Flask(__name__)
application = app  # our hosting requires application in passenger_wsgi
cfg = get_config()["general"]
app.secret_key = cfg["session_secret"]
app.config["TEMPLATES_AUTO_RELOAD"] = True  # Reload template if signature differs
for p in (
    auth_pages,
    index_pages,
    admin_pages,
    instructor_pages,
    onboarding_pages,
    shop_tech_pages,
    tech_lead_pages,
):
    app.register_blueprint(p)

if __name__ == "__main__":
    import threading

    t = threading.Thread(target=discord_bot.run, daemon=True)
    t.start()
    app.run()
