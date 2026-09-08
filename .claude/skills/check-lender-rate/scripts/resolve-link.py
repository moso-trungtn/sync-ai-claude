#!/usr/bin/env python3
"""Resolve a moso quote share link into a reusable loan scenario.

Accepts a /l/<key> short link, a full .../quote_result?... URL, or a bare query
string. Prints three things:

  1. the scenario as a readable table
  2. a Quote JSON one-liner to paste into MosoPricingTools#testDebug (RunPricingOp)
  3. a QuoteServer builder to paste into an eligibility test (validations())

Usage:
  python3 resolve-link.py https://www.loanfactory.com/l/RsJfe5f981579d5
  python3 resolve-link.py --lender NexBank <url>      # adds alert_lenders to the JSON
  python3 resolve-link.py --json-only <url>
"""

import argparse
import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# URL param -> Quote field. Only names moso's EnumType/BooleanType accept.
# Booleans arrive as Yes/No, enums arrive as enum NAMES (EnumType._fromJson
# takes names, so no ordinal counting is needed).
# ---------------------------------------------------------------------------

BOOL_PARAMS = {
    "impounds", "use_lp", "waive_lender_fee", "finance_ufmip",
    "finance_uf_guarantee", "va_regular_military", "va_first_use",
    "va_funding", "va_disability_status", "w2_income_only", "low_income",
    "has_self_employed", "first_time_home_buyer", "is_compass_agent",
    "mi_paid_by_lender", "interest_only", "is_property_listed_for_sale",
}

NUM_PARAMS = {
    "loan_amount", "property_value", "credit_score", "debt_to_income",
    "number_of_borrowers", "financed_properties", "total_number_properties",
    "actual_number_of_units", "borrower_paid_compensation", "ami",
    "lock_period", "super_conf_limit", "second_loan_amount", "cash_out_amount",
    "non_qm_dscr", "non_qm_cash_reserved", "max_compensation",
}

# Params that are moso plumbing, not loan facts. `inviter` is kept out of the
# Quote JSON but reported separately: it is the LO to impersonate.
DROP_PARAMS = {"branch", "transaction_id", "utm_source", "utm_medium", "utm_campaign"}
JSON_EXCLUDE = {"inviter"}

# loan_program_group -> (amortization term, fixed period, is ARM)
TERMS = {
    "FIXED_40": (40, 40, False), "FIXED_30": (30, 30, False),
    "FIXED_25": (25, 25, False), "FIXED_20": (20, 20, False),
    "FIXED_15": (15, 15, False), "FIXED_10": (10, 10, False),
    "ARM_10": (30, 10, True), "ARM_7": (30, 7, True),
    "ARM_5": (30, 5, True), "ARM_3": (30, 3, True), "ARM_1": (30, 1, True),
}


def resolve(url: str) -> str:
    """Return the query string of the final quote_result URL."""
    if "?" in url and "/l/" not in url:
        return url.split("?", 1)[1]
    if "=" in url and "://" not in url:
        return url  # already a bare query string

    out = subprocess.run(
        ["curl", "-sI", "-m", "30", url],
        capture_output=True, text=True, check=False,
    ).stdout
    for line in out.splitlines():
        if line.lower().startswith("location:"):
            target = line.split(":", 1)[1].strip()
            if "?" not in target:
                sys.exit(f"redirect has no query string: {target}")
            print(f"# resolved -> {target.split('?')[0]}", file=sys.stderr)
            return target.split("?", 1)[1]
    sys.exit("no Location header; link may be dead or need auth")


def parse(qs: str) -> dict:
    raw = {k: v[0] for k, v in parse_qs(qs, keep_blank_values=False).items()}
    scenario = {}
    for key, val in raw.items():
        if key in DROP_PARAMS or val == "":
            continue
        if key in BOOL_PARAMS:
            scenario[key] = val.strip().lower() in ("yes", "true", "1")
        elif key in NUM_PARAMS:
            num = float(val)
            scenario[key] = int(num) if num.is_integer() else num
        else:
            scenario[key] = val
    return scenario


def derived(s: dict) -> dict:
    """Values the parser/validation code needs that the URL does not carry."""
    d = {}
    la, pv = s.get("loan_amount"), s.get("property_value")
    if la and pv:
        d["ltv_percent"] = round(la / pv * 100, 3)
        d["ltv_fraction"] = round(la / pv, 6)
    group = s.get("loan_program_group")
    if group in TERMS:
        d["term"], d["fixed_term"], d["arm"] = TERMS[group]
    d["is_du"] = not s.get("use_lp", False)
    d["impound"] = s.get("impounds", False)
    return d


def quote_json(s: dict, lender: str | None) -> str:
    q = {k: v for k, v in s.items() if k not in JSON_EXCLUDE}
    q.setdefault("kind", "Rate")
    q["get_all_rates"] = True
    if "loan_amount" in q:
        q.setdefault("total_loan_amount", q["loan_amount"])
    # alert_lenders is the ONLY field that restricts the run to one lender.
    q["alert_lenders"] = [lender] if lender else []
    return json.dumps(q, separators=(",", ":"))


