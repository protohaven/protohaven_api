# A set of command line tools, usually run by CRON

def send_hours_submission_reminders():
    raise Exception("TODO implement")

def send_storage_violation_reminders():
    # TODO For any violation tagged with a user, send an email
    # Send a summary of violations without users to a discord channel / email location
	pass

def validate_member_clearances():
	# TODO match clearances in spreadsheet with clearances in Neon.
	# Remove this when clearance information is primarily stored in Neon.

def validate_tool_documentation():
	# TODO go through list of tools in airtable, ensure all of them have
	# links to a tool guide and a clearance doc that resolve successfully
	pass
