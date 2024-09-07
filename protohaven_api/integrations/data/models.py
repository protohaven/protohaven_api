"""OOP-style representation of entities stored in Airtable and elsewhere"""
from dataclasses import dataclass


@dataclass
class SignInEvent:
    """Represents a sign-in event by a user at the /welcome form"""

    email: str
    dependent_info: str
    waiver_ack: bool
    referrer: str
    purpose: str
    am_member: bool

    def to_airtable(self):
        """Convert data to Airtable record format"""
        return {
            "Email": self.email,
            "Dependent Info": self.dependent_info,
            "Waiver Ack": self.waiver_ack,
            "Referrer": self.referrer,
            "Purpose": self.purpose,
            "Am Member": self.am_member,
        }

    def to_google_form(self):
        """Convert data to google form format"""
        return {
            "email": self.email,
            "dependent_info": self.dependent_info,
            "waiver_ack": (
                "I have read and understand this agreement and "
                "agree to be bound by its requirements.",  # Must be this, otherwise 400 error
            )
            if self.waiver_ack
            else "",
            "referrer": self.referrer,
            "purpose": "I'm a member, just signing in!",
            "am_member": "Yes" if self.am_member else "No",
        }
