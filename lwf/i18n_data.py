"""
Texts stored in the database that the UI shows translated: the labels of the
workflow steps (Action.action_display). Each is a literal here so that
makemessages finds it.
"""
from django.utils.translation import gettext_noop

WORKFLOW_STEP_LABELS = [
    gettext_noop('Approve'),
    gettext_noop('Cancel'),
    gettext_noop('Change Request'),
    gettext_noop('Close'),
    gettext_noop('Confirm Disbursement'),
    gettext_noop('Confirm Disbursement Complete'),
    gettext_noop('Confirm Valuation'),
    gettext_noop('Confirm for Approval Condition'),
    gettext_noop('Endorse to Sale Support'),
    gettext_noop('General Director Approve'),
    gettext_noop('Head of Credit upload Approval Result'),
    gettext_noop('Preparation Complete'),
    gettext_noop('Re-Open'),
    gettext_noop('Re-Submit'),
    gettext_noop('Recommend to Approver 1'),
    gettext_noop('Reject'),
    gettext_noop('Reject Disbursement'),
    gettext_noop('Request CED Check Approval Condition'),
    gettext_noop('Request CED Update'),
    gettext_noop('Request Change Term and Condition'),
    gettext_noop('Request Docs Preparation'),
    gettext_noop('Request Re-Submit'),
    gettext_noop('Request Sale Update'),
    gettext_noop('Request Sale Update CR'),
    gettext_noop('Request Update'),
    gettext_noop('Submit to CED'),
    gettext_noop('Submit to Credit Manager'),
    gettext_noop('Submit to General Director'),
    gettext_noop('Submit to Head of Credit'),
    gettext_noop('Submit to Head of PFS'),
    gettext_noop('Submit to Head of Sale'),
    gettext_noop('Submit to Sale Leader'),
    gettext_noop('Update to Aprrover 1'),
    gettext_noop('Update to Aprrover 2'),
    gettext_noop('Update to CED'),
    gettext_noop('Update to CRA'),
    gettext_noop('Update to Sale Support'),
    gettext_noop('Valuation Review Request'),
]
