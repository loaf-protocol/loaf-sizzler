"""Tool to approve USDC allowance for protocol usage."""


def approve_usdc(args: dict, contract) -> dict:
    """Approve USDC allowance for protocol usage."""
    # Default to "infinite" approval if amount not specified
    amount = args.get("amount", 2**256 - 1)
    return contract.approve_usdc(amount)
