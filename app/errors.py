"""Domain exceptions. Framework-free; the HTTP mapping lives in app/api/error_handlers.py."""


class VendorMatchError(Exception):
    """Base class for all domain errors."""

    code = "vendormatch_error"
    status_code = 500

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidWeightsError(VendorMatchError):
    code = "invalid_weights"
    status_code = 422


class InvalidCriteriaError(VendorMatchError):
    code = "invalid_criteria"
    status_code = 422


class ScoringError(VendorMatchError):
    code = "scoring_error"
    status_code = 500


class NotFoundError(VendorMatchError):
    code = "not_found"
    status_code = 404


class SemanticModelUnavailableError(VendorMatchError):
    code = "semantic_model_unavailable"
    status_code = 503
