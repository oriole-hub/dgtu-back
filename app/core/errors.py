from dataclasses import dataclass


@dataclass(frozen=True)
class ApiError:
    code: str
    msg: str
    status: int


INVALID_CREDENTIALS = ApiError("invalid_credentials", "Invalid login or password", 401)
USER_EXISTS = ApiError("user_exists", "User already exists", 409)
NOT_FOUND = ApiError("not_found", "Resource not found", 404)
UNAUTHORIZED = ApiError("unauthorized", "Unauthorized", 401)
INVALID_TOKEN = ApiError("invalid_token", "Invalid token", 401)
PASS_INVALID = ApiError("invalid", "Pass is invalid", 404)
PASS_EXPIRED = ApiError("expired", "Pass is expired", 410)
PASS_ALREADY_USED = ApiError("already_used", "Pass is already used", 409)
PASS_REVOKED = ApiError("revoked", "Pass is revoked", 409)
FORBIDDEN = ApiError("forbidden", "Insufficient role permissions", 403)
ACCOUNT_EXPIRED = ApiError("account_expired", "Account is expired", 403)
PASS_LIMIT_REACHED = ApiError("pass_limit_reached", "Pass creation limit is reached", 403)
OFFICE_HEAD_EXISTS = ApiError("office_head_exists", "Office head already exists", 409)
OFFICE_REQUIRED = ApiError("office_required", "User must be assigned to an office", 400)
OFFICE_NOT_FOUND = ApiError("office_not_found", "Office not found", 404)
OFFICE_SCOPE_VIOLATION = ApiError("office_scope_violation", "Pass can be used only in assigned office", 403)
OFFICE_INACTIVE = ApiError("office_inactive", "Office is inactive", 403)
