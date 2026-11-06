class AppError(Exception):
    """Base class for expected, safely reportable application errors."""


class ConfigurationError(AppError):
    pass


class ApiError(AppError):
    pass


class ApiSchemaError(ApiError):
    pass


class UnsafeSelectionError(ApiError):
    """Raised when the response cannot prove which clients are newest."""
