"""Constants and other datatypes for Neon integration"""
from dataclasses import dataclass

URL_BASE = "https://api.neoncrm.com/v2"
ADMIN_URL = "https://protohaven.app.neoncrm.com/np/admin"


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

    @classmethod
    def from_id(cls, v):
        """Converts to a CustomField from a neon ID"""
        for k in dir(cls):
            if int(v) == getattr(cls, k):
                return " ".join(
                    [w.capitalize() for w in k.split("_")]
                )  # Neon uses capital case names for custom fields
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
