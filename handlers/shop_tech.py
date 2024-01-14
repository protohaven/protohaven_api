from flask import Blueprint, request, render_template, session
from rbac import require_login_role, Role
from integrations import wiki, neon

page = Blueprint('shop_tech', __name__, template_folder='templates')

@page.route("/shop_tech/handoff")
@require_login_role(Role.SHOP_TECH)
def shop_tech_handoff():
    shift_tasks = wiki.get_shop_tech_shift_tasks()
    return render_template("shop_tech_handoff.html", shift_tasks=shift_tasks)

@page.route("/shop_tech/profile", methods=["GET", "POST"])
@require_login_role(Role.SHOP_TECH)
def shop_tech_profile():
    user = session['neon_id']
    if request.method == "POST":
        interest = request.form['interest']
        neon.set_interest(user, interest)
        session['neon_account'] = neon.fetch_account(session['neon_id'])

    interest = ""
    for cf in session['neon_account']['individualAccount']['accountCustomFields']:
        if cf['name'] == 'Interest':
            interest = cf['value']
            break
    return render_template("shop_tech_profile.html", interest=interest)