def java_string_literal(payload: str) -> str:
    """Split the JSON into ~150-char Java string concat chunks."""
    esc = payload.replace("\\", "\\\\").replace('"', '\\"')
    chunks, size = [], 150
    while esc:
        cut = size
        # never split in the middle of an escape sequence
        while cut < len(esc) and esc[cut - 1] == "\\":
            cut += 1
        chunks.append(esc[:cut])
        esc = esc[cut:]
    body = '" +\n              "'.join(chunks)
    return f'JSON.parse("{body}");'


def quote_server(s: dict, d: dict) -> str:
    """QuoteServer builder for a local validations() check. ltv is a FRACTION."""
    lines = ["QuoteServer q = new QuoteServer();"]

    def add(expr, comment=None):
        lines.append(f"q.{expr};" + (f"   // {comment}" if comment else ""))

    if "category" in s:
        add(f"category = LoanCategory.{s['category']}")
    if "loan_type" in s:
        add(f"loanType = LoanType.{s['loan_type']}")
    if "credit_score" in s:
        add(f"fico = {s['credit_score']}")
    if "ltv_fraction" in d:
        add(f"ltv = {d['ltv_fraction']}d",
            f"{d['ltv_percent']}% - QuoteImpl.ltv is a FRACTION, not a percent")
        add(f"cltv = {d['ltv_fraction']}d")
    if "loan_amount" in s:
        add(f"loanAmount = {s['loan_amount']}")
    if "term" in d:
        add(f"term = {d['term']}")
        add(f"fixedTerm = {d['fixed_term']}")
        if d["arm"]:
            add("arm = true")
    if "purpose" in s:
        add(f"purpose = PurposeType.{s['purpose']}")
    if "occupancy" in s:
        add(f"occupancy = OccupancyType.{s['occupancy']}")
    if "property_type" in s:
        add(f"propertyType = PropertyType.{s['property_type']}")
    if "attachment_type" in s:
        add(f"attachmentType = AttachmentType.{s['attachment_type']}")
    if "actual_number_of_units" in s:
        add(f"unit = {s['actual_number_of_units']}")
    if "number_of_borrowers" in s:
        add(f"numberOfBorrowers = {s['number_of_borrowers']}")
    if "debt_to_income" in s:
        add(f"debtToIncome = {s['debt_to_income']}d")
    if "state" in s:
        add(f'state = "{s["state"]}"')
    add(f"isDU = {str(d['is_du']).lower()}")
    add(f"impound = {str(d['impound']).lower()}")
    if "financed_properties" in s:
        add(f"financedProperties = {s['financed_properties']}")
    if "total_number_properties" in s:
        add(f"totalNumberProperties = {s['total_number_properties']}")
    if "has_self_employed" in s:
        add(f"hasSelfEmployment = {str(s['has_self_employed']).lower()}")
    if "first_time_home_buyer" in s:
        add(f"firstTimeHomeBuyer = {str(s['first_time_home_buyer']).lower()}")
    if "low_income" in s:
        add(f"lowIncome = {str(s['low_income']).lower()}")
    if "income_to_ami" in s:
        add(f"incomeToAMI = IncomeToAMI.{s['income_to_ami']}")
    if "lock_period" in s:
        add(f"lockPeriod = {s['lock_period']}")
    if "loan_program_group" in s:
        add(f"loanProgramGroup = ProgramFilterGroup.{s['loan_program_group']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="/l/ link, quote_result URL, or bare query string")
    ap.add_argument("--lender", help="LenderType name to put in alert_lenders")
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args()

    s = parse(resolve(args.url))
    d = derived(s)
    payload = quote_json(s, args.lender)

    if args.json_only:
        print(payload)
        return

    print("=" * 78)
    print("SCENARIO")
    print("=" * 78)
    for key in sorted(s):
        print(f"  {key:28} {s[key]}")
    print("  " + "-" * 40)
    for key in sorted(d):
        print(f"  {key:28} {d[key]}   (derived)")

    print()
    print("=" * 78)
    print("1) Quote JSON  ->  MosoPricingTools#testDebug, RunPricingOp")
    print("=" * 78)
    print(java_string_literal(payload))
    print()
    lo_email = s.get("inviter", "<inviter email>")
    print("   NOTE: run as the LO or RunPricingOp keeps one row per lender per rate.")
    print("   Bean lo = new Bundle().readOnly().find(Admin.TYPE)")
    print(f'           .whereEquals(Admin.email, "{lo_email}").first();')
    print("   ThreadContext.setRequestUser(new AppServer().createSessionUser(lo));")

    print()
    print("=" * 78)
    print("2) QuoteServer  ->  local eligibility check against validations()")
    print("=" * 78)
    print(quote_server(s, d))


if __name__ == "__main__":
    main()
