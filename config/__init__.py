"""
Configuration package for IDP platform.

Provides profile loading and configuration management.
"""

from config.profile_loader import (
    ProfileLoader,
    ProfileNotFoundError,
    ProfileValidationError,
    get_profile_for_environment,
)

__all__ = [
    'ProfileLoader',
    'ProfileNotFoundError',
    'ProfileValidationError',
    'get_profile_for_environment',
]
