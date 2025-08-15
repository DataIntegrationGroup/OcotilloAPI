def audit_add(user, obj):
    # TODO: see note in "AuditMixin"
    if user:
        obj.created_by_id = user["sub"]
        obj.created_by_name = user["name"]
