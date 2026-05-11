import os
import random
from datetime import datetime, timedelta, timezone
from groq import Groq

from faker import Faker


# ---- helpers ---------------------------------------------------------------
def _random_timestamp(fake: Faker, start: datetime, end: datetime) -> datetime:
    """Return a random ``datetime`` between *start* and *end*."""
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=random.randint(0, int(delta)))


def _print_separator(char: str = "=", width: int = 72) -> None:
    print(char * width)


# ---- transaction generation ------------------------------------------------

def generate_transactions(seed: int = 42) -> list[dict]:
    """Return 10 fake credit-card transactions, some with suspicious patterns."""
    fake = Faker()
    Faker.seed(seed)  # deterministic output for reproducibility
    random.seed(seed)

    base_time = datetime(2026, 5, 9, 8, 0, 0, tzinfo=timezone.utc)

    # Definitions: (text label, transaction builder callable)
    # fmt is a helper that calls fake.simple_profile() etc.
    def _normal_txn() -> dict:
        return {
            "txn_id": fake.uuid4()[:8],
            "cardholder": fake.name(),
            "amount": round(random.uniform(10, 150), 2),
            "timestamp": _random_timestamp(fake, base_time, base_time + timedelta(hours=10)),
            "merchant": fake.company(),
            "category": random.choice(["groceries", "dining", "gas", "entertainment"]),
            "location": fake.city(),
            "location_country": fake.country(),
            "cardholder_home": fake.city(),
        }

    def _suspicious_txn(high_amount: bool, odd_hour: bool, foreign: bool) -> dict:
        txn = _normal_txn()
        if high_amount:
            txn["amount"] = round(random.uniform(2000, 12000), 2)
        if odd_hour:
            # Shift the timestamp window to 02:00-04:00 UTC.
            odd_base = base_time.replace(hour=2, minute=0)
            txn["timestamp"] = _random_timestamp(fake, odd_base, odd_base + timedelta(hours=2))
        if foreign:
            # Cardholder is in the US; transaction is in a high-risk country.
            txn["cardholder_home"] = fake.city() + ", United States"
            foreign_countries = ["Russia", "Nigeria", "Philippines", "China", "Brazil"]
            txn["location_country"] = random.choice(foreign_countries)
        return txn

    transactions = [
        # 1-4: normal transactions
        _normal_txn(),
        _normal_txn(),
        _normal_txn(),
        _normal_txn(),
        # 5: very high amount (>$5000)
        _suspicious_txn(high_amount=True, odd_hour=False, foreign=False),
        # 6: unusual hour (2am-4am)
        _suspicious_txn(high_amount=False, odd_hour=True, foreign=False),
        # 7: foreign country (cardholder is in US, transaction in Nigeria)
        _suspicious_txn(high_amount=False, odd_hour=False, foreign=True),
        # 8: high amount + odd hour (compounded risk)
        _suspicious_txn(high_amount=True, odd_hour=True, foreign=False),
        # 9: high amount + foreign (very suspicious)
        _suspicious_txn(high_amount=True, odd_hour=False, foreign=True),
        # 10: normal (control)
        _normal_txn(),
    ]

    # Assign IDs 1-10 for readability
    for i, t in enumerate(transactions, 1):
        t["txn_id"] = f"TXN{i:03d}"

    return transactions


# ---- Groq fraud analysis ---------------------------------------------------

def assess_transaction(api_key: str, txn: dict) -> str:
    """Send one transaction to Groq and return the plain-text assessment.

    The prompt asks for a JSON-ish response with ``risk_level`` and
    ``reason``, but we let the model answer in free text and extract
    what we need.
    """
    client = Groq(api_key=api_key)

    prompt = f"""You are a fraud-detection analyst. Evaluate this credit-card transaction:

Transaction ID: {txn['txn_id']}
Cardholder: {txn['cardholder']}
Amount: ${txn['amount']:.2f}
Timestamp (UTC): {txn['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Merchant: {txn['merchant']}
Category: {txn['category']}
Location: {txn['location']}, {txn['location_country']}
Cardholder's home city: {txn['cardholder_home']}

Respond in exactly this format (no extra text):

Risk Level: LOW | MEDIUM | HIGH
Reason: <one or two sentences explaining your reasoning>"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
    )
    return resp.choices[0].message.content or ""


def parse_assessment(text: str) -> tuple[str, str]:
    """Extract ``(risk_level, reason)`` from the model's response."""
    lines = text.strip().split("\n")
    risk = "UNKNOWN"
    reason_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("RISK LEVEL:"):
            candidate = stripped.split(":", 1)[1].strip().upper()
            if candidate in ("LOW", "MEDIUM", "HIGH"):
                risk = candidate
        elif stripped.upper().startswith("REASON:"):
            reason_lines.append(stripped.split(":", 1)[1].strip())
        else:
            reason_lines.append(stripped)
    reason = " ".join(reason_lines) if reason_lines else text
    return risk, reason


# ---- main ------------------------------------------------------------------

def main():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        return

    # Step 1: Generate 10 fake credit-card transactions, some suspicious.
    transactions = generate_transactions()
    print("Generated 10 transactions for analysis.\n")

    # Step 2 + 3: For each transaction, ask Groq to assess fraud risk,
    # then print the result.
    for idx, txn in enumerate(transactions, 1):
        _print_separator("-")
        print(f"Transaction {idx}/{len(transactions)}")
        print(f"  ID:       {txn['txn_id']}")
        print(f"  Amount:   ${txn['amount']:.2f}")
        print(f"  Time:     {txn['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Merchant: {txn['merchant']} ({txn['category']})")
        print(f"  Location: {txn['location']}, {txn['location_country']}")
        print(f"  Home:     {txn['cardholder_home']}")

        print("  --- Analyzing with Groq ... ", end="", flush=True)
        raw = assess_transaction(api_key, txn)
        risk, reason = parse_assessment(raw)
        print("done.")

        # Colour-code the risk level for visual clarity.
        ansi = {"LOW": "\033[92m", "MEDIUM": "\033[93m", "HIGH": "\033[91m"}.get(risk, "")
        reset = "\033[0m"
        print(f"  Risk Level: {ansi}{risk}{reset}")
        print(f"  Reason:     {reason}")
        print()

    _print_separator("=")
    print("Analysis complete.")


if __name__ == "__main__":
    main()
