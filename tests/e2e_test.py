import hashlib
import json
import time

import requests

BASE_A = "http://localhost:7100/mcp"
BASE_B = "http://localhost:7101/mcp"

AXL_A = "8b6a18ac96f7c30c85689627f47625eed10d3309f91be8aa8f47141b9eb1cb9f"
AXL_B = "8176eb050803ffea4407d02f738102a5c7c726e2d2ecfdd9bc0c3bcd672a78cb"

JOB_ID = "e2e_test_job_001"
OUTPUT = "analysis complete: sentiment is positive with 87% confidence"
CRITERIA = "perform sentiment analysis and return confidence score"


def call(base_url: str, tool: str, args: dict, headers: dict = {}) -> dict:
    """Call a loaf-sizzler MCP tool and return result."""
    try:
        response = requests.post(
            base_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": tool,
                    "arguments": args,
                },
            },
            headers={"Content-Type": "application/json", **headers},
            timeout=10,
        )
        return response.json()
    except requests.RequestException as e:
        return {
            "error": f"request failed: {e}",
            "result": {},
            "meta": {
                "base_url": base_url,
                "tool": tool,
                "args": args,
                "headers": headers,
            },
        }
    except ValueError as e:
        return {
            "error": f"invalid json response: {e}",
            "result": {},
            "meta": {
                "base_url": base_url,
                "tool": tool,
                "args": args,
                "headers": headers,
            },
        }


def _dump_failure(result: dict):
    print("     result:")
    print(json.dumps(result, indent=2, sort_keys=True))


def assert_ok(result: dict, expected_key: str, expected_value: str, step: str):
    """Assert result contains expected key/value. Print pass or fail."""
    try:
        actual = result["result"][expected_key]
        if actual == expected_value:
            print(f"  ✅ {step}")
        else:
            print(f"  ❌ {step} — expected {expected_key}={expected_value}, got {actual}")
            _dump_failure(result)
    except Exception as e:
        print(f"  ❌ {step} — exception: {e}")
        _dump_failure(result)


def assert_contains(result: dict, expected_type: str, step: str):
    """Assert inbox contains a message of expected type."""
    try:
        messages = result["result"]["messages"]
        types = [m.get("type") for m in messages]
        if expected_type in types:
            print(f"  ✅ {step}")
        else:
            print(f"  ❌ {step} — expected type '{expected_type}' in inbox, got {types}")
            _dump_failure(result)
    except Exception as e:
        print(f"  ❌ {step} — exception: {e}")
        _dump_failure(result)


def setup():
    """Clear both inboxes before test."""
    clear_a = call(BASE_A, "clear_inbox", {})
    assert_ok(clear_a, "status", "cleared", "A inbox cleared")

    clear_b = call(BASE_B, "clear_inbox", {})
    assert_ok(clear_b, "status", "cleared", "B inbox cleared")


def test_phase_1_bidding():
    """
    A bids to B.
    B checks inbox — sees bid.
    """
    bid = call(
        BASE_A,
        "bid_job",
        {
            "poster_axl_key": AXL_B,
            "job_id": JOB_ID,
            "criteria": CRITERIA,
        },
    )
    assert_ok(bid, "status", "bid_sent", "A sent bid to B")

    inbox_b = call(BASE_B, "get_inbox", {})
    assert_contains(inbox_b, "bid", "B inbox contains bid")


def test_phase_2_acceptance():
    """
    B accepts A's bid.
    A checks inbox — sees acceptance.
    """
    accept = call(
        BASE_B,
        "accept_bid",
        {
            "bidder_axl_key": AXL_A,
            "job_id": JOB_ID,
        },
    )
    assert_ok(accept, "status", "accepted", "B accepted A bid")

    inbox_a = call(BASE_A, "get_inbox", {})
    assert_contains(inbox_a, "acceptance", "A inbox contains acceptance")


def test_phase_3_submit_work():
    """
    A submits work with output.
    Assert status is submitted.
    Assert output_hash is returned.
    """
    result = call(
        BASE_A,
        "submit_work",
        {
            "job_id": JOB_ID,
            "output": OUTPUT,
        },
    )
    assert_ok(result, "status", "submitted", "A submitted work")

    expected_hash = hashlib.sha256(OUTPUT.encode()).hexdigest()
    try:
        output_hash = result["result"]["output_hash"]
        if output_hash == expected_hash:
            print("  ✅ submit_work output_hash returned")
        else:
            print(f"  ❌ submit_work output_hash mismatch — expected {expected_hash}, got {output_hash}")
            _dump_failure(result)
    except Exception as e:
        print(f"  ❌ submit_work output_hash missing — exception: {e}")
        _dump_failure(result)


