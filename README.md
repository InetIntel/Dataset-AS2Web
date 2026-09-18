# AS2Web Dataset

AS2Web is an Autonomous System (AS) to website mapping dataset. It maps
ASes to the official websites of their operating organizations by
combining Internet registry and operational data sources with fallback
AI-based web search.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19645661.svg)](https://doi.org/10.5281/zenodo.19645661)

Please open an issue to report any inaccuracies in the dataset (include
ASN, month, and evidence).

This is the public release of AS2Web. Some URLs that depend on
separately licensed third-party sources are represented by placeholders.
See [Filling third-party-data
placeholders](#filling-third-party-data-placeholders) for details and
local reconstruction instructions.

## Related paper

The methodology behind this dataset is described in:

-   Z. Chen, Z. Bischof, C. Testart, A. Dainotti, "AS2Biz: Leveraging
    Web Presence and AI to Improve AS Business Classification,"
    *Proceedings of the 2026 ACM Internet Measurement Conference (IMC
    '26)*, 2026.
-   Paper link: https://doi.org/10.1145/3777912.3809155

## Dataset access

-   Latest snapshot: see the `data/` directory for monthly JSON
    snapshots.
-   File naming: `as2web.YYYY-MM.json`
-   Some URLs are replaced with third-party-data placeholders in the
    public release. See [Filling third-party-data
    placeholders](#filling-third-party-data-placeholders) for their
    meaning and instructions for local reconstruction.
-   Reconstruction scripts write locally filled snapshots under
    `filled_data/YYYY-MM/` by default, mirroring the layout under
    `data/`.

## Overview

For each snapshot month, the dataset stores: - metadata about the
snapshot and website-discovery setting used - a mapping from ASN to its
selected website URL - the provenance of each assigned URL

The JSON structure is:

``` json
{
  "metadata": {
    "snapshot_month": "{yyyy_mm}",
    "web_search_setting": "{model_or_setting}"
  },
  "data": {
    "AS1": {
      "url": "{url}",
      "sources": ["{source1}", "{source2}"]
    },
    "AS2": {
      "url": "{url}",
      "sources": ["{source3}"]
    }
  }
}
```

## Field description

### `metadata`

-   `snapshot_month`: snapshot month in `YYYY-MM` format, for example
    `2025-09`
-   `web_search_setting`: the model or search setting used for the
    AI-based web-search fallback stage
-   `ipinfo_lite_snapshot_date`: the date (`YYYY-MM-DD`) the IPinfo Lite
    data used by the AS-centered stage was pulled, when generating this
    AS2Web snapshot
-   `peeringdb_snapshot_date`: the date (`YYYY-MM-DD`) the PeeringDB
    data used by the AS-centered stage was pulled, when generating this
    AS2Web snapshot

Snapshots with expanded method accounting also include:

-   `total_ases`: the total number of ASNs in the snapshot
-   `ases_url_from_as_centered`: the number of URLs selected by the
    AS-centered stage
-   `ases_url_from_web_search`: the number of URLs obtained through new
    WebSearch queries for the current snapshot, excluding reused URLs
-   `ases_url_reused_from_prev`: the number of URLs reused from the
    preceding published AS2Web snapshot
-   `ases_url_from_fallback_imputation`: the number of URLs assigned
    through fallback imputation

The reconstruction scripts add their own enrichment metadata to locally
filled outputs; those fields are documented in [Filling third-party-data
placeholders](#filling-third-party-data-placeholders) and are not
present in the files under `data/`.

### `data`

`data` is a dictionary keyed by ASN string. Each ASN maps to a
dictionary with the following fields:

-   `url`: the selected official website URL of the organization
    operating the ASN, or a placeholder indicating that third-party data
    is required for local reconstruction
-   `sources`: the source or sources that provided evidence for this URL

Example:

``` json
{
  "data": {
    "12345": {
      "url": "https://www.example.com",
      "sources": ["Whois"]
    },
    "67890": {
      "url": "https://www.example.net",
      "sources": ["WebSearch"]
    },
    "13579": {
      "url": "[Need IPinfoLite Data]",
      "sources": ["IPinfo"]
    },
    "24680": {
      "url": "[Need PeeringDB Data]",
      "sources": ["PeeringDB"]
    }
  }
}
```

## Source values

The `sources` field indicates how the website is represented in the
public AS2Web snapshot:

-   `Whois`: the selected URL is available from Whois data. When Whois
    supports the selected URL, the public record uses `Whois` as its
    source.
-   `IPinfo`: the selected URL relies on IPinfo Lite rather than Whois.
    The URL is represented as `"[Need IPinfoLite Data]"` and can be
    reconstructed locally using IPinfo Lite.
-   `PeeringDB`: the selected URL relies on PeeringDB rather than Whois.
    The URL is represented as `"[Need PeeringDB Data]"` and can be
    reconstructed locally using CAIDA PeeringDB data.
-   `WebSearch`: the URL was identified through the AI-based web-search
    stage and is included directly in the public snapshot.

## Filling third-party-data placeholders

To reconstruct the complete AS2Web mappings locally, users should obtain
the required IPinfo Lite and CAIDA PeeringDB data in accordance with
their respective licenses, acceptable-use terms, and access
requirements. The provided reconstruction scripts can then fill the
corresponding placeholders using these locally obtained upstream data.

The reconstruction scripts do not redistribute the corresponding
third-party datasets. They operate on data obtained separately by the
user and display the applicable third-party notice before processing.

### IPinfo Lite

The AS2Web pipeline uses downloadable data from [IPinfo
Lite](https://ipinfo.io/lite), including the "IP to ASN (Free)" dump.
IPinfo Lite is released under [CC BY-SA
4.0](https://creativecommons.org/licenses/by-sa/4.0/). To avoid
redistributing IPinfo-derived data and to keep AS2Web's licensing terms
separate from those applicable to IPinfo Lite, we do not redistribute
IPinfo data or URLs derived solely from it.

ASNs for which IPinfo was the only supporting source have `url` set to
`"[Need IPinfoLite Data]"`, with `sources: ["IPinfo"]`.
`scripts/fill_ipinfo_lite.py` can reconstruct these URLs locally using
IPinfo Lite data that you obtain yourself. If you publish or
redistribute material produced using IPinfo Lite data, you are
responsible for complying with the applicable CC BY-SA 4.0 terms,
including attribution and, where applicable, ShareAlike requirements.

### CAIDA PeeringDB

The PeeringDB data used by the AS2Web pipeline is sourced from the
[CAIDA PeeringDB
archive](https://www.caida.org/catalog/datasets/peeringdb/), which CAIDA
distributes subject to the [CAIDA Acceptable Use Agreement for Publicly
Accessible Datasets
(Public-AUA)](https://www.caida.org/about/legal/aua/public_aua/). To
avoid redistributing CAIDA/PeeringDB-derived data and to keep AS2Web's
licensing terms separate from CAIDA's, we do not redistribute PeeringDB
data or URLs derived from it without independent corroboration.

ASNs that depend on PeeringDB without independent Whois corroboration
have `url` set to `"[Need PeeringDB Data]"`, with the original source
provenance left in place. `scripts/fill_peeringdb.py` can reconstruct
these URLs locally using a CAIDA PeeringDB snapshot. Before accessing
the CAIDA PeeringDB dataset for the first time, visit the [CAIDA
PeeringDB dataset
page](https://www.caida.org/catalog/datasets/peeringdb/) and follow its
**Data Access** link to submit CAIDA's [user-information
form](https://www.caida.org/catalog/datasets/request_user_info_forms/peeringdb/).
If you create a publication using the CAIDA dataset, the Public-AUA
requires you to cite the dataset and report the publication to CAIDA.

### Reconstruction quick start

``` bash
# IPinfo Lite
# 1. Sign up for IPinfo Lite and obtain an API token:
#    https://ipinfo.io/lite
# 2. Set the token in your environment:
export IPINFO_TOKEN=your_token_here

# 3. Fill IPinfo Lite placeholders:
python3 scripts/fill_ipinfo_lite.py \
    --input data/2026-09/as2web.2026-09.json


# CAIDA PeeringDB
# Before first access, follow the Data Access instructions on the
# CAIDA PeeringDB dataset page and submit the user-information form:
# https://www.caida.org/catalog/datasets/peeringdb/
# Use of the dataset is subject to the CAIDA Public-AUA.

python3 scripts/fill_peeringdb.py \
    --input data/2026-09/as2web.2026-09.json \
    --date 2026-09-01
```

The scripts can be run in either order and continue from the same local
reconstructed snapshot by default. For alternative input modes using
your own local IPinfo or CAIDA snapshots, caching, custom output paths,
continuation behavior, and historical-reproducibility details, see
[scripts/README.md](scripts/README.md).

## 2026-09 Method Update

The 2026-09 pipeline introduces a mechanism for reusing URLs from the
preceding published AS2Web snapshot. Its purpose is to avoid repeating
WebSearch queries for ASNs whose underlying organizations have not
changed across snapshots, thereby reducing unnecessary API calls and
associated costs. Reuse is considered only for ASNs that would otherwise
require WebSearch because the AS-centered stage found no usable website.
A previously published URL is reused when the available WHOIS identity
fields---AS name, organization, and description, where provided by the
corresponding RIR---exactly match between snapshots, and the previous
URL still responds to an HTTP probe and passes URL-safety checks. Reused
ASNs do not trigger a new WebSearch query. ASNs with a usable
AS-centered URL bypass this mechanism, while those with changed or
missing WHOIS identity remain eligible for WebSearch. The number of
reused assignments is reported in `ases_url_reused_from_prev`.

For ASNs for which neither the AS-centered stage nor WebSearch produces
a website, the pipeline uses fallback imputation. It selects from
candidate URLs identified by AS-centered sources such as Whois,
PeeringDB, and IPinfo but not successfully reached during normal HTTP
validation. Before inclusion, these candidates undergo URL sanitization
and registry/lookup filtering, and their original source provenance is
preserved. The number of such assignments is reported in
`ases_url_from_fallback_imputation`.

## Citation

If you use this dataset, please cite the paper describing our
methodology:

``` bibtex
@inproceedings{chen2026as2biz,
  title     = {{AS2Biz: Leveraging Web Presence and AI to Improve AS Business Classification}},
  author    = {Chen, Zhiyi and Bischof, Zachary and Testart, Cecilia and Dainotti, Alberto},
  booktitle = {Proceedings of the 2026 ACM Internet Measurement Conference (IMC '26)},
  year      = {2026},
  address   = {Karlsruhe, Germany},
  publisher = {ACM},
  isbn      = {979-8-4007-2327-8/2026/10},
  doi       = {10.1145/3777912.3809155},
  url       = {https://doi.org/10.1145/3777912.3809155},
}
```

And the Zenodo **concept DOI** for the dataset (all versions):
https://doi.org/10.5281/zenodo.19645661

``` bibtex
@software{chen_as2web_concept,
  author       = {Chen, Zhiyi and
                  Bischof, Zachary and
                  Testart, Cecilia and
                  Dainotti, Alberto},
  title        = {AS to Website Mapping (AS2Web)},
  month        = apr,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {2026-03},
  doi          = {10.5281/zenodo.19645661},
  url          = {https://doi.org/10.5281/zenodo.19645661},
}
```

## License / Acceptable Use

The dataset is publicly accessible in this repository. However, any
access and use of the data is subject to the repository license and any
applicable acceptable-use terms.

See the [LICENSE](LICENSE) file for details.

Note: this license applies to AS2Web itself. If you use
`scripts/fill_ipinfo_lite.py` to fill in IPinfo Lite placeholders, the
data you obtain from IPinfo is separately subject to IPinfo's own CC
BY-SA 4.0 terms --- see [IPinfo Lite](#ipinfo-lite) above. Likewise, if
you use `scripts/fill_peeringdb.py` to fill in PeeringDB placeholders,
the data you obtain from CAIDA is separately subject to the CAIDA
Public-AUA --- see [CAIDA PeeringDB](#caida-peeringdb) above.
