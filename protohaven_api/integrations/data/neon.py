"""Constants and other datatypes for Neon integration"""

from dataclasses import dataclass


class CustomFieldNotFoundError(RuntimeError):
    """Raised when the custom field is not found by an ID"""


@dataclass
class CustomField:
    """Account Custom Fields from Neon"""

    API_SERVER_ROLE = 85
    CLEARANCES = 75
    INTEREST = 148
    EXPERTISE = 155
    DISCORD_USER = 150
    WAIVER_ACCEPTED = 151
    SHOP_TECH_SHIFT = 152
    SHOP_TECH_LAST_DAY = 158
    SHOP_TECH_FIRST_DAY = 160
    AREA_LEAD = 153
    ANNOUNCEMENTS_ACKNOWLEDGED = 154
    ZERO_COST_OK_UNTIL = 159
    PRONOUNS = 161
    NOTIFY_BOARD_AND_STAFF = 162
    ACCOUNT_AUTOMATION_RAN = 163
    BOOKED_USER_ID = 165
    INCOME_BASED_RATE = 78
    LAST_REVIEW = 166

    # PROOF_OF_INCOME doesn't exist in the output fields, likely because
    # it's a file attachment and not a "primitive" field type.

    @classmethod
    def from_id(cls, v):
        """Converts to a CustomField from a neon ID"""
        for k in dir(cls):
            if int(v) == getattr(cls, k):
                result = " ".join(
                    [w.capitalize() for w in k.split("_")]
                )  # Neon uses capital case names for custom fields

                # Small correction to include ampersand
                # since it cannot be used in a variable name
                if result == "Notify Board And Staff":
                    return "Notify Board & Staff"
                return result
        raise CustomFieldNotFoundError(f"No CustomField ID {v}")


@dataclass
class Category:
    """Event categories from Neon"""

    VOLUNTEER_DAY = "32"
    MEMBER_EVENT = "33"
    PROJECT_BASED_WORKSHOP = "15"
    SHOP_TECH = "34"
    SKILLS_AND_SAFETY_WORKSHOP = "16"
    SOMETHING_ELSE_AMAZING = "27"
