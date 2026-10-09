from types import SimpleNamespace

import pytest

from api.services.telephony.providers.ari.provider import ARIProvider
from api.services.workflow.pipecat_engine_custom_tools import _transfer_caller_id


def _run(**initial_context):
    return SimpleNamespace(initial_context=initial_context)


def test_outbound_run_presents_the_called_number():
    run = _run(direction="outbound", caller_number="+15550001111", called_number="+15552223333")
    assert _transfer_caller_id(run) == "+15552223333"


def test_inbound_run_presents_the_caller_number():
    run = _run(direction="inbound", caller_number="+15552223333", called_number="8000")
    assert _transfer_caller_id(run) == "+15552223333"


def test_phone_number_column_is_the_fallback():
    assert _transfer_caller_id(_run(phone_number=" +15559990000 ")) == "+15559990000"


def test_no_number_means_no_caller_id():
    assert _transfer_caller_id(_run()) is None
    assert _transfer_caller_id(SimpleNamespace(initial_context=None)) is None


@pytest.mark.asyncio
async def test_ari_transfer_originate_carries_the_caller_id(monkeypatch):
    provider = ARIProvider(
        {"ari_endpoint": "http://asterisk:8088", "app_name": "dograh", "app_password": "x", "stasis_app_name": "dograh_test"}
    )
    seen = {}

    class _Response:
        status = 200

        async def text(self):
            return '{"id": "chan-1"}'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _Session:
        def post(self, endpoint, params=None, auth=None):
            seen["params"] = params
            return _Response()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _Manager:
        async def store_transfer_channel_mapping(self, *args):
            pass

        async def remove_transfer_context(self, *args):
            pass

    async def _manager():
        return _Manager()

    monkeypatch.setattr("aiohttp.ClientSession", lambda *a, **k: _Session())
    monkeypatch.setattr(
        "api.services.telephony.call_transfer_manager.get_call_transfer_manager", _manager
    )

    await provider.transfer_call("Local/55532@ai-to-closer", "t-1", "conf", caller_id="+15552223333")
    assert seen["params"]["callerId"] == "+15552223333"

    await provider.transfer_call("Local/55532@ai-to-closer", "t-2", "conf")
    assert "callerId" not in seen["params"]