def test_phase_4_verify_bid():
    """
    B bids to verify A's work.
    A checks inbox — sees verify_bid.
    """
    verify_bid = call(
        BASE_B,
        "bid_verify",
        {
            "poster_axl_key": AXL_A,
            "job_id": JOB_ID,
        },
    )
    assert_ok(verify_bid, "status", "bid_sent", "B sent verify bid to A")

    inbox_a = call(BASE_A, "get_inbox", {})
    assert_contains(inbox_a, "verify_bid", "A inbox contains verify_bid")


def test_phase_5_accept_verifier():
    """
    A accepts B as verifier.
    B checks inbox — sees verifier_acceptance with worker_axl_key.
    """
    accept = call(
        BASE_A,
        "accept_verifier",
        {
            "verifier_axl_key": AXL_B,
            "job_id": JOB_ID,
            "worker_axl_key": AXL_A,
        },
    )
    assert_ok(accept, "status", "accepted", "A accepted B as verifier")

    inbox_b = call(BASE_B, "get_inbox", {})
    assert_contains(inbox_b, "verifier_acceptance", "B inbox contains verifier_acceptance")

    try:
        messages = inbox_b["result"]["messages"]
        matches = [m for m in messages if m.get("type") == "verifier_acceptance" and m.get("job_id") == JOB_ID]
        if matches and matches[-1].get("worker_axl_key") == AXL_A:
            print("  ✅ verifier_acceptance includes worker_axl_key")
        else:
            print("  ❌ verifier_acceptance missing correct worker_axl_key")
            _dump_failure(inbox_b)
    except Exception as e:
        print(f"  ❌ verifier_acceptance parse failure — exception: {e}")
        _dump_failure(inbox_b)


def test_phase_6_get_output():
    """
    B requests output from A.
    Calls get_output on A with X-From-Peer-Id header.
    Assert output matches what was submitted.
    Assert output_hash matches.
    """
    result = call(
        BASE_A,
        "get_output",
        {"job_id": JOB_ID},
        headers={"X-From-Peer-Id": AXL_B},
    )

    try:
        output = result["result"]["output"]
        if output == OUTPUT:
            print("  ✅ get_output returned expected output")
        else:
            print(f"  ❌ get_output output mismatch — expected '{OUTPUT}', got '{output}'")
            _dump_failure(result)
    except Exception as e:
        print(f"  ❌ get_output missing output — exception: {e}")
        _dump_failure(result)

    expected_hash = hashlib.sha256(OUTPUT.encode()).hexdigest()
    try:
        output_hash = result["result"]["output_hash"]
        if output_hash == expected_hash:
            print("  ✅ get_output returned expected output_hash")
        else:
            print(f"  ❌ get_output hash mismatch — expected {expected_hash}, got {output_hash}")
            _dump_failure(result)
    except Exception as e:
        print(f"  ❌ get_output missing output_hash — exception: {e}")
        _dump_failure(result)


def test_phase_7_submit_verdict():
    """
    B submits verdict to A.
    A checks inbox — sees settlement message.
    Assert result is pass.
    """
    verdict = call(
        BASE_B,
        "submit_verdict",
        {
            "poster_axl_key": AXL_A,
            "job_id": JOB_ID,
            "verdict": "pass",
            "reason": "output matched criteria",
        },
    )
    assert_ok(verdict, "status", "verdict_sent", "B sent verdict to A")

    inbox_a = call(BASE_A, "get_inbox", {})
    assert_contains(inbox_a, "settlement", "A inbox contains settlement")

    try:
        messages = inbox_a["result"]["messages"]
        settlements = [m for m in messages if m.get("type") == "settlement" and m.get("job_id") == JOB_ID]
        if settlements and settlements[-1].get("result") == "pass":
            print("  ✅ settlement result is pass")
        else:
            print("  ❌ settlement result is not pass")
            _dump_failure(inbox_a)
    except Exception as e:
        print(f"  ❌ settlement parse failure — exception: {e}")
        _dump_failure(inbox_a)


def run_all():
    print("\n🍞 loaf-sizzler e2e test\n")
    print("─" * 40)

    print("\n[setup] clearing inboxes...")
    setup()

    print("\n[phase 1] bidding...")
    test_phase_1_bidding()
    time.sleep(1)

    print("\n[phase 2] acceptance...")
    test_phase_2_acceptance()
    time.sleep(1)

    print("\n[phase 3] submit work...")
    test_phase_3_submit_work()
    time.sleep(1)

    print("\n[phase 4] verify bid...")
    test_phase_4_verify_bid()
    time.sleep(1)

    print("\n[phase 5] accept verifier...")
    test_phase_5_accept_verifier()
    time.sleep(1)

    print("\n[phase 6] get output...")
    test_phase_6_get_output()
    time.sleep(1)

    print("\n[phase 7] submit verdict...")
    test_phase_7_submit_verdict()

    print("\n" + "─" * 40)
    print("🍞 test complete\n")


if __name__ == "__main__":
    run_all()
