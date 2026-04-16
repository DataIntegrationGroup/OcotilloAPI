# AEM Parsers

This package contains AEM source-format parsers and shared parsing helpers.

Responsibilities:
- detect source format
- normalize contractor-delivered files into the canonical sounding schema
- handle CRS normalization and lat/lon derivation
- keep parser logic separate from DB loading and batch orchestration

Modules:
- `detect.py`: format detection and flight ID extraction
- `bylayer.py`: Aarhus Workbench by-layer parser
- `seogi.py`: Seogi rho parser
- `agf.py`: AGF LCI parser
- `common.py`: canonical columns and CRS helpers
