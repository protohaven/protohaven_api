from flask import Blueprint, request, render_template
from integrations import discord_bot
from rbac import require_login_role, Role

page = Blueprint('onboarding', __name__, template_folder='templates')

@page.route("/onboarding")
@require_login_role(Role.ONBOARDING)
def onboarding():
    return render_template("onboarding_wizard.html")

@page.route("/onboarding/check_membership")
@require_login_role(Role.ONBOARDING)
def onboarding_check_membership():
    email = request.args.get('email')
    m = neon.search_member(email.strip())
    print(m)
    return dict(
            neon_id=m['Account ID'],
            first=m['First Name'], 
            last=m['Last Name'], 
            status=m['Account Current Membership Status'], 
            level=m['Membership Level'],
            discord_user=m['Discord User'])

@page.route("/onboarding/coupon")
@require_login_role(Role.ONBOARDING)
def onboarding_create_coupon():
    email = request.args.get('email')
    m = neon.search_member(email.strip())
    code = f"NM-{m['Last Name'].upper()[:3]}{int(time.time())%1000}"
    print("Creating coupon code", code)
    return neon.create_coupon_code(code, 45)

@page.route("/onboarding/discord_member_add")
@require_login_role(Role.ONBOARDING)
def discord_member_add():
    name = request.args.get('name', '')
    neon_id = request.args.get('neon_id', '')
    nick = request.args.get('nick', '')
    if name == "" or neon_id == "" or nick == "":
        return "Require params: name, neon_id, nick"
    

    print(neon.set_discord_user(neon_id, name))

    client = discord_bot.get_client()
    result = asyncio.run_coroutine_threadsafe(
            client.grant_role(name, 'Members'),
            client.loop).result()
    if result == False:
        return "Failed to grant Members role: member not found"

    result = asyncio.run_coroutine_threadsafe(
            client.set_nickname(name, nick),
            client.loop).result()
    if result == False:
        return "Failed to set nickname: member not found"
    elif result == True:
        return "Setup complete"
    else:
        return result

@page.route("/discord")
def discord_redirect():
    return redirect("https://discord.gg/twmKh749aH")
