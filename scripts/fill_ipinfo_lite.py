#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_ipinfo_lite.py

Some ASNs in this dataset carry the placeholder URL "[Need IPinfoLite Data]"
instead of a real website (see README for why). If you have your own IPinfo
account, this script fills those placeholders back in using IPinfo Lite data
that YOU provide, so nothing from IPinfo is ever redistributed by this
project.

IPinfo Lite is released under CC BY-SA 4.0. If you use this script with
IPinfo Lite data, you are responsible for complying with IPinfo's applicable
licensing and attribution requirements. See the license notice displayed by
the script before processing begins.

Two ways to provide the data:
    Method 1 -- download IPinfo's current snapshot (--token). IPinfo's
        download endpoints always serve their current, daily-refreshed data;
        there is no way to request a historical dated snapshot. So this
        reflects today's IPinfo Lite data, which may not exactly match what
        IPinfo reported as of the dataset snapshot's month.
    Method 2 -- point at your own archived IPinfo snapshot (--csv). If you
        already keep your own dated IPinfo pulls, pass the one closest to
        the target snapshot's month for a closer match than Method 1. Both
        the current CSV schema (network,...,asn,as_name,as_domain) and the
        older start_ip/end_ip ASN-dump schema (start_ip,end_ip,asn,name,
        domain) are auto-detected and accepted, gzip or not.

Getting the data (Method 1):
    1. Sign up at https://ipinfo.io and get an API token.
    2. Either let this script download it for you (--token, or the
       IPINFO_TOKEN env var so the token doesn't end up in your shell
       history), or fetch it yourself and pass --csv:
           curl -L "https://ipinfo.io/data/ipinfo_lite.csv.gz?token=$TOKEN" \
               -o ipinfo_lite.csv.gz
    By default, a --token/$IPINFO_TOKEN download goes to a temporary
    location that is deleted once the run finishes -- nothing is cached in
    your working directory. Pass --cache-csv PATH if you deliberately want
    to reuse the same download across multiple runs (e.g. filling several
    AS2Web snapshots without re-fetching each time); it then persists at
    that path until you delete it yourself.

The output records how the fill was done in metadata.ipinfo_lite_enrichment
(input_type, when it was retrieved, and -- if you pass
--ipinfo-snapshot-date -- the date/month of the snapshot you supplied), so a
filled file's provenance doesn't get confused with the original snapshot's.

Usage:
    # Method 1: let the script download the current snapshot
    export IPINFO_TOKEN=your_token_here
    python3 fill_ipinfo_lite.py --input data/2026-09/as2web.2026-09.json
    # Method 2: use a snapshot (current or archived) you already have
    python3 fill_ipinfo_lite.py --input data/2026-09/as2web.2026-09.json \
        --csv your_archived_ipinfo_snapshot.csv.gz \
        --ipinfo-snapshot-date 2026-09
"""

import argparse
import csv
import datetime
import gzip
import json
import os
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path
import re

PLACEHOLDER = "[Need IPinfoLite Data]"
IPINFO_SOURCE = "IPinfo"
DOWNLOAD_URL = "https://ipinfo.io/data/ipinfo_lite.csv.gz?token={token}"

NOTICE_RULE = "=" * 79

LICENSE_NOTICE = f"""\
{NOTICE_RULE}
IPinfo Lite License Notice
{NOTICE_RULE}

This script uses data that you provide from IPinfo Lite.

The script can either download the current IPinfo Lite data for you or use
a compatible IPinfo Lite snapshot that you provide locally. If current
IPinfo Lite data is used to fill an older AS2Web snapshot, the resulting
mappings may differ from those originally generated for that snapshot. If
you have an archived IPinfo Lite snapshot from the relevant period, you may
provide it instead for a closer historical reconstruction.

Historical IPinfo Lite snapshots are not redistributed with this artifact.

IPinfo Lite data is made available under the Creative Commons
Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) license:

https://creativecommons.org/licenses/by-sa/4.0/

IPinfo:
https://ipinfo.io/

By using IPinfo Lite data, you are responsible for complying with the
applicable license terms.

In particular:

