"""`cti_alerts.mailer.create_graph_draft` -- port `_send_newsletter_email()`/
`_create_graph_draft()` lama (jalur Graph doang, lihat docstring modul).
Mock `msal`/`httpx` -- gak boleh manggil Azure AD/Graph API beneran dari
test unit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from cti_alerts.mailer import GraphAuthError, GraphSendError, create_graph_draft
from cti_core.config import GraphSettings

_SETTINGS = GraphSettings(
    tenant_id="tenant-1",
    client_id="client-1",
    client_secret="secret-1",
    sender="cti@example.com",
    cc="a@example.com, b@example.com",
)


def _mock_msal_app(token: str | None = "fake-token") -> MagicMock:
    app = MagicMock()
    app.acquire_token_for_client.return_value = (
        {"access_token": token} if token else {"error_description": "bad creds"}
    )
    return app


def test_auth_failure_raises_graph_auth_error() -> None:
    with (
        patch(
            "cti_alerts.mailer.msal.ConfidentialClientApplication",
            return_value=_mock_msal_app(None),
        ),
        pytest.raises(GraphAuthError),
    ):
        create_graph_draft("<html/>", "subject", settings=_SETTINGS)


def test_non_201_response_raises_graph_send_error() -> None:
    mock_resp = MagicMock(status_code=400, text="Bad Request")
    with (
        patch(
            "cti_alerts.mailer.msal.ConfidentialClientApplication", return_value=_mock_msal_app()
        ),
        patch("cti_alerts.mailer.httpx.post", return_value=mock_resp) as mock_post,
        pytest.raises(GraphSendError),
    ):
        create_graph_draft("<html/>", "subject", settings=_SETTINGS)
    assert mock_post.called


def test_successful_send_returns_message_id() -> None:
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"id": "msg-123"}
    with (
        patch(
            "cti_alerts.mailer.msal.ConfidentialClientApplication", return_value=_mock_msal_app()
        ),
        patch("cti_alerts.mailer.httpx.post", return_value=mock_resp) as mock_post,
    ):
        result = create_graph_draft("<html/>content", "subject line", settings=_SETTINGS)

    assert result == "msg-123"
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["subject"] == "subject line"
    assert call_kwargs["json"]["body"] == {"contentType": "html", "content": "<html/>content"}
    assert call_kwargs["json"]["ccRecipients"] == [
        {"emailAddress": {"address": "a@example.com"}},
        {"emailAddress": {"address": "b@example.com"}},
    ]
    assert f"/users/{_SETTINGS.sender}/messages" in mock_post.call_args.args[0]


def test_empty_cc_produces_empty_recipient_list() -> None:
    settings = GraphSettings(
        tenant_id="t", client_id="c", client_secret="s", sender="cti@example.com", cc=""
    )
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"id": "msg-1"}
    with (
        patch(
            "cti_alerts.mailer.msal.ConfidentialClientApplication", return_value=_mock_msal_app()
        ),
        patch("cti_alerts.mailer.httpx.post", return_value=mock_resp) as mock_post,
    ):
        create_graph_draft("<html/>", "subject", settings=settings)

    assert mock_post.call_args.kwargs["json"]["ccRecipients"] == []
