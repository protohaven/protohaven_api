from protohaven_api.commands.finances import Commands as C
from protohaven_api.integrations import neon, airtable

def test_validate_memberships_empty(mocker):
    mocker.patch.object(neon, "search_member", return_value=[])
    got = C().validate_memberships_internal([])
    assert not got

def test_validate_membership_amp_ok():
    got = C().validate_membership_singleton("1234", {
        'level': 'AMP',
        'term': 'Extremely Low Income',
        'amp': {'optionValues': ['ELI']},
        'active_memberships': [{'fee': 1}],
        })
    assert not got


def test_validate_membership_zero_cost_roles_ok():
    for l in ['Shop Tech', 'Board Member', 'Staff']:
        got = C().validate_membership_singleton("1234", {
            'level': l,
            'roles': [l],
            'active_memberships': [{'fee': 0, 'level': l}],
            })
    assert not got


def test_validate_membership_general_zero_cost_bad():
    got = C().validate_membership_singleton("1234", {
        'level': 'General Membership',
        'active_memberships': [{'fee': 0, 'level': 'General Membership'}],
        })
    assert got == ['Abnormal zero-cost membership General Membership']


def test_validate_membership_instructor_ok():
    got = C().validate_membership_singleton("1234", {
        'level': 'Instructor',
        'roles': ['Instructor'],
        'active_memberships': [{'fee': 1}],
        })
    assert not got


def test_validate_membership_instructor_no_role():
    got = C().validate_membership_singleton("1234", {
        'level': 'Instructor',
        'roles': [],
        'active_memberships': [{'fee': 1}],
        })
    assert got == ['Needs role Instructor, has []']

def test_validate_membership_addl_family_ok():
    got = C().validate_membership_singleton("1234", {
        'hid': "123",
        'household_member_count': 2,
        'household_num_addl_members': 1,
        'level': 'Additional Family Membership',
        'active_memberships': [{'fee': 1}],
        })
    assert not got

def test_validate_membership_addl_family_too_few_bad():
    got = C().validate_membership_singleton("1234", {
        'hid': "123",
        'household_member_count': 1,
        'household_num_addl_members': 0,
        'level': 'Additional Family Membership',
        'active_memberships': [{'fee': 1}],
        })
    assert got == ['Missing required 2+ members in household #123']

def test_validate_membership_addl_family_no_fullprice_bad():
    got = C().validate_membership_singleton("1234", {
        'hid': "123",
        'household_member_count': 2,
        'household_num_addl_members': 2,
        'level': 'Additional Family Membership',
        'active_memberships': [{'fee': 1}],
        })
    assert got == ['Missing full-price member in household #123']

def test_validate_membership_employer_ok():
    got = C().validate_membership_singleton("1234", {
        'company_member_count': 2,
        'level': 'Corporate Membership',
        'active_memberships': [{'fee': 1}],
        })
    assert not got


def test_validate_membership_employer_too_few_bad():
    got = C().validate_membership_singleton("1234", {
        'cid': "123",
        'company_member_count': 1,
        'level': 'Corporate Membership',
        'active_memberships': [{'fee': 1}],
        })
    assert got == ['Missing required 2+ members in company #123']
