import logging

audit_logger = logging.getLogger('tracker.audit')

def log_audit(user, action, details=''):
    audit_logger.info(f"User: {user.username} | Action: {action} | {details}")