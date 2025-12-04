"""
Configuration package for IDP platform.

Provides profile loading and configuration management.
"""

from config.profile_loader import ProfileLoader, ProfileNotFoundError

__all__ = ['ProfileLoader', 'ProfileNotFoundError']
