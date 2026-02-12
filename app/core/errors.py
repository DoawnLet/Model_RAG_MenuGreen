"""
Error handling utilities for Menu Green.
Provides structured error responses and custom exceptions.
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    
    # Authentication & Authorization
    UNAUTHORIZED = "unauthorized"
    SUBSCRIPTION_REQUIRED = "subscription_required"
    PERMISSION_DENIED = "permission_denied"
    
    # Input Validation
    INVALID_INPUT = "invalid_input"
    MISSING_FIELD = "missing_field"
    INVALID_FORMAT = "invalid_format"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"
    
    # External Services
    GEMINI_ERROR = "gemini_error"
    SUPABASE_ERROR = "supabase_error"
    EMBEDDING_ERROR = "embedding_error"
    
    # Business Logic
    NO_RECIPES_FOUND = "no_recipes_found"
    INVALID_SUBSCRIPTION_TIER = "invalid_subscription_tier"
    INSUFFICIENT_INVENTORY = "insufficient_inventory"
    
    # System Errors
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class ErrorResponse(BaseModel):
    """Structured error response model."""
    
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "subscription_required",
                "message": "This feature requires Saving tier or higher",
                "details": {
                    "required_tier": "saving",
                    "current_tier": "free",
                    "feature": "inventory_management"
                },
                "suggestion": "Upgrade to Saving tier to access inventory management"
            }
        }


class MenuGreenException(Exception):
    """Base exception for Menu Green application."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(message)
    
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail=ErrorResponse(
                code=self.code,
                message=self.message,
                details=self.details,
                suggestion=self.suggestion
            ).model_dump()
        )


class SubscriptionRequiredException(MenuGreenException):
    """Raised when user lacks required subscription tier."""
    
    def __init__(
        self,
        required_tier: str,
        current_tier: str,
        feature: str
    ):
        super().__init__(
            code=ErrorCode.SUBSCRIPTION_REQUIRED,
            message=f"This feature requires {required_tier} tier or higher",
            status_code=status.HTTP_403_FORBIDDEN,
            details={
                "required_tier": required_tier,
                "current_tier": current_tier,
                "feature": feature
            },
            suggestion=f"Upgrade to {required_tier} tier to access {feature}"
        )


class InvalidInputException(MenuGreenException):
    """Raised when user input is invalid."""
    
    def __init__(self, field: str, reason: str):
        super().__init__(
            code=ErrorCode.INVALID_INPUT,
            message=f"Invalid input for field '{field}': {reason}",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": field, "reason": reason}
        )


class RateLimitException(MenuGreenException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": retry_after},
            suggestion=f"Please wait {retry_after} seconds before retrying"
        )


class GeminiAPIException(MenuGreenException):
    """Raised when Gemini API fails."""
    
    def __init__(self, original_error: str):
        super().__init__(
            code=ErrorCode.GEMINI_ERROR,
            message="AI service temporarily unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"error": original_error},
            suggestion="Please try again in a few moments"
        )


class SupabaseException(MenuGreenException):
    """Raised when Supabase operation fails."""
    
    def __init__(self, operation: str, original_error: str):
        super().__init__(
            code=ErrorCode.SUPABASE_ERROR,
            message=f"Database operation failed: {operation}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"operation": operation, "error": original_error}
        )


class NoRecipesFoundException(MenuGreenException):
    """Raised when no recipes match the search criteria."""
    
    def __init__(self, search_criteria: Dict[str, Any]):
        super().__init__(
            code=ErrorCode.NO_RECIPES_FOUND,
            message="No recipes found matching your criteria",
            status_code=status.HTTP_404_NOT_FOUND,
            details=search_criteria,
            suggestion="Try adjusting your search criteria or ingredients"
        )


# User-friendly error messages for Vietnamese users
ERROR_MESSAGES_VI = {
    ErrorCode.UNAUTHORIZED: "Bạn cần đăng nhập để sử dụng tính năng này",
    ErrorCode.SUBSCRIPTION_REQUIRED: "Tính năng này yêu cầu gói cao hơn",
    ErrorCode.PERMISSION_DENIED: "Bạn không có quyền truy cập",
    ErrorCode.INVALID_INPUT: "Dữ liệu nhập vào không hợp lệ",
    ErrorCode.RATE_LIMIT_EXCEEDED: "Bạn đã sử dụng quá nhiều lần. Vui lòng thử lại sau",
    ErrorCode.GEMINI_ERROR: "Dịch vụ AI tạm thời không khả dụng",
    ErrorCode.SUPABASE_ERROR: "Lỗi kết nối cơ sở dữ liệu",
    ErrorCode.NO_RECIPES_FOUND: "Không tìm thấy công thức phù hợp",
    ErrorCode.INTERNAL_ERROR: "Lỗi hệ thống. Vui lòng thử lại sau",
    ErrorCode.SERVICE_UNAVAILABLE: "Dịch vụ tạm thời không khả dụng",
}


def get_vietnamese_message(code: ErrorCode) -> str:
    """Get Vietnamese error message for error code."""
    return ERROR_MESSAGES_VI.get(code, "Đã xảy ra lỗi không xác định")
