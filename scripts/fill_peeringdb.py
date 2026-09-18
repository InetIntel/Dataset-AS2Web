#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_peeringdb.py

Some ASNs in this dataset carry the placeholder URL "[Need PeeringDB Data]"
instead of a real website (see `strip_peeringdb.py` for why). This script
fills those placeholders back in using a CAIDA PeeringDB Dataset snapshot
that YOU provide, so nothing from CAIDA/PeeringDB is ever redistributed by
this project.

CAIDA maintains a public archive of historical, dated PeeringDB snapshots,
unlike IPinfo, which only serves its current data. So the best way to match
a given AS2Web snapshot month is to select a CAIDA snapshot dated close to
the data originally used for that AS2Web snapshot.

Two ways to provide the data:
    Method 1 -- point at a CAIDA PeeringDB snapshot you already downloaded
        (--caida-json). Browse https://publicdata.caida.org/datasets/peeringdb/
        for the year/month you want; files are named
        peeringdb_2_dump_YYYY_MM_DD.json. This is the recommended method,
        since it lets you closely match the AS2Web snapshot's month (or as
        closely as CAIDA's daily archive allows).
    Method 2 -- let this script download a dated snapshot directly from
        CAIDA's public archive for you (--date YYYY-MM-DD). Equivalent to
        Method 1 but saves you the manual download step. Files are ~100+MB.
        By default the download goes to a temporary location that is
        deleted once the run finishes, so nothing is cached in your working
        directory; pass --cache-json PATH if you deliberately want to reuse
        the same download across multiple runs instead of re-fetching it
        each time.

Either way, use of the CAIDA dataset is subject to the CAIDA Acceptable Use
Agreement (Public-AUA) -- see the license notice displayed by the script
before processing begins.

The output records how the fill was done in metadata.peeringdb_enrichment
(source, snapshot_date, input_type, and when it was retrieved), so a filled
file's provenance doesn't get confused with the original snapshot's.

Usage:
    # Method 1: use a CAIDA snapshot you already downloaded
    python3 fill_peeringdb.py --input PUBLIC.json --output FILLED.json \\
        --caida-json peeringdb_2_dump_2026_09_13.json

    # Method 2: let the script download a dated snapshot for you
    python3 fill_peeringdb.py --input PUBLIC.json --output FILLED.json \\
        --date 2026-09-13
"""

import argparse
import datetime
import gzip
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

PLACEHOLDER = "[Need PeeringDB Data]"
PEERINGDB_SOURCE = "PeeringDB"
DOWNLOAD_URL_TMPL = (
    "https://publicdata.caida.org/datasets/peeringdb/{yyyy}/{mm}/"
    "peeringdb_2_dump_{yyyy}_{mm}_{dd}.json"
)
FILENAME_DATE_RE = re.compile(r"peeringdb_2_dump_(\d{4})_(\d{2})_(\d{2})")

NOTICE_RULE = "=" * 79

LICENSE_NOTICE = f"""\
{NOTICE_RULE}
CAIDA PeeringDB Dataset Notice
{NOTICE_RULE}

This script uses a CAIDA PeeringDB Dataset snapshot that you provide, or
that it downloads on your behalf, from CAIDA's public archive at:

https://publicdata.caida.org/datasets/peeringdb/

Before accessing the CAIDA PeeringDB dataset for the first time, please
visit the dataset page and follow its Data Access link to submit CAIDA's
user-information form:

https://www.caida.org/catalog/datasets/request_user_info_forms/peeringdb/

If you already obtained the CAIDA snapshot you plan to use, you may proceed
to the notice below.

Use of the CAIDA dataset is subject to the CAIDA Acceptable Use Agreement
for Publicly Accessible Datasets (Public-AUA):

https://www.caida.org/about/legal/aua/public_aua/

Dataset catalog page:
https://www.caida.org/catalog/datasets/peeringdb/

If you create a publication using this dataset, CAIDA requires you to cite
the dataset and report the publication to CAIDA. CAIDA's suggested citation
form is:

    The CAIDA UCSD PeeringDB Dataset, <date range used>
    https://www.caida.org/catalog/datasets/peeringdb/

This project does not redistribute the CAIDA PeeringDB snapshot. You are
responsible for obtaining the data separately (yourself, or via this
script's --date download option, which fetches it from CAIDA's own public
archive) and complying with the applicable CAIDA terms.

