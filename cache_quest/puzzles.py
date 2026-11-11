"""Pure puzzle validation and spoiler-light, state-aware hints."""

from collections.abc import Collection

from .world import FRAGMENT_IDS


def valid_code(candidate: str, expected: str) -> bool:
    """Accept exactly three ASCII digits, including any leading zeroes."""
    return (
        isinstance(candidate, str)
        and len(candidate) == 3
        and all("0" <= char <= "9" for char in candidate)
        and candidate == expected
    )


def contextual_hint(
    room_id: str,
    inventory: Collection[str],
    card_used: bool,
    vault_unlocked: bool,
    beacon_repaired: bool,
    won: bool,
) -> str:
    """Suggest a next step without disclosing a mission's numeric code."""
    if won:
        return "Mission complete! The beacon is safe. Start a new mission for a fresh challenge."
    if beacon_repaired:
        if room_id == "archive_vault":
            return "The beacon is repaired. Take the beacon to complete your mission."
        return "Return to the Archive Vault and take the repaired beacon."
    if not vault_unlocked:
        if not card_used:
            if "access card" not in inventory:
                return "Look for the access card in the Control Room and take it."
            if room_id == "hallway":
                return "Use the access card on the vault to activate its keypad."
            return "Bring your access card to the hallway and use it on the vault."
        if room_id == "lab":
            return "Inspect the terminal for the outer code digits, then inspect the maintenance log for the middle digit."
        if room_id == "maintenance":
            return "Inspect the maintenance log for the middle digit. Combine it with the lab terminal's outer digits."
        return "Inspect the terminal in the lab and the maintenance log. Use the resulting three-digit code on the hallway keypad."
    missing = [fragment for fragment in FRAGMENT_IDS if fragment not in inventory]
    if missing:
        return "Explore the Control Room, Lab, Hallway, and Maintenance to collect the missing signal fragments: " + ", ".join(missing) + "."
    if room_id == "archive_vault":
        return "Use the fragments on the beacon to repair it, then take the beacon."
    return "Bring all three signal fragments to the Archive Vault and use them on the beacon."