* You must provide appropriate attribution to IPinfo when required.
* If you share material that constitutes an adaptation of IPinfo Lite data,
    you must comply with the ShareAlike requirements of CC BY-SA 4.0.
* You must not impose legal terms or technological restrictions that prevent
    others from exercising rights granted by the CC BY-SA 4.0 license.

You should review the CC BY-SA 4.0 license and IPinfo's current licensing and
attribution requirements before redistributing data or derived datasets.

This project does not redistribute IPinfo Lite data. The IPinfo data used by
this script is obtained separately by you and processed locally.

Filling these placeholders does not replace the license that applies to
AS2Web itself:

https://github.com/InetIntel/Dataset-AS2Web/blob/main/LICENSE

The original AS2Web content remains subject to the AS2Web repository's
license, while any IPinfo Lite data or derived material included through
this script remains subject to the applicable CC BY-SA 4.0 terms.

{NOTICE_RULE}"""


def show_license_notice(auto_yes):
    # Blank lines + rule-delimited box so the notice stands out from whatever
    # was already on screen and from the [fill_ipinfo_lite] log lines that
    # follow once it's acknowledged.
    print()
    print(LICENSE_NOTICE)
    print()
    if auto_yes:
        print("(--yes passed: notice acknowledged non-interactively)")
        print()
        return
    try:
        input(">>> Press Enter to acknowledge this notice and continue, or Ctrl+C to exit. ")
    except (EOFError, KeyboardInterrupt):
        print("\nNot acknowledged; exiting without contacting IPinfo or writing any output.")
        sys.exit(1)
    print()

# Domains that carry no organizational identity (personal mailbox providers,
# registry contact addresses) -- mirrors the filter the internal pipeline
# applies, kept here so filled placeholders get the same treatment.
UNMEANINGFUL_DOMAINS = {
    "gmail.com", "yahoo.com", "me.com", "hotmail.com",
    "lacnic.net", "ripe.net", "apnic.net", "mhs.attmail.com",
}


def download_csv(token, dest):
    url = DOWNLOAD_URL.format(token=token)
    print(f"[fill_ipinfo_lite] downloading IPinfo Lite CSV to {dest} ...")
    urllib.request.urlretrieve(url, dest)
    return dest


def open_maybe_gzip(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return open(path, "rt", encoding="utf-8", newline="")


def build_asn2domain(csv_path):
    """Read an IPinfo ASN/domain CSV and return {asn_without_prefix: domain}.

    Two schemas are auto-detected from the header:
      - current IPinfo Lite: network,country,country_code,continent,
        continent_code,asn,as_name,as_domain -- each ASN maps to exactly one
        as_domain value across all of its network rows (no per-range
        disagreement to resolve).
      - older start_ip/end_ip ASN dump: start_ip,end_ip,asn,name,domain --
        an ASN can appear once per IP range with disagreeing domain values,
        so the most frequently listed (mode) domain is used.
    """
    with open_maybe_gzip(csv_path) as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        if "as_domain" in fieldnames:
            print("[fill_ipinfo_lite] detected schema: IPinfo Lite (network/as_domain)")
            asn2domain = {}
            for row in reader:
                asn = row.get("asn", "").strip()
                domain = row.get("as_domain", "").strip()
                if asn and domain:
                    asn2domain[asn[2:]] = domain  # "AS13335" -> "13335"
            return asn2domain
        elif "domain" in fieldnames and "start_ip" in fieldnames:
            print("[fill_ipinfo_lite] detected schema: legacy start_ip/end_ip ASN dump")
            domain_counts = {}
            for row in reader:
                asn = row.get("asn", "").strip()
                domain = row.get("domain", "").strip()
                if not asn:
                    continue
                c = domain_counts.setdefault(asn, Counter())
                if domain:
                    c[domain] += 1
            return {
                asn[2:]: c.most_common(1)[0][0]
                for asn, c in domain_counts.items()
                if c
            }
        else:
            raise SystemExit(
                f"[fill_ipinfo_lite] unrecognized CSV columns in {csv_path}: "
                f"{sorted(fieldnames)}"
            )


def fill_placeholders(data, asn2domain):
    filled = 0
    missing_no_csv_entry = 0
    missing_unmeaningful = 0
    for asn, rec in data.items():
        if rec.get("url") != PLACEHOLDER:
            continue
        if IPINFO_SOURCE not in rec.get("sources", []):
            continue
        domain = asn2domain.get(asn)
        if not domain:
            missing_no_csv_entry += 1
            continue
        if domain in UNMEANINGFUL_DOMAINS:
            missing_unmeaningful += 1
            continue
        rec["url"] = f"https://{domain}/"
        filled += 1
    return filled, missing_no_csv_entry, missing_unmeaningful


def _default_output_path(input_path: str) -> Path:
    """Mirror data/YYYY-MM/... into filled_data/YYYY-MM/....

    For other input locations, use filled_data/<parent>/<filename> when the
    parent looks like YYYY-MM, otherwise filled_data/<filename>.
    """
    src = Path(input_path)
    parts = list(src.parts)

    if "data" in parts:
        idx = len(parts) - 1 - parts[::-1].index("data")
        rel = Path(*parts[idx + 1:])
        return Path("filled_data") / rel

    if "filled_data" in parts:
        idx = len(parts) - 1 - parts[::-1].index("filled_data")
        rel = Path(*parts[idx + 1:])
        return Path("filled_data") / rel

    if re.fullmatch(r"\d{4}-\d{2}", src.parent.name):
        return Path("filled_data") / src.parent.name / src.name
    return Path("filled_data") / src.name


def _write_json_atomic(payload: dict, output_path: Path) -> None:
    """Write JSON safely, including when input and output are the same path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_name(output_path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, output_path)


