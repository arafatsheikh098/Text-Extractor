"""Exceptions that are meaningful to end users of the app."""

from __future__ import annotations


class UserFacingError(Exception):
    """An error whose message is safe and useful to show to the person using the app."""


class Cancelled(Exception):
    """Raised inside a job when its cancellation flag has been tripped."""
