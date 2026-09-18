# Reconstruction scripts

`fill_ipinfo_lite.py` and `fill_peeringdb.py` fill in the `"[Need IPinfoLite Data]"` and `"[Need PeeringDB Data]"` placeholders in the public AS2Web snapshots. See the main [README](../README.md#filling-third-party-data-placeholders) for the public AS2Web placeholder structure, upstream data sources, and applicable license or acceptable-use terms. This file documents the scripts' command-line behavior.

## Local reconstruction behavior

By default, reconstructed snapshots are written under `filled_data/YYYY-MM/`, mirroring the public `data/YYYY-MM/` layout. `filled_data/` is intended for local generated output and should be listed in `.gitignore`; do not include filled snapshots in the public repository.

Both reconstruction scripts use the same default output path. If a locally filled snapshot already exists there, either script continues from that file rather than starting again from the public snapshot in `data/`. This means IPinfo and PeeringDB placeholders can be filled in either order, re-running the same filler does not undo previous reconstruction steps, and enrichment metadata from earlier reconstruction steps is preserved rather than overwritten.

This continuation behavior only applies to the default output path. If you pass `--output` explicitly, the script always reads `--input` and writes `--output` exactly as given, never treating an existing `--output` as something to continue from. To discard previous local reconstruction progress and start over, delete the corresponding file under `filled_data/`.

## IPinfo Lite (`fill_ipinfo_lite.py`)

### Fill from IPinfo's current snapshot

```bash
# 1. Sign up at https://ipinfo.io and get an API token.
# 2. Put it in an environment variable so it does not end up in shell history.
export IPINFO_TOKEN=your_token_here

# 3. Run the filler, one AS2Web snapshot at a time.
python3 scripts/fill_ipinfo_lite.py \
    --input data/2026-09/as2web.2026-09.json
```

`--token YOUR_IPINFO_TOKEN` also works as an explicit override.

By default, the downloaded CSV is written to a temporary location that is deleted once the run finishes — nothing is left in your working directory, and each run reflects IPinfo's current data. Pass `--cache-csv PATH` if you deliberately want to reuse the same download across multiple runs (e.g. filling several AS2Web snapshots without re-fetching each time); it then persists at that path until you delete it yourself.

### Fill from an IPinfo snapshot you already have

The script accepts current IPinfo Lite CSVs as well as the older `start_ip`/`end_ip` ASN-dump schema, compressed or uncompressed:

```bash
python3 scripts/fill_ipinfo_lite.py \
    --input data/2026-09/as2web.2026-09.json \
    --csv path/to/your_ipinfo_snapshot.csv.gz \
    --ipinfo-snapshot-date 2026-09
```

`--ipinfo-snapshot-date` is optional and informational. It is recorded in `metadata.ipinfo_lite_enrichment` together with information such as the input type, retrieval time, and license, so a locally filled output can be distinguished from the original public snapshot.

The script prints an IPinfo Lite license notice and waits for acknowledgement before processing. If you publish or redistribute material produced using IPinfo Lite data, you are responsible for complying with the applicable CC BY-SA 4.0 terms, including attribution and, where applicable, ShareAlike requirements.

### Historical reproducibility

IPinfo's download endpoint serves its current, daily-refreshed data rather than a user-selected historical snapshot. A placeholder filled from the current download therefore reflects current IPinfo Lite data and may differ from the data used when the AS2Web snapshot was generated. If you have an archived IPinfo Lite snapshot from the relevant period, supplying it directly can provide a closer historical approximation. Exact reconstruction requires the same upstream IPinfo snapshot originally used by the AS2Web pipeline, which is not redistributed as part of this public artifact. The date originally used is recorded in `metadata.ipinfo_lite_snapshot_date`.

## CAIDA PeeringDB (`fill_peeringdb.py`)

Before accessing the CAIDA PeeringDB dataset for the first time, follow the
Data Access instructions on the CAIDA PeeringDB dataset page and submit
the user-information form. Use of the dataset is subject to the CAIDA
Public-AUA.

### Fill from a CAIDA snapshot you already downloaded

```bash
python3 scripts/fill_peeringdb.py \
    --input data/2026-09/as2web.2026-09.json \
    --caida-json path/to/peeringdb_2_dump_2026_09_01.json
```

### Download a dated CAIDA snapshot with the script

```bash
python3 scripts/fill_peeringdb.py \
    --input data/2026-09/as2web.2026-09.json \
    --date 2026-09-01
```

By default, a `--date` download (~100+MB) is written to a temporary location that is deleted once the run finishes. Pass `--cache-json PATH` if you deliberately want to reuse the same download across multiple runs. If you expect to fill several AS2Web snapshots from the same CAIDA date, using `--caida-json` with a file you download and keep yourself avoids repeated large downloads entirely.

In either mode, the script displays the CAIDA PeeringDB Dataset notice and waits for acknowledgement before contacting CAIDA or reading the supplied data. If you create a publication using the CAIDA dataset, the Public-AUA requires you to cite the dataset and report the publication to CAIDA.

Running the script adds a `metadata.peeringdb_enrichment` object to the locally filled output, recording information such as the source, snapshot date, input type, and retrieval time.

### Historical reproducibility

CAIDA maintains an archive of historical, dated PeeringDB snapshots. The date of the PeeringDB data originally used by the AS2Web pipeline is recorded in `metadata.peeringdb_snapshot_date`. Using a CAIDA snapshot from the recorded date provides the closest available historical reconstruction. Exact reconstruction requires the same upstream snapshot originally used by the pipeline.