def _load_reconstruction_base(input_path, output_path, used_default_output, tag):
    """Return the snapshot to fill placeholders in.

    When writing to the default filled_data/... path and a local
    reconstruction already exists there, continue from it instead of
    starting over from the public snapshot -- so IPinfo and PeeringDB fills
    compose regardless of which order they're run in, and re-running the
    same filler after its placeholders are already gone is a no-op rather
    than something that could undo the other filler's work. An explicit
    --output is always treated as a plain destination, never as a base to
    continue from, so it behaves exactly as written: read --input, write
    --output.
    """
    with open(input_path, encoding="utf-8") as f:
        input_snapshot = json.load(f)

    if not used_default_output or not output_path.exists():
        return input_snapshot

    with open(output_path, encoding="utf-8") as f:
        existing = json.load(f)

    existing_month = existing.get("metadata", {}).get("snapshot_month")
    input_month = input_snapshot.get("metadata", {}).get("snapshot_month")
    if existing_month is not None and input_month is not None and existing_month != input_month:
        raise SystemExit(
            f"[{tag}] refusing to continue: {output_path} already exists but is for "
            f"snapshot_month={existing_month!r}, not {input_month!r} (from {input_path}). Pass "
            f"--output to write elsewhere, or remove {output_path} to start a fresh local "
            f"reconstruction from {input_path}."
        )

    print(f"[{tag}] continuing from existing local reconstruction at {output_path}")
    return existing


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", required=True, help="Public as2web.<snapshot>.json with placeholders")
    ap.add_argument(
        "--output",
        help=(
            "Path to write the filled-in version to. By default, the script mirrors "
            "data/YYYY-MM/... under filled_data/YYYY-MM/...."
        ),
    )
    ap.add_argument(
        "--csv",
        help="Method 2: path to an IPinfo ASN/domain CSV you already have (current or "
        "archived, .gz or not; schema is auto-detected). Use this instead of --token "
        "if you keep your own dated IPinfo snapshots and want one closer to the "
        "target month than IPinfo's current download.",
    )
    ap.add_argument(
        "--token",
        help="Method 1: your IPinfo API token; the script downloads IPinfo's current "
        "IPinfo Lite snapshot with it if --csv is not given. Defaults to the "
        "IPINFO_TOKEN environment variable if set, so the token need not appear in "
        "your shell history.",
    )
    ap.add_argument(
        "--cache-csv",
        help="Optional: save the CSV downloaded via --token/$IPINFO_TOKEN at this path and "
        "reuse it on later runs instead of re-downloading (delete the file yourself to force "
        "a fresh download). Without this flag, the download goes to a temporary location "
        "that is deleted once this run finishes, so nothing is left in your working "
        "directory -- and each run reflects IPinfo's current data rather than a possibly "
        "stale earlier download.",
    )
    ap.add_argument(
        "--ipinfo-snapshot-date",
        help="Optional: the date (or month) of the IPinfo snapshot you're supplying via "
        "--csv, e.g. 2026-09 or 2026-09-01. Recorded in the output's "
        "ipinfo_lite_enrichment metadata for provenance; purely informational, not "
        "verified against the CSV's actual contents.",
    )
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Acknowledge the IPinfo Lite license notice non-interactively (still your "
        "responsibility to comply with it). Without this flag the script prints the "
        "notice and waits for Enter.",
    )
    args = ap.parse_args()

    used_default_output = args.output is None
    output_path = Path(args.output) if args.output else _default_output_path(args.input)

    token = args.token or os.environ.get("IPINFO_TOKEN")
    if not args.csv and not token:
        ap.error(
            "pass either --csv (Method 2: a snapshot you already have) or --token / "
            "$IPINFO_TOKEN (Method 1: download the current one)"
        )
    if args.csv and args.token:
        ap.error("pass either --csv or --token, not both")

    show_license_notice(args.yes)

    csv_path = args.csv
    input_type = "user_provided_snapshot"
    tmp_dir = None
    if not csv_path:
        input_type = "current_download"
        if args.cache_csv:
            # Explicit opt-in: persist/reuse the download at this path across runs.
            if os.path.exists(args.cache_csv):
                print(f"[fill_ipinfo_lite] reusing cached {args.cache_csv} (delete it to force a re-download)")
            else:
                download_csv(token, args.cache_csv)
            csv_path = args.cache_csv
        else:
            # No persistent cache requested: download to a throwaway temp
            # directory that is removed in the `finally` block below, so
            # nothing lingers in the working directory (and each run gets
            # IPinfo's current data instead of silently reusing a stale copy).
            tmp_dir = tempfile.TemporaryDirectory(prefix="fill_ipinfo_lite_")
            csv_path = os.path.join(tmp_dir.name, "ipinfo_lite.csv.gz")
            download_csv(token, csv_path)

    try:
        asn2domain = build_asn2domain(csv_path)
        print(f"[fill_ipinfo_lite] loaded {len(asn2domain)} ASN -> domain entries from {csv_path}")

        snapshot = _load_reconstruction_base(args.input, output_path, used_default_output, "fill_ipinfo_lite")

        placeholders_before = sum(
            1 for rec in snapshot["data"].values() if rec.get("url") == PLACEHOLDER
        )
        filled, missing_no_entry, missing_unmeaningful = fill_placeholders(snapshot["data"], asn2domain)

        enrichment = {
            "performed": True,
            "source": "user-provided IPinfo Lite",
            "input_type": input_type,
            "retrieved_at": datetime.date.today().isoformat(),
            "license": "CC BY-SA 4.0",
        }
        if args.ipinfo_snapshot_date:
            enrichment["ipinfo_snapshot_date"] = args.ipinfo_snapshot_date
        snapshot.setdefault("metadata", {})["ipinfo_lite_enrichment"] = enrichment

        _write_json_atomic(snapshot, output_path)

        print(f"[fill_ipinfo_lite] {args.input} -> {output_path}")
        print(f"[fill_ipinfo_lite] placeholders found:            {placeholders_before}")
        print(f"[fill_ipinfo_lite] filled from provided IPinfo data: {filled}")
        print(f"[fill_ipinfo_lite] still missing (ASN not in CSV):  {missing_no_entry}")
        print(f"[fill_ipinfo_lite] still missing (unmeaningful domain): {missing_unmeaningful}")
        print(f"[fill_ipinfo_lite] recorded metadata.ipinfo_lite_enrichment: {enrichment}")
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


if __name__ == "__main__":
    main()
