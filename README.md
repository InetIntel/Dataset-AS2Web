# AS2Web Dataset

AS2Web is an Autonomous System (AS) to website mapping dataset. It maps ASes to the official websites of their operating organizations by combining Internet registry and operational data sources with fallback AI-based web search.

<!-- Replace with final Zenodo badge and concept DOI once released. -->
[![DOI](https://zenodo.org/badge/563047649.svg)](https://doi.org/10.5281/zenodo.19645661)

Please open an issue to report any inaccuracies in the dataset (include ASN, month, and evidence).

## Related paper

The methodology behind this dataset is described in:

<!-- Replace with final paper information once available. -->
- *PAPER_TITLE_PLACEHOLDER*  
- Paper link: PAPER_LINK_PLACEHOLDER

## Quick start

- Latest snapshot: see the `data/` directory for monthly JSON snapshots.
- File naming: `as2web.YYYY-MM.json`

## Overview

For each snapshot month, the dataset stores:
- metadata about the snapshot and website-discovery setting used
- a mapping from ASN to its selected website URL
- the provenance of each assigned URL

The JSON structure is:

```json
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

- `snapshot_month`: snapshot month in `YYYY-MM` format, for example `2025-09`
- `web_search_setting`: the model or search setting used for the AI-based web-search fallback stage

Example:

```json
{
  "metadata": {
    "snapshot_month": "2025-09",
    "web_search_setting": "Perplexity AI sonar-pro"
  }
}
```

### `data`

`data` is a dictionary keyed by ASN string. Each ASN maps to a dictionary with the following fields:

- `url`: the selected official website URL of the organization operating the ASN
- `sources`: the source or sources that provided evidence for this URL

Example:

```json
{
  "data": {
    "12345": {
      "url": "https://www.example.com",
      "sources": ["Whois", "PeeringDB"]
    },
    "67890": {
      "url": "https://www.example.net",
      "sources": ["WebSearch"]
    }
  }
}
```

## Source values

Source values indicate where the website evidence came from:

- `Whois`  
  The website comes from Whois data.

- `PeeringDB`  
  The website comes from PeeringDB.

- `IPinfo`  
  The website comes from IPinfo.

- `WebSearch`  
  The website comes from AI-based web search.

When multiple sources support the same website, `sources` records all supporting sources.

## Notes on website selection

AS2Web aims to identify the official website of the organization operating each ASN. In practice, candidate domains may come from multiple sources and may appear in slightly different URL forms. The dataset records the final selected website URL after candidate generation and validation.

## Citation

If you use this dataset, please cite the Zenodo **concept DOI** (all versions):
https://doi.org/10.5281/zenodo.19645661

```bibtex
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
```

If you find the methodology or framework described in our paper useful, please also cite:

```bibtex
@inproceedings{AS2Web_paper_placeholder,
  title        = {PAPER_TITLE_PLACEHOLDER},
  author       = {AUTHOR_LIST_PLACEHOLDER},
  booktitle    = {VENUE_PLACEHOLDER},
  year         = {YEAR_PLACEHOLDER},
  pages        = {PAGES_PLACEHOLDER},
  organization = {PUBLISHER_PLACEHOLDER}
}
```

## License / Acceptable Use

The dataset is publicly accessible in this repository. However, any access and use of the data is subject to the repository license and any applicable acceptable-use terms.

See the [LICENSE](LICENSE) file for details.
