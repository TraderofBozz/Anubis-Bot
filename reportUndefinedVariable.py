"""
Module for handling undefined variables
"""
from typing import Any, Optional

def check_variable(var_name: str, scope: dict) -> Optional[Any]:
    """Check if variable is defined in scope"""
    return scope.get(var_name)