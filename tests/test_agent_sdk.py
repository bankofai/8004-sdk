import re

from sdk.agent_sdk import AgentSDK
from sdk.contract_adapter import ContractAdapter
from sdk.signer import Signer


class RecordingAdapter(ContractAdapter):
    def __init__(self) -> None:
        self.calls = []

    def call(self, method: str, params: list) -> dict:
        self.calls.append(("call", method, params))
        return {"method": method, "params": params}

    def send(self, contract: str, method: str, params: list, signer: Signer) -> str:
        self.calls.append(("send", contract, method, params, signer.get_address()))
        return "txid"


class FixedSigner(Signer):
    def __init__(self, address: str = "TB1JKi9cPxrwy34n4iVYif8W7h9mfn9vXD") -> None:
        self._address = address

    def get_address(self) -> str:
        return self._address

    def sign_tx(self, unsigned_tx):  # pragma: no cover - not used
        return unsigned_tx

    def sign_message(self, payload: bytes) -> str:
        return "0x" + ("11" * 65)


def _last_call(adapter: RecordingAdapter):
    return adapter.calls[-1]


def test_validation_request_params() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    tx_id = sdk.validation_request(
        validator_addr="TValidator",
        agent_id=7,
        request_uri="ipfs://test",
        request_hash="0x" + ("aa" * 32),
    )
    assert tx_id == "txid"
    call = _last_call(adapter)
    assert call[0] == "send"
    assert call[1] == "validation"
    assert call[2] == "validationRequest"
    params = call[3]
    assert params[0] == "TValidator"
    assert params[1] == 7
    assert params[2] == "ipfs://test"
    assert params[3] == bytes.fromhex("aa" * 32)


def test_validation_response_params() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.validation_response(
        request_hash="0x" + ("bb" * 32),
        response=100,
        response_uri="ipfs://resp",
        response_hash="0x" + ("cc" * 32),
        tag="0x" + ("dd" * 32),
    )
    call = _last_call(adapter)
    params = call[3]
    assert params[0] == bytes.fromhex("bb" * 32)
    assert params[1] == 100
    assert params[2] == "ipfs://resp"
    assert params[3] == bytes.fromhex("cc" * 32)
    assert params[4] == bytes.fromhex("dd" * 32)


def test_submit_reputation_params() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.submit_reputation(
        agent_id=6,
        score=95,
        tag1="0x" + ("11" * 32),
        tag2="0x" + ("22" * 32),
        fileuri="ipfs://file",
        filehash="0x" + ("33" * 32),
        feedback_auth="0x" + ("44" * 65),
    )
    call = _last_call(adapter)
    assert call[1] == "reputation"
    assert call[2] == "giveFeedback"
    params = call[3]
    assert params[0] == 6
    assert params[1] == 95
    assert params[2] == bytes.fromhex("11" * 32)
    assert params[3] == bytes.fromhex("22" * 32)
    assert params[4] == "ipfs://file"
    assert params[5] == bytes.fromhex("33" * 32)
    assert params[6] == bytes.fromhex("44" * 65)


def test_register_agent_token_uri_only() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.register_agent(token_uri="http://example.com/agent.json")
    call = _last_call(adapter)
    assert call[1] == "identity"
    assert call[2] == "register"
    assert call[3] == ["http://example.com/agent.json"]


def test_register_agent_empty() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.register_agent(token_uri=None)
    call = _last_call(adapter)
    assert call[3] == []


def test_register_agent_with_metadata() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    metadata = [
        {"key": "k1", "value": "v1"},
        {"key": "k2", "value": "0x" + ("aa" * 4)},
    ]
    sdk.register_agent(token_uri="http://example.com/agent.json", metadata=metadata)
    call = _last_call(adapter)
    params = call[3]
    assert params[0] == "http://example.com/agent.json"
    entries = params[1]
    assert entries[0]["key"] == "k1"
    assert entries[0]["value"] == b"v1"
    assert entries[1]["key"] == "k2"
    assert entries[1]["value"] == bytes.fromhex("aa" * 4)


def test_update_metadata_params() -> None:
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.update_metadata(agent_id=3, key="name", value="agent")
    call = _last_call(adapter)
    params = call[3]
    assert params[0] == 3
    assert params[1] == "name"
    assert params[2] == b"agent"


def test_build_feedback_auth_format() -> None:
    sdk = AgentSDK(signer=FixedSigner())
    feedback = sdk.build_feedback_auth(
        agent_id=6,
        client_addr="TB1JKi9cPxrwy34n4iVYif8W7h9mfn9vXD",
        index_limit=1,
        expiry=123,
        chain_id=10,
        identity_registry="TWG6M8RJdPKdJSb4DV1Dn6MDzcix92tMb3",
    )
    assert feedback.startswith("0x")
    assert re.fullmatch(r"0x[0-9a-fA-F]+", feedback)
    assert len(bytes.fromhex(feedback[2:])) >= 224 + 65
