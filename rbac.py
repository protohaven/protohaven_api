from flask import session, redirect, url_for, request

class Role:
    INSTRUCTOR = dict(name="Instructor", id="75")
    SHOP_TECH = dict(name="Shop Tech", id="238")
    SHOP_TECH_LEAD = dict(name="Shop Tech Lead", id="241")
    ONBOARDING = dict(name="Onboarding", id="240")
    ADMIN = dict(name="Admin", id="239")

def require_login(fn):
    def do_login_check(*args, **kwargs):
        if session.get('neon_id') is None:
            session['redirect_to_login_url'] = request.url
            return redirect(url_for(login_user_neon_oauth.__name__))
        return fn(*args, **kwargs)
    do_login_check.__name__ = fn.__name__
    return do_login_check 

def get_roles():
    if "api_key" in request.values:
        roles = cfg.get('external_access_codes').get(request.values.get('api_key'))
        print("Request with API key - roles", roles)
        return roles

    neon_acct = session.get('neon_account')
    if neon_acct is None:
        return None
    acct = neon_acct.get('individualAccount') or neon_acct.get('companyAccount')
    if acct is None:
        return None

    result = []
    for cf in acct.get('accountCustomFields', []):
        if cf['name'] == 'API server role':
            for ov in cf['optionValues']:
                result.append(ov.get('name'))
            break
    return result

def require_login_role(role):
    def fn_setup(fn):
        def do_role_check(*args, **kwargs):
            roles = get_roles()
            if roles is None:
                session['redirect_to_login_url'] = request.url
                return redirect(url_for(login_user_neon_oauth.__name__))
            elif role['name'] in roles:
                return fn(*args, **kwargs)
            return "Access Denied"
        do_role_check.__name__ = fn.__name__
        return do_role_check
    return fn_setup

