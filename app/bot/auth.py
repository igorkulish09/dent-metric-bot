from app.config import settings

def is_admin(user_id: int) -> bool:
    return not settings.admin_id_set or user_id in settings.admin_id_set
