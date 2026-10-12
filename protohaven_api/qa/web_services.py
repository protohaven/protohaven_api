"""Registry of production-only web service QA checks.

Cases that can be exercised without production state live in the Svelte
Cypress component tests and Python handler/unit tests. The checks below
require production credentials or external state (real Neon accounts,
Discord notifications, Wyze door state, Square subscriptions, Booked
reservations, or Airtable side effects) and are collected here for the
post-deploy QA pass.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WebServiceCheck:
    """A single manual/production-only web service QA check."""

    path: str
    description: str
    detail: str = ""


PROD_ONLY_CHECKS = (
    WebServiceCheck(
        "/welcome",
        "Member sign in fails with hello+testnonmember@protohaven.org",
        "Requires a real Neon account with no active membership.",
    ),
    WebServiceCheck(
        "/welcome",
        "Member sign in with hello+testalert@protohaven.org sends the notice",
        "Requires the real Neon alert account and Discord delivery.",
    ),
    WebServiceCheck(
        "/welcome",
        "Member sign in with hello+testmember@protohaven.org sends multiple-accounts alert",
        "Requires the real Neon test member and #membership-automation delivery.",
    ),
    WebServiceCheck(
        "/welcome",
        "Member sign in with hello+testampmake@protohaven.org succeeds with no validation alerts",
        "Requires the real AMP test account.",
    ),
    WebServiceCheck(
        "/welcome",
        "Guest sign in presents waiver, completes, and records a Sign Ins row",
        "Requires production Airtable sign-in recording.",
    ),
    WebServiceCheck(
        "/techs",
        "Door lock state matches Wyze state",
        "Requires production Wyze credentials and live door hardware.",
    ),
    WebServiceCheck(
        "/techs",
        "Calendar swap overrides send an alert to #techs",
        "Requires production forecast data and Discord delivery.",
    ),
    WebServiceCheck(
        "/techs",
        "Storage subscription state and unpaid invoice badges match Square/Neon",
        "Requires production Square and Neon subscription data.",
    ),
    WebServiceCheck(
        "/techs",
        "Events tab can create, register, unregister, and delete a techs-only class",
        "Requires production Eventbrite/Neon class creation and cleanup.",
    ),
    WebServiceCheck(
        "/instructor",
        "Adding a new class on a holiday triggers validation error",
        "Requires production calendar data.",
    ),
    WebServiceCheck(
        "/instructor",
        "Adding a new class on a day with similar area reservations triggers validation error",
        "Requires production Booked reservations.",
    ),
    WebServiceCheck(
        "/instructor",
        "Adding a new class too close to a recent run of that class triggers validation error",
        "Requires production class history.",
    ),
    WebServiceCheck(
        "/instructor",
        "Schedule overrides send alerts to #edu-leads",
        "Requires production Discord delivery.",
    ),
    WebServiceCheck(
        "/instructor",
        "Supplies needed / OK sends notice to #supply-automation",
        "Requires production Discord delivery.",
    ),
    WebServiceCheck(
        "/instructor",
        "Instructor creation / enrollment / disenrollment via roster",
        "Requires production Neon and Airtable capabilities data.",
    ),
)
