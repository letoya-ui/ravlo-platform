"""Regression test for the default outbound mail provider.

Before SendGrid, Ravlo sent transactional email through its own
Microsoft 365 mailbox's SMTP relay (smtp.office365.com), which is free
since it rides on the existing M365 subscription rather than a separate
paid service. The MAIL_SERVER default should still point there so any
environment that doesn't set MAIL_SERVER explicitly (matching
LoanMVP/.env.example) doesn't silently fall back to SendGrid.
"""
import importlib


def test_mail_server_defaults_to_office365(monkeypatch):
    monkeypatch.delenv("MAIL_SERVER", raising=False)

    from LoanMVP import config as config_module
    importlib.reload(config_module)

    assert config_module.Config.MAIL_SERVER == "smtp.office365.com"
