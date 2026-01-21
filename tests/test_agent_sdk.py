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
    """Test validation_response with Jan 2026 Update (tag is now string)"""
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
        tag="execution",  # Jan 2026: tag is now string, not bytes32
    )
    call = _last_call(adapter)
    params = call[3]
    assert params[0] == bytes.fromhex("bb" * 32)
    assert params[1] == 100
    assert params[2] == "ipfs://resp"
    assert params[3] == bytes.fromhex("cc" * 32)
    assert params[4] == "execution"  # Jan 2026: tag is string


def test_submit_reputation_params() -> None:
    """Test submit_reputation with Jan 2026 Update (no feedbackAuth, new endpoint param)"""
    adapter = RecordingAdapter()
    sdk = AgentSDK(
        signer=FixedSigner(),
        contract_adapter=adapter,
    )
    sdk.submit_reputation(
        agent_id=6,
        score=95,
        tag1="execution",  # Jan 2026: tags are now strings
        tag2="market-swap",
        endpoint="/a2a/x402/execute",  # Jan 2026: new endpoint param
        feedback_uri="ipfs://file",  # Jan 2026: renamed from fileuri
        feedback_hash="0x" + ("33" * 32),  # Jan 2026: renamed from filehash
    )
    call = _last_call(adapter)
    assert call[1] == "reputation"
    assert call[2] == "giveFeedback"
    params = call[3]
    assert params[0] == 6  # agent_id
    assert params[1] == 95  # score
    assert params[2] == "execution"  # tag1 (string)
    assert params[3] == "market-swap"  # tag2 (string)
    assert params[4] == "/a2a/x402/execute"  # endpoint
    assert params[5] == "ipfs://file"  # feedback_uri
    assert params[6] == bytes.fromhex("33" * 32)  # feedback_hash


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
    # entries 是 tuple 列表: [(key, value), ...]
    assert entries[0][0] == "k1"
    assert entries[0][1] == b"v1"
    assert entries[1][0] == "k2"
    assert entries[1][1] == bytes.fromhex("aa" * 4)


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
