"""Utility functions for CLI commands."""

import asyncio


def run_async(coro):
    """Run an async coroutine synchronously.

    Click is synchronous, so we wrap async calls with this helper.

    Args:
        coro: Async coroutine to run

    Returns:
        Result of the coroutine
    """
    return asyncio.run(coro)
