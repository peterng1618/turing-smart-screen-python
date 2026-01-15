# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from tests.tools.theme_validator import ThemeValidator

validator = ThemeValidator()
themes = validator.list_active_themes()

@pytest.mark.parametrize("theme_name", themes)
def test_theme_regression(theme_name):
    """
    Regression test for every theme in res/themes/.
    Ensures that the theme can be loaded and rendered without errors.
    """
    result = validator.validate_theme(theme_name)
    
    if not result.success:
        msg = f"Theme '{theme_name}' failed validation.\nError: {result.error}"
        if result.traceback:
            msg += f"\nTraceback:\n{result.traceback}"
        pytest.fail(msg)
