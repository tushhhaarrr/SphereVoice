"""Campaign module — pre-built campaign templates.

Each template provides sensible defaults for variable_mapping,
writeback_mapping, and call_settings so users can launch common
campaign types without configuration from scratch.
"""

from __future__ import annotations

from typing import Any

CAMPAIGN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "lead_qualification",
        "name": "Lead Qualification",
        "description": "Call new leads to assess interest level, budget, and timeline. Qualify as Hot/Warm/Cold and log outcome to CRM.",
        "category": "sales",
        "variable_mapping": {
            "caller_name": "Full_Name",
            "caller_email": "Email",
            "caller_phone": "Phone",
            "caller_company": "Company",
            "lead_source": "Lead_Source",
        },
        "writeback_mapping": {
            "qualification_status": "Lead_Status",
            "budget_range": "Budget_Range",
            "timeline": "Timeline",
            "notes": "Description",
        },
        "call_settings": {
            "max_concurrent": 5,
            "calls_per_minute": 10,
            "max_retries": 2,
            "retry_delay_minutes": 60,
        },
        "extraction_hints": [
            "qualification_status",
            "budget_range",
            "timeline",
            "interest_level",
            "next_steps",
        ],
    },
    {
        "id": "appointment_setting",
        "name": "Appointment Setting",
        "description": "Schedule meetings or demos with prospects. Confirm preferred date/time and send calendar invite.",
        "category": "sales",
        "variable_mapping": {
            "caller_name": "Full_Name",
            "caller_email": "Email",
            "caller_phone": "Phone",
            "caller_company": "Company",
            "product_interest": "Product_Interest",
        },
        "writeback_mapping": {
            "meeting_scheduled": "Meeting_Scheduled",
            "preferred_date": "Preferred_Meeting_Date",
            "preferred_time": "Preferred_Meeting_Time",
            "meeting_notes": "Description",
        },
        "call_settings": {
            "max_concurrent": 3,
            "calls_per_minute": 5,
            "max_retries": 3,
            "retry_delay_minutes": 120,
        },
        "extraction_hints": [
            "meeting_scheduled",
            "preferred_date",
            "preferred_time",
            "contact_method",
        ],
    },
    {
        "id": "follow_up_call",
        "name": "Follow-up Call",
        "description": "Re-engage leads who showed interest but haven't converted. Check status and address objections.",
        "category": "retention",
        "variable_mapping": {
            "caller_name": "Full_Name",
            "caller_email": "Email",
            "last_interaction": "Last_Activity_Time",
            "previous_interest": "Product_Interest",
        },
        "writeback_mapping": {
            "follow_up_outcome": "Lead_Status",
            "objections": "Objections",
            "next_action": "Next_Step",
            "notes": "Description",
        },
        "call_settings": {
            "max_concurrent": 5,
            "calls_per_minute": 8,
            "max_retries": 1,
            "retry_delay_minutes": 30,
        },
        "extraction_hints": [
            "follow_up_outcome",
            "objections",
            "interest_renewed",
            "next_action",
        ],
    },
    {
        "id": "survey",
        "name": "Survey / Feedback",
        "description": "Collect structured feedback from customers via voice survey. Capture ratings and open-ended responses.",
        "category": "research",
        "variable_mapping": {
            "caller_name": "Full_Name",
            "caller_email": "Email",
            "product_used": "Product_Name",
        },
        "writeback_mapping": {
            "overall_rating": "Survey_Rating",
            "feedback_summary": "Survey_Feedback",
            "nps_score": "NPS_Score",
        },
        "call_settings": {
            "max_concurrent": 10,
            "calls_per_minute": 15,
            "max_retries": 1,
            "retry_delay_minutes": 120,
        },
        "extraction_hints": [
            "overall_rating",
            "satisfaction_level",
            "feedback_summary",
            "improvement_suggestions",
            "nps_score",
        ],
    },
    {
        "id": "announcement",
        "name": "Announcement / Notification",
        "description": "Deliver important announcements — pricing changes, event reminders, or service updates — to a contact list.",
        "category": "communication",
        "variable_mapping": {
            "caller_name": "Full_Name",
            "caller_phone": "Phone",
        },
        "writeback_mapping": {
            "acknowledged": "Announcement_Acknowledged",
            "response": "Announcement_Response",
        },
        "call_settings": {
            "max_concurrent": 10,
            "calls_per_minute": 20,
            "max_retries": 2,
            "retry_delay_minutes": 60,
        },
        "extraction_hints": [
            "acknowledged",
            "questions_asked",
            "response",
        ],
    },
]


def get_campaign_templates() -> list[dict[str, Any]]:
    """Return all available campaign templates."""
    return CAMPAIGN_TEMPLATES


def get_template_by_id(template_id: str) -> dict[str, Any] | None:
    """Look up a single campaign template by its ID."""
    for t in CAMPAIGN_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None