Filling these placeholders does not replace the license that applies to
AS2Web itself:

https://github.com/InetIntel/Dataset-AS2Web/blob/main/LICENSE

The original AS2Web content remains subject to the AS2Web repository's
license, while
any CAIDA PeeringDB data or derived material included through this script
remains subject to the applicable CAIDA Public-AUA terms.

{NOTICE_RULE}"""


def show_license_notice(auto_yes):
    # Blank lines + rule-delimited box so the notice stands out from whatever
    # was already on screen and from the [fill_peeringdb] log lines that
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
        print("\nNot acknowledged; exiting without contacting CAIDA or writing any output.")
        sys.exit(1)
    print()


def download_json(date_str, dest):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    url = DOWNLOAD_URL_TMPL.format(yyyy=dt.strftime("%Y"), mm=dt.strftime("%m"), dd=dt.strftime("%d"))
    print(f"[fill_peeringdb] downloading {url}")
    print("[fill_peeringdb] this is a full CAIDA PeeringDB snapshot (~100+MB); this may take a while ...")
    urllib.request.urlretrieve(url, dest)
    return dest


def open_maybe_gzip(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "rt", encoding="utf-8")


def guess_snapshot_date(path):
    """Best-effort YYYY-MM-DD from a peeringdb_2_dump_YYYY_MM_DD.json(.gz) filename."""
    m = FILENAME_DATE_RE.search(os.path.basename(path))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def build_asn2website(json_path):
    """Read a CAIDA/PeeringDB API-format JSON dump and return {asn_str: website}.

    The expected top-level shape (CAIDA's `peeringdb_2_dump_*.json` files, and
    PeeringDB's own API dumps) is:
        {"net": {"data": [{"asn": 12345, "website": "https://...", ...}, ...]}, ...}
    A couple of narrower shapes are also accepted as a fallback, in case a
    user passes a single-endpoint `net` dump rather than a full API dump:
        {"data": [{"asn": ..., "website": ...}, ...]}
        [{"asn": ..., "website": ...}, ...]

    Every net record's ASN is included in the returned mapping, even when its
    `website` field is empty, so callers can distinguish "no net record for
    this ASN in this snapshot" from "PeeringDB has no website on file for it".
    """
    with open_maybe_gzip(json_path) as f:
        doc = json.load(f)

    if isinstance(doc, dict) and "net" in doc and isinstance(doc["net"], dict):
        records = doc["net"].get("data", [])
    elif isinstance(doc, dict) and "data" in doc:
        records = doc["data"]
    elif isinstance(doc, list):
        records = doc
    else:
        raise SystemExit(
            f"[fill_peeringdb] unrecognized JSON shape in {json_path}: expected a CAIDA/"
            f"PeeringDB API dump with a top-level 'net' endpoint (or a bare 'net' records list)"
        )

    asn2website = {}
    for rec in records:
        asn = rec.get("asn")
        if asn is None:
            continue
        asn2website[str(asn)] = (rec.get("website") or "").strip()
    return asn2website


def fill_placeholders(data, asn2website):
    filled = 0
    missing_no_entry = 0
    missing_no_website = 0
    for asn, rec in data.items():
        if rec.get("url") != PLACEHOLDER:
            continue
        if PEERINGDB_SOURCE not in rec.get("sources", []):
            continue
        if asn not in asn2website:
            missing_no_entry += 1
            continue
        website = asn2website[asn]
        if not website:
            missing_no_website += 1
            continue
        rec["url"] = website
        filled += 1
    return filled, missing_no_entry, missing_no_website


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
        "--caida-json",
        help="Method 1 (recommended): path to a CAIDA PeeringDB dump you already downloaded "
        "(peeringdb_2_dump_YYYY_MM_DD.json, .gz or not) from "
        "https://publicdata.caida.org/datasets/peeringdb/ -- pick the date closest to the "
        "target AS2Web snapshot month.",
    )
    ap.add_argument(
        "--date",
        help="Method 2: date (YYYY-MM-DD) of the CAIDA daily snapshot to download directly "
        "from CAIDA's public archive, in place of --caida-json.",
    )
    ap.add_argument(
        "--cache-json",
        help="Optional: save the file downloaded via --date at this path and reuse it on "
        "later runs instead of re-downloading (delete the file yourself to force a fresh "
        "download). Without this flag, the download (~100+MB) goes to a temporary location "
        "that is deleted once this run finishes -- nothing is left in your working "
        "directory. If you expect to fill multiple AS2Web snapshots from the same CAIDA "
        "date, either pass this flag or download once yourself and reuse it via "
        "--caida-json (Method 1) instead of re-downloading per run.",
    )
    ap.add_argument(
        "--snapshot-date",
        help="Optional: override/confirm the date (YYYY-MM-DD) of the CAIDA snapshot you're "
        "supplying via --caida-json, for provenance in metadata.peeringdb_enrichment. If "
        "omitted, it is parsed from the filename when possible.",
    )
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Acknowledge the CAIDA PeeringDB Dataset notice non-interactively (still your "
        "responsibility to read and comply with the CAIDA Public-AUA). Without this flag the "
        "script prints the notice and waits for Enter.",
    )
    args = ap.parse_args()

    used_default_output = args.output is None
    output_path = Path(args.output) if args.output else _default_output_path(args.input)

    if bool(args.caida_json) == bool(args.date):
        ap.error(
            "pass exactly one of --caida-json (Method 1: a snapshot you already have) or "
            "--date (Method 2: download that date directly from CAIDA)"
        )

    show_license_notice(args.yes)

    tmp_dir = None
    if args.date:
        input_type = "direct_download"
        if args.cache_json:
            # Explicit opt-in: persist/reuse the download at this path across runs.
            if os.path.exists(args.cache_json):
                print(f"[fill_peeringdb] reusing cached {args.cache_json} (delete it to force a re-download)")
            else:
                download_json(args.date, args.cache_json)
            json_path = args.cache_json
        else:
            # No persistent cache requested: download to a throwaway temp
            # directory that is removed in the `finally` block below, so
            # nothing lingers in the working directory. If you're filling
            # several AS2Web snapshots from the same CAIDA date, pass
            # --cache-json (or use --caida-json with a file you keep
            # yourself) instead of re-downloading ~100+MB each run.
            tmp_dir = tempfile.TemporaryDirectory(prefix="fill_peeringdb_")
            json_path = os.path.join(tmp_dir.name, f"peeringdb_2_dump_{args.date.replace('-', '_')}.json")
            download_json(args.date, json_path)
        snapshot_date = args.date
    else:
        input_type = "user_provided_caida_snapshot"
        json_path = args.caida_json
        snapshot_date = args.snapshot_date or guess_snapshot_date(json_path)
        if not snapshot_date:
            print(
                "[fill_peeringdb] warning: could not determine the snapshot date from the "
                "filename; pass --snapshot-date to record it in metadata.peeringdb_enrichment"
            )

    try:
        asn2website = build_asn2website(json_path)
        print(f"[fill_peeringdb] loaded {len(asn2website)} ASN -> website entries from {json_path}")

        snapshot = _load_reconstruction_base(args.input, output_path, used_default_output, "fill_peeringdb")

        placeholders_before = sum(
            1 for rec in snapshot["data"].values() if rec.get("url") == PLACEHOLDER
        )
        filled, missing_no_entry, missing_no_website = fill_placeholders(snapshot["data"], asn2website)

        enrichment = {
            "performed": True,
            "source": "CAIDA UCSD PeeringDB Dataset",
            "snapshot_date": snapshot_date,
            "input_type": input_type,
            "retrieved_at": datetime.date.today().isoformat(),
            "license": "CAIDA Public-AUA",
        }
        snapshot.setdefault("metadata", {})["peeringdb_enrichment"] = enrichment

        _write_json_atomic(snapshot, output_path)

        print(f"[fill_peeringdb] {args.input} -> {output_path}")
        print(f"[fill_peeringdb] placeholders found:                 {placeholders_before}")
        print(f"[fill_peeringdb] filled from provided CAIDA data:    {filled}")
        print(f"[fill_peeringdb] still missing (ASN not in snapshot): {missing_no_entry}")
        print(f"[fill_peeringdb] still missing (no website on file): {missing_no_website}")
        print(f"[fill_peeringdb] recorded metadata.peeringdb_enrichment: {enrichment}")
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


if __name__ == "__main__":
    main()
