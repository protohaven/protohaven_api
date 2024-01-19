"""Collect various blueprints and start the flask server - also the discord bot"""
import os

from flask import Flask  # pylint: disable=import-error

from protohaven_api.config import get_config
from protohaven_api.discord_bot import run as run_bot
from protohaven_api.handlers.admin import page as admin_pages
from protohaven_api.handlers.auth import page as auth_pages
from protohaven_api.handlers.index import page as index_pages
from protohaven_api.handlers.instructor import page as instructor_pages
from protohaven_api.handlers.onboarding import page as onboarding_pages
from protohaven_api.handlers.shop_tech import page as shop_tech_pages
from protohaven_api.handlers.tech_lead import page as tech_lead_pages
from protohaven_api.integrations.data.connector import init as init_connector

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

server_mode = os.getenv("PH_SERVER_MODE", "dev").lower()
run_discord_bot = os.getenv("DISCORD_BOT", "false").lower() == "true"
init_connector(dev=server_mode != "prod")
if run_discord_bot:
    import threading

    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
else:
    print("Skipping startup of discord bot")

if __name__ == "__main__":
    app.run()
