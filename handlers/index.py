from flask import session, render_template, Blueprint
from rbac import require_login
from handlers.auth import user_fullname, user_email
import json

page = Blueprint('index', __name__, template_folder='templates')

@page.route("/")
@require_login
def index():
    neon_account = session.get('neon_account')
    clearances = []
    roles = []
    neon_account['custom_fields'] = {'Clearances': {'optionValues': []}}
    neon_json = json.dumps(neon_account, indent=2)
    for cf in neon_account['individualAccount']['accountCustomFields']:
        if cf['name'] == 'Clearances':
            clearances = [v['name'] for v in cf['optionValues']]
        if cf['name'] == 'API server role':
            roles = [v['name'] for v in cf['optionValues']]
        neon_account['custom_fields'][cf['name']] = cf

    return render_template("dashboard.html", 
            fullname=user_fullname(), 
            email=user_email(), 
            neon_id=session.get('neon_id'), 
            neon_account=neon_account, 
            neon_json=neon_json, 
            clearances=clearances, 
            roles=roles)

