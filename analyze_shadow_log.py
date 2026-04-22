"""
analyze_shadow_log.py — Parse batch run logs to identify Agent vs Hybrid
disagreement patterns from shadow-run output.

Usage:
    python analyze_shadow_log.py <path-to-log-file>

Reads the log produced by run_batch.py. Shadow lines have the format:
    🔬  Shadow: Agent=<N> | Hybrid=<N> | Delta=<+/-N>

HWID is inferred from the preceding context line:
    ➡️  HWID <N> | <StudentName> | <SectionName>

Read-only. Does not modify the log file or database.
"""

import re
import sys
from collections import defaultdict


# ------------------------------------------------------------
# Patterns
# ------------------------------------------------------------
# Matches:  ➡️  HWID 12345 | ...
RE_HWID   = re.compile(r"HWID\s+(\d+)")

# Matches:  🔬  Shadow: Agent=4 | Hybrid=3 | Delta=-1
RE_SHADOW = re.compile(
    r"Shadow:\s+Agent=(\d+)\s*\|?\s*Hybrid=(\d+)\s*\|?\s*Delta=([+-]?\d+)"
)


# ------------------------------------------------------------
# Parsing
# ------------------------------------------------------------
def parse_log(path: str) -> list[dict]:
    """
    Scan the log file line by line.
    Track the most-recently-seen HWID and pair it with each shadow line.
    Returns a list of dicts: hwid, agent_grade, hybrid_grade, delta.
    """
    records = []
    current_hwid = None

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                hwid_match = RE_HWID.search(line)
                if hwid_match:
                    current_hwid = int(hwid_match.group(1))

                shadow_match = RE_SHADOW.search(line)
                if shadow_match:
                    agent_grade  = int(shadow_match.group(1))
                    hybrid_grade = int(shadow_match.group(2))
                    delta        = int(shadow_match.group(3))
                    records.append({
                        "hwid":         current_hwid,
                        "agent_grade":  agent_grade,
                        "hybrid_grade": hybrid_grade,
                        "delta":        delta,
                    })

    except FileNotFoundError:
        print(f"Error: file not found — {path}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    return records


# ------------------------------------------------------------
# Grouping
# ------------------------------------------------------------
def group_by_delta(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by |delta| bucket: 0, 1, 2, 3+."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        mag = abs(r["delta"])
        if mag == 0:
            key = "|delta|=0"
        elif mag == 1:
            key = "|delta|=1"
        elif mag == 2:
            key = "|delta|=2"
        else:
            key = "|delta|>=3"
        groups[key].append(r)
    return groups


# ------------------------------------------------------------
# Reporting
# ------------------------------------------------------------
BUCKET_ORDER = ["|delta|=0", "|delta|=1", "|delta|=2", "|delta|>=3"]


def format_hwids(records: list[dict], max_samples: int = 5) -> str:
    seen = []
    for r in records:
        hwid = r["hwid"]
        label = str(hwid) if hwid is not None else "unknown"
        if label not in seen:
            seen.append(label)
        if len(seen) == max_samples:
            break
    remainder = len(records) - len(seen)
    suffix = f" … (+{remainder} more)" if remainder > 0 else ""
    return ", ".join(seen) + suffix


def print_report(records: list[dict], groups: dict[str, list[dict]]) -> None:
    total = len(records)

    if total == 0:
        print("No shadow-run lines found in log.")
        return

    def pct(n: int) -> str:
        return f"{n / total * 100:.1f}%"

    agreement_count = len(groups.get("|delta|=0", [])) + len(groups.get("|delta|=1", []))
    agreement_rate  = f"{agreement_count / total * 100:.1f}%"

    print()
    print("═" * 64)
    print("AGENT vs HYBRID SHADOW DISAGREEMENT REPORT")
    print(f"Agreement rate (|delta|<=1): {agreement_rate}  "
          f"({agreement_count}/{total} submissions)")
    print("═" * 64)

    for key in BUCKET_ORDER:
        bucket = groups.get(key, [])
        count  = len(bucket)
        if count == 0:
            print(f"\n{key:12}  {count:4}  ({pct(count)})  —")
        else:
            sample = format_hwids(bucket)
            print(f"\n{key:12}  {count:4}  ({pct(count)})")
            print(f"             Sample HWIDs: {sample}")

    print()
    print("─" * 64)
    print(f"Total shadow lines parsed: {total}")

    # Direction breakdown (agent higher vs hybrid higher)
    agent_higher  = sum(1 for r in records if r["delta"] > 0)
    hybrid_higher = sum(1 for r in records if r["delta"] < 0)
    tied          = sum(1 for r in records if r["delta"] == 0)
    print(f"Agent higher: {agent_higher} | Hybrid higher: {hybrid_higher} | Tied: {tied}")
    print("═" * 64)


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_shadow_log.py <path-to-log-file>", file=sys.stderr)
        sys.exit(1)

    log_path = sys.argv[1]
    records  = parse_log(log_path)
    groups   = group_by_delta(records)
    print_report(records, groups)


if __name__ == "__main__":
    main()
