"""
AEM GCS Path Mapper — NMBGMR
=============================
Walks the shared drive, detects each file type, and proposes a
canonical GCS destination path for every file.

Does NOT move or copy anything. Outputs a CSV for review.

GCS hierarchy (agreed April 10 2026):
  surveys/{survey_id}/
    acquisition/
      vectors/           ← flight lines, footprints (SHP/KMZ)
      companions/        ← GEX, TTP, LIN
      binary/            ← SKB, SPS, SR2
    aem/
      raw/
        leveled_xyz/     ← SkyTEM XYZ, GeoTech CSVs
        edited/          ← Geosoft GDB (manually processed)
        forward_models/  ← reference models (if present)
      inversion/
        preliminary/     ← Seogi CSVs, PIK files (preliminary/refined)
        final/
          bylayer/       ← *_byLayer.xyz
          inv/           ← *_inv.xyz
          dat/           ← *_dat.xyz / dobs QA
          agf_lci/       ← AGF LCI CSVs
      interpreted/
        depth_slices/    ← GeoTIFF / Surfer GRD rasters
        leapfrog/        ← .lfview files
    reports/             ← PDFs, PNGs, HTML viz, presentations
    metadata/            ← READMEs, spreadsheets, INI, GDOC stubs

Output columns:
  source_path           — current path on shared drive
  file_name             — filename only
  extension             — file extension
  detected_type         — label from file type detector
  survey_id             — canonical survey identifier
  processing_stage      — acquisition / minimally_processed / manually_processed /
                          preliminary_inversion / refined_inversion / final_inversion /
                          interpreted / acquisition_metadata / reports / unknown
  proposed_gcs_path     — proposed destination (relative to bucket root)
  normalization_needed  — Y/N flag
  normalization_notes   — what needs to change before ingest
  action                — MOVE / FLAG_UNKNOWN / FLAG_REVIEW / HOLD
  action_notes          — why
"""

import os
import re
import csv
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────

# ROOT = r"G:\My Drive\NM AEM Exploration"
ROOT = Path("/Users/jross/Google Drive/My Drive/AEM/NM AEM ExplorationCOPY")
OUTPUT_CSV = "gcs_path_mapping.csv"

# Survey folder name → canonical survey_id
SURVEY_ID_MAP = {
    "Estancia Basin_GeoTech data": "estancia_2025",
    "Gila_Animas_GeoTech data": "gila_animas_2025",
    "Northern Tularosa Basin_GeoTech data": "n_tularosa_2025",
    "Santa Teresa region": "santa_teresa",
}

# ── FILE TYPE DETECTORS (copied from aem_audit.py) ───────────────────────────


def is_seogi_rho(fname, ext, parent):
    return ext == ".csv" and fname.startswith("rho_")


def is_seogi_dobs(fname, ext, parent):
    return ext == ".csv" and fname.startswith("dobs_")


def is_seogi_dpred(fname, ext, parent):
    return ext == ".csv" and fname.startswith("dpred_")


def is_seogi_collar(fname, ext, parent):
    return ext == ".csv" and fname.startswith("collar")


def is_seogi_survey(fname, ext, parent):
    return ext == ".csv" and fname.startswith("survey-")


def is_seogi_interval(fname, ext, parent):
    return ext == ".csv" and fname.startswith("interval")


def is_geotech_raw(fname, ext, parent):
    if ext != ".csv":
        return False
    if re.match(r"gl\d+_f\d+", fname):
        return True
    if re.match(r"gl\d+_preliminary_f\d+", fname):
        return True
    if re.match(r"raw_data_gl\d+_f[\d\-]+", fname):
        return True
    return False


def is_geotech_qa_stats(fname, ext, parent):
    return ext == ".csv" and any(
        x in fname for x in ("gate_stats", "early_mid_late", "_stats")
    )


def is_agf_lci(fname, ext, parent):
    return ext == ".csv" and "lci" in fname and "prelim" in fname


def is_skytem_raw_xyz(fname, ext, parent):
    return (
        ext == ".xyz"
        and any(x in fname for x in ("skytem", "prelim", "raw", "processed"))
    ) or (ext == ".xyz" and "mimbres" in fname)


def is_aarhus_bylayer(fname, ext, parent):
    # Standard naming: *_byLayer.xyz
    # Non-standard (Santa Teresa GIP): Q_SCI_I01_by_Layer_MOD.xyz
    if ext != ".xyz":
        return False
    return "bylayer" in fname or "by_layer" in fname


def is_aarhus_inv(fname, ext, parent):
    if ext != ".xyz":
        return False
    return (
        fname.endswith("_inv.xyz")
        or fname.endswith("_mod_inv.xyz")
        or (re.search(r"sci_i\d+.*inv", fname) is not None)
    )


def is_aarhus_dat(fname, ext, parent):
    if ext != ".xyz":
        return False
    return (
        fname.endswith("_dat.xyz")
        or fname.endswith("_mod_dat.xyz")
        or (re.search(r"sci_i\d+.*dat", fname) is not None)
        or fname.endswith("_mod_syn.xyz")
    )  # synthetic/predicted = dat equivalent


def is_gex(fname, ext, parent):
    return ext == ".gex"


def is_ttp(fname, ext, parent):
    return ext == ".ttp"


def is_lin(fname, ext, parent):
    return ext == ".lin"


def is_sr2(fname, ext, parent):
    return ext == ".sr2"


def is_skb(fname, ext, parent):
    return ext == ".skb"


def is_sps(fname, ext, parent):
    return ext == ".sps"


def is_pik(fname, ext, parent):
    return ext == ".pik"


def is_gerda_gdb(fname, ext, parent):
    return ext == ".gdb" and any(
        x in parent for x in ("gerda", "workbench", "workspace", "aarhus")
    )


def is_geosoft_gdb(fname, ext, parent):
    return ext == ".gdb" and not any(
        x in parent for x in ("gerda", "workbench", "workspace", "aarhus")
    )


def is_lfview(fname, ext, parent):
    return ext == ".lfview"


def is_geosoftvoxel(fname, ext, parent):
    return ext == ".geosoftvoxel"


def is_html_viz(fname, ext, parent):
    return ext in (".html", ".htm")


def is_geotiff(fname, ext, parent):
    return ext in (".tif", ".tiff")


def is_shapefile(fname, ext, parent):
    return ext == ".shp"


def is_shp_sidecar(fname, ext, parent):
    # Standard shapefile sidecar extensions
    if ext in (".dbf", ".shx", ".prj", ".cpg", ".qpj"):
        return True
    # Spatial index files (.sbn, .sbx) — travel with .shp
    if ext in (".sbn", ".sbx"):
        return True
    # ArcGIS metadata XML attached to shapefile (e.g. CNMECLINES.shp.xml)
    if fname.endswith(".shp.xml"):
        return True
    return False


def is_kmz(fname, ext, parent):
    return ext == ".kmz"


def is_edi(fname, ext, parent):
    return ext == ".edi"


def is_zip(fname, ext, parent):
    return ext in (".zip", ".tar", ".gz", ".7z")


def is_pdf(fname, ext, parent):
    return ext == ".pdf"


def is_png(fname, ext, parent):
    return ext == ".png"


def is_jpg(fname, ext, parent):
    return ext in (".jpg", ".jpeg")


def is_readme(fname, ext, parent):
    return "readme" in fname or fname == "read_me.txt"


def is_presentation(fname, ext, parent):
    return ext == ".pptx"


def is_spreadsheet(fname, ext, parent):
    return ext in (".xlsx", ".xls")


def is_gdoc(fname, ext, parent):
    return ext == ".gdoc"


def is_ini(fname, ext, parent):
    return ext == ".ini"


def is_mpkx(fname, ext, parent):
    return ext == ".mpkx"


# ── NEW DETECTORS ─────────────────────────────────────────────────────────────


def is_thumbs_db(fname, ext, parent):
    """Windows thumbnail cache — skip, do not migrate."""
    return fname in ("thumbs.db", "desktop.ini", ".ds_store")


def is_geosoft_grid_index(fname, ext, parent):
    """Geosoft Grid Index (.gi) — sidecar to GRD/TIF, archive alongside parent."""
    return ext == ".gi"


def is_geosoft_zone(fname, ext, parent):
    """Geosoft Zone/Colour file (.zon) — colour scale for a grid, archive alongside GRD."""
    return ext == ".zon"


def is_geosoft_map(fname, ext, parent):
    """Geosoft Montaj map layout file (.map) — archive alongside GDB."""
    return ext == ".map"


def is_ahsan_inversion_csv(fname, ext, parent):
    """Per-line inversion result CSV from Ahsan's Aarhus Workbench work.
    Naming pattern: line_L####_inverted_resistivity_cells_discrete.csv
    Columns: line_no, distance_m, easting, northing, elev_top_m, elev_bottom_m,
             elev_center_m, depth_top_m, depth_bottom_m, depth_center_m, rho_ohm_m
    """
    return ext == ".csv" and "inverted_resistivity_cells_discrete" in fname


def is_geosoft_native_grd(fname, ext, parent):
    """Geosoft native grid file — NOT Surfer GRD. Detected by filename content.
    These are standard GeoTech deliverables: CVG, DEM, SFz, PLM, TauSF, RTP, mag grids.
    Cannot be distinguished from Surfer GRD by extension alone — use content type from name.
    """
    if ext != ".grd":
        return False
    geosoft_patterns = (
        "_cvg",
        "_cvg_rtp",
        "_dem",
        "_dem_laser",
        "_sfz",
        "_plm",
        "_taush",
        "_rtp",
        "_mag",
        "_tmi",
        "_rmf",
        "_dBdt",
        "dbdt",
    )
    return any(p in fname for p in geosoft_patterns)


def _read_grd_header(fpath):
    try:
        with open(fpath, "rb") as f:
            return f.read(4)
    except Exception:
        return b""


def classify_grd(fpath):
    h = _read_grd_header(fpath)
    if h[:4] == b"DSAA":
        return "surfer_grd_ascii"
    if h[:4] == b"DSBB":
        return "surfer_grd_binary"
    if h[:4] == b"DSRB":
        return "surfer_grd_binary_v2"
    return "grd_unknown_format"


DETECTORS = [
    # System files — check first so they don't match other patterns
    ("thumbs_db", is_thumbs_db),
    # Seogi inversion outputs
    ("seogi_rho", is_seogi_rho),
    ("seogi_dobs", is_seogi_dobs),
    ("seogi_dpred", is_seogi_dpred),
    ("seogi_collar", is_seogi_collar),
    ("seogi_survey", is_seogi_survey),
    ("seogi_interval", is_seogi_interval),
    # Ahsan per-line inversion CSVs — before geotech_raw so pattern is caught first
    ("ahsan_inversion_csv", is_ahsan_inversion_csv),
    # GeoTech raw and QA
    ("geotech_raw_csv", is_geotech_raw),
    ("geotech_qa_stats", is_geotech_qa_stats),
    # AGF LCI
    ("agf_lci_csv", is_agf_lci),
    # SkyTEM raw
    ("skb_binary", is_skb),
    ("sps_ascii", is_sps),
    ("sr2_index", is_sr2),
    ("skytem_raw_xyz", is_skytem_raw_xyz),
    # Aarhus Workbench exports — bylayer before inv/dat to avoid false matches
    ("aarhus_bylayer", is_aarhus_bylayer),
    ("aarhus_inv_xyz", is_aarhus_inv),
    ("aarhus_dat_xyz", is_aarhus_dat),
    # Companion files
    ("gex_geometry", is_gex),
    ("ttp_columns", is_ttp),
    ("lin_lines", is_lin),
    # Inversion
    ("pik_inversion", is_pik),
    # Databases
    ("gerda_workspace", is_gerda_gdb),
    ("geosoft_gdb", is_geosoft_gdb),
    # Visualization / 3D
    ("lfview", is_lfview),
    ("geosoftvoxel", is_geosoftvoxel),
    ("html_visualization", is_html_viz),
    # Raster / Grid
    # Note: .grd handled separately in detect_type() via header check
    # But Geosoft-named GRDs can be identified by filename pattern first
    ("geosoft_native_grd", is_geosoft_native_grd),
    ("geotiff", is_geotiff),
    # Geosoft sidecar files
    ("geosoft_grid_index", is_geosoft_grid_index),
    ("geosoft_zone", is_geosoft_zone),
    ("geosoft_map", is_geosoft_map),
    # Vector — shp_sidecar before shapefile so sidecar extensions are caught first
    ("shp_sidecar", is_shp_sidecar),
    ("shapefile", is_shapefile),
    ("kmz", is_kmz),
    # MT
    ("edi_mt", is_edi),
    # Archives
    ("archive_zip", is_zip),
    # Documents / reports
    ("pdf_report", is_pdf),
    ("png_image", is_png),
    ("jpg_image", is_jpg),
    ("presentation_pptx", is_presentation),
    ("spreadsheet", is_spreadsheet),
    ("readme", is_readme),
    ("gdoc_stub", is_gdoc),
    ("ini_config", is_ini),
    ("esri_mappackage", is_mpkx),
]


def detect_type(fpath):
    fname = fpath.name.lower()
    ext = fpath.suffix.lower()
    parent = str(fpath.parent).lower()

    # Windows thumbnail/system files — check before anything else
    if fname in ("thumbs.db", "desktop.ini", ".ds_store"):
        return "thumbs_db"

    # .shp.xml — ArcGIS metadata sidecar — catch before .xml is treated as unknown
    if fname.endswith(".shp.xml"):
        return "shp_sidecar"

    # .grd — try to distinguish Geosoft native from Surfer via filename first,
    # then fall back to header check. Geosoft GRDs from GeoTech have recognisable
    # content-type patterns in the filename (CVG, DEM, SFz, PLM, TauSF, RTP, mag).
    # Surfer GRDs (Santa Teresa) use MRES naming. Header check is authoritative.
    if ext == ".grd":
        grd_type = classify_grd(fpath)
        if grd_type in (
            "surfer_grd_ascii",
            "surfer_grd_binary",
            "surfer_grd_binary_v2",
        ):
            return grd_type
        # Header didn't match Surfer — check if it looks like a Geosoft named grid
        if is_geosoft_native_grd(fname, ext, parent):
            return "geosoft_native_grd"
        return grd_type  # grd_unknown_format fallback

    for label, fn in DETECTORS:
        if fn(fname, ext, parent):
            return label
    return f"other_{ext}" if ext else "other"


# ── GCS PATH MAPPER ───────────────────────────────────────────────────────────


def geotech_flight_id(fname):
    """Extract flight ID from GeoTech filename for wellid prefix notes."""
    m = re.search(r"_f(\d[\d\-]*)", fname.lower())
    if m:
        return "F" + m.group(1).replace("-", "_")
    return None


def propose(fpath, detected_type, survey_id, survey_folder):
    """
    Returns (processing_stage, proposed_gcs_path, normalization_needed,
             normalization_notes, action, action_notes)
    """
    sid = survey_id
    fname = fpath.name
    fname_l = fname.lower()
    base = f"surveys/{sid}"
    is_santa = "santa" in survey_id

    # ── System files ─────────────────────────────────────────────────────────
    if detected_type == "thumbs_db":
        return (
            "metadata",
            f"{base}/SKIP/{fname}",
            "N",
            "",
            "SKIP",
            "Windows system file — do not migrate to GCS",
        )

    # ── Ahsan per-line inversion CSVs ────────────────────────────────────────
    if detected_type == "ahsan_inversion_csv":
        return (
            "preliminary_inversion",
            f"{base}/aem/inversion/preliminary/{fname}",
            "N",
            "Per-line inversion result from Ahsan (Aarhus Workbench). "
            "Columns: line_no, distance_m, easting, northing, elev_top_m, elev_bottom_m, "
            "elev_center_m, depth_top_m, depth_bottom_m, depth_center_m, rho_ohm_m. "
            "Confirm with Ahsan whether these are preliminary or refined inversion — "
            "move to final/ if confirmed final.",
            "FLAG_REVIEW",
            "Ahsan per-line inversion CSV — confirm processing stage before classifying",
        )

    # ── Acquisition geometry ──────────────────────────────────────────────────
    if detected_type == "skb_binary":
        return (
            "raw_acquisition",
            f"{base}/acquisition/binary/{fpath.parent.name}/{fname}",
            "N",
            "",
            "MOVE",
            "Archive-only — SkyLab required to process",
        )

    if detected_type in ("sps_ascii", "sr2_index"):
        return (
            "raw_acquisition",
            f"{base}/acquisition/binary/{fpath.parent.name}/{fname}",
            "N",
            "",
            "MOVE",
            "Archive-only",
        )

    if detected_type in ("gex_geometry", "ttp_columns", "lin_lines"):
        return (
            "acquisition_metadata",
            f"{base}/acquisition/companions/{fname}",
            "N",
            "",
            "MOVE",
            "Required for Aarhus Workbench re-inversion — keep with binary/",
        )

    if detected_type in ("shapefile", "shp_sidecar"):
        return (
            "acquisition_metadata",
            f"{base}/acquisition/vectors/{fname}",
            "N",
            "",
            "MOVE",
            "Flight lines / survey footprint",
        )

    if detected_type == "kmz":
        return (
            "acquisition_metadata",
            f"{base}/acquisition/vectors/{fname}",
            "N",
            "",
            "MOVE",
            "Google Earth flight lines / footprint",
        )

    # ── Minimally processed (leveled) ─────────────────────────────────────────
    if detected_type == "geotech_raw_csv":
        norm_needed = "N"
        norm_notes = ""
        # N. Tularosa has capitalisation inconsistency and multi-flight files
        if "tularosa" in survey_id:
            norm_needed = "Y"
            norm_notes = (
                "Normalise capitalisation (Raw_data_ vs Raw_Data_). "
                "Multi-flight files (e.g. F01-F02) — document span in metadata. "
                "Proposal GL250259."
            )
        elif "preliminary" in fname_l:
            norm_needed = "Y"
            norm_notes = "Naming variant GL######_Preliminary_F##.csv — normalise to GL######_F##.csv"
        return (
            "minimally_processed",
            f"{base}/aem/raw/leveled_xyz/{fname}",
            norm_needed,
            norm_notes,
            "MOVE",
            "GeoTech raw acquisition CSV",
        )

    if detected_type == "skytem_raw_xyz":
        return (
            "minimally_processed",
            f"{base}/aem/raw/leveled_xyz/{fname}",
            "N",
            "",
            "MOVE",
            "SkyTEM XYZ export — space-delimited, * = null. "
            "GEX+TTP+LIN companions must be present alongside.",
        )

    if detected_type == "geotech_qa_stats":
        return (
            "minimally_processed",
            f"{base}/aem/raw/leveled_xyz/{fname}",
            "N",
            "",
            "MOVE",
            "GeoTech QA statistics file — archive alongside raw CSVs",
        )

    # ── Manually processed ────────────────────────────────────────────────────
    if detected_type == "geosoft_gdb":
        is_final = "final" in fname_l
        action_note = (
            "FINAL GDB — likely final manually processed database. "
            "Confirm contents before moving. DO NOT rename internal files."
            if is_final
            else "Geosoft Montaj GDB — confirm file vs folder structure before move"
        )
        return (
            "manually_processed",
            f"{base}/aem/raw/edited/{fname}",
            "N",
            "DO NOT rename internal files/folders — Geosoft GDB internal structure may break. "
            "Confirm whether this is a standalone file or folder-based GDB before moving.",
            "FLAG_REVIEW",
            action_note,
        )

    if detected_type == "gerda_workspace":
        return (
            "manually_processed",
            f"{base}/aem/raw/edited/{fname}",
            "N",
            "DO NOT rename — Aarhus GERDA workspace internal structure breaks if renamed.",
            "FLAG_REVIEW",
            "Aarhus GERDA workspace — must archive as-is, confirm folder structure intact",
        )

    # ── Preliminary / refined inversion ──────────────────────────────────────
    if detected_type in (
        "seogi_rho",
        "seogi_dobs",
        "seogi_dpred",
        "seogi_collar",
        "seogi_survey",
        "seogi_interval",
    ):
        flight_id = geotech_flight_id(fname_l)
        norm_needed = "Y"
        norm_notes = (
            f"wellid resets to 1 per flight folder. "
            f"Prefix wellid with flight ID ({flight_id or 'F??'}_) before merging across flights."
        )
        subtype = detected_type.replace("seogi_", "")
        return (
            "preliminary_inversion",
            f"{base}/aem/inversion/preliminary/{fname}",
            norm_needed,
            norm_notes,
            "MOVE",
            f"Seogi Python preliminary inversion output ({subtype})",
        )

    if detected_type == "pik_inversion":
        return (
            "preliminary_inversion",
            f"{base}/aem/inversion/preliminary/{fname}",
            "N",
            "Confirm processing stage with Ahsan/DBS&A: "
            "preliminary, refined, or final? "
            "N. Tularosa PIKs are likely refined inversion (Ahsan in-house Aarhus Workbench). "
            "Move to aem/inversion/final/ if confirmed final.",
            "FLAG_REVIEW",
            "PIK inversion file — processing stage unconfirmed",
        )

    # ── Final inversion ───────────────────────────────────────────────────────
    if detected_type == "aarhus_bylayer":
        return (
            "final_inversion",
            f"{base}/aem/inversion/final/bylayer/{fname}",
            "N",
            "",
            "MOVE",
            "Aarhus Workbench byLayer export — PRIMARY INGEST TARGET",
        )

    if detected_type == "aarhus_inv_xyz":
        return (
            "final_inversion",
            f"{base}/aem/inversion/final/inv/{fname}",
            "N",
            "",
            "MOVE",
            "Aarhus Workbench inv export — full uncertainty per layer",
        )

    if detected_type == "aarhus_dat_xyz":
        return (
            "final_inversion",
            f"{base}/aem/inversion/final/dat/{fname}",
            "N",
            "",
            "MOVE",
            "Aarhus Workbench dat export — observed EM data QA",
        )

    if detected_type == "agf_lci_csv":
        return (
            "final_inversion",
            f"{base}/aem/inversion/final/agf_lci/{fname}",
            "N",
            "",
            "MOVE",
            "AGF Aarhus Workbench LCI CSV — treat as final inversion",
        )

    # ── Interpreted products ──────────────────────────────────────────────────
    if detected_type == "geotiff":
        norm_needed = "Y"
        norm_notes = (
            "Rename to canonical convention: {survey_id}_{depth_m}m.tif. "
            "Validate CRS embedded (expected EPSG:26913 or 32613)."
        )
        return (
            "interpreted",
            f"{base}/aem/interpreted/depth_slices/{fname}",
            norm_needed,
            norm_notes,
            "MOVE",
            "Resistivity depth slice raster",
        )

    if detected_type in (
        "surfer_grd_binary_v2",
        "surfer_grd_binary",
        "surfer_grd_ascii",
        "grd_unknown_format",
    ):
        action = "HOLD" if is_santa else "FLAG_REVIEW"
        notes = (
            "Santa Teresa: BLOCKED on (1) CRS confirmation from GIP "
            "and (2) data rights confirmation (prior NMISC contract). "
            "Once both confirmed: gdal_translate -of GTiff -a_srs EPSG:{CRS} input.grd output.tif. "
            "Then move converted TIF to aem/interpreted/depth_slices/."
            if is_santa
            else "Unexpected GRD file outside Santa Teresa — investigate format and origin."
        )
        return (
            "interpreted",
            f"{base}/aem/interpreted/depth_slices/{fname}",
            "Y",
            f"Surfer GRD ({detected_type}) — requires GDAL conversion to GeoTIFF before ingest. "
            f"Confirm CRS before converting.",
            action,
            notes,
        )

    if detected_type == "geosoft_native_grd":
        # Route by content type: resistivity/conductance/EM grids → interpreted
        # magnetic/DEM/PLM grids → acquisition
        interp_patterns = ("_cvg", "_sfz", "_taush", "taush", "_rtp", "dBdt", "dbdt")
        acq_patterns = ("_dem", "_mag", "_tmi", "_rmf", "_plm")
        fname_check = fname_l
        if any(p in fname_check for p in interp_patterns):
            return (
                "interpreted",
                f"{base}/aem/interpreted/depth_slices/{fname}",
                "Y",
                "Geosoft native GRD — conductance/EM grid. "
                "Convert to GeoTIFF with GDAL before platform ingest: "
                "gdal_translate -of GTiff input.grd output.tif (confirm CRS first).",
                "FLAG_REVIEW",
                "Geosoft GRD — needs GDAL conversion to GeoTIFF before ingest",
            )
        elif any(p in fname_check for p in acq_patterns):
            return (
                "acquisition_metadata",
                f"{base}/acquisition/vectors/{fname}",
                "Y",
                "Geosoft native GRD — DEM/magnetic/PLM grid. "
                "Convert to GeoTIFF with GDAL before platform ingest.",
                "FLAG_REVIEW",
                "Geosoft GRD — needs GDAL conversion before ingest, route as acquisition",
            )
        else:
            return (
                "interpreted",
                f"{base}/aem/interpreted/depth_slices/{fname}",
                "Y",
                "Geosoft native GRD — content type unclear from filename. "
                "Inspect and route to interpreted/ or acquisition/ accordingly.",
                "FLAG_REVIEW",
                "Geosoft GRD — confirm content type before routing",
            )

    if detected_type == "geosoft_grid_index":
        # .gi sidecar — archive alongside its parent GRD or TIF
        return (
            "interpreted",
            f"{base}/aem/interpreted/depth_slices/{fname}",
            "N",
            "Geosoft Grid Index sidecar (.gi) — must be archived alongside its parent GRD or TIF file. "
            "Do not move without the parent file.",
            "MOVE",
            "Geosoft sidecar — archive with parent grid",
        )

    if detected_type == "geosoft_zone":
        # .zon colour scale file — archive alongside its parent GRD
        return (
            "interpreted",
            f"{base}/aem/interpreted/depth_slices/{fname}",
            "N",
            "Geosoft Zone/Colour file (.zon) — colour scale definition for the parent GRD. "
            "Archive alongside parent GRD.",
            "MOVE",
            "Geosoft sidecar — archive with parent grid",
        )

    if detected_type == "geosoft_map":
        # .map layout file — archive alongside GDB
        return (
            "reports",
            f"{base}/reports/{fname}",
            "N",
            "Geosoft Montaj map layout (.map) — the layout file that produced the PDF maps. "
            "Archive alongside the GDB it references.",
            "MOVE",
            "Geosoft map layout — archive with reports",
        )
        return (
            "interpreted",
            f"{base}/aem/interpreted/leapfrog/{fname}",
            "Y",
            "Leapfrog proprietary format — request re-export from DBS&A in open format "
            "(CSV point cloud, DXF, or Geosoft voxel). Free viewer available but cannot export.",
            "FLAG_REVIEW",
            "DBS&A interpreted product — plan open re-export before archiving",
        )

    if detected_type == "geosoftvoxel":
        return (
            "interpreted",
            f"{base}/aem/interpreted/depth_slices/{fname}",
            "Y",
            "Geosoft voxel format — needs conversion to open format for platform ingest.",
            "FLAG_REVIEW",
            "3D resistivity voxel — confirm conversion path",
        )

    # ── Reports / visualizations ──────────────────────────────────────────────
    if detected_type == "pdf_report":
        return (
            "reports",
            f"{base}/reports/{fname}",
            "N",
            "",
            "MOVE",
            "PDF report or map document",
        )

    if detected_type == "png_image":
        return (
            "reports",
            f"{base}/reports/visualizations/{fname}",
            "N",
            "",
            "MOVE",
            "Cross-section image or visualization screenshot — "
            "derived from inversion results, not a scientific data product itself",
        )

    if detected_type == "jpg_image":
        return (
            "reports",
            f"{base}/reports/visualizations/{fname}",
            "N",
            "",
            "MOVE",
            "Project area map or photograph",
        )

    if detected_type == "html_visualization":
        return (
            "reports",
            f"{base}/reports/visualizations/{fname}",
            "N",
            "",
            "MOVE",
            "Interactive HTML visualization (Ahsan / Seogi fence diagrams)",
        )

    if detected_type == "presentation_pptx":
        return (
            "reports",
            f"{base}/reports/{fname}",
            "N",
            "",
            "MOVE",
            "Inversion results presentation or ZTEM proposal document",
        )

    if detected_type == "kmz":
        return (
            "acquisition_metadata",
            f"{base}/acquisition/vectors/{fname}",
            "N",
            "",
            "MOVE",
            "Google Earth KMZ — flight lines or resistivity overview",
        )

    # ── Metadata ──────────────────────────────────────────────────────────────
    if detected_type == "readme":
        return (
            "metadata",
            f"{base}/metadata/{fname}",
            "N",
            "",
            "MOVE",
            "README — move to survey metadata folder",
        )

    if detected_type == "spreadsheet":
        # Time gate spec goes with companions; well logs go to metadata
        if "timegate" in fname_l or ("vtem" in fname_l and "gate" in fname_l):
            return (
                "acquisition_metadata",
                f"{base}/acquisition/companions/{fname}",
                "N",
                "",
                "MOVE",
                "VTEM time gate specification — keep with companion files",
            )
        if "well" in fname_l or "log" in fname_l or "borehole" in fname_l:
            return (
                "metadata",
                f"{base}/metadata/{fname}",
                "N",
                "",
                "MOVE",
                "Well log data — ground truth reference, store in survey metadata",
            )
        return (
            "metadata",
            f"{base}/metadata/{fname}",
            "N",
            "",
            "MOVE",
            "Spreadsheet — review contents, likely metadata or reference data",
        )

    if detected_type == "gdoc_stub":
        return (
            "metadata",
            f"{base}/metadata/{fname}",
            "N",
            "",
            "MOVE",
            "Google Doc stub (178B) — likely just a Drive link, low priority",
        )

    if detected_type == "ini_config":
        return (
            "metadata",
            f"{base}/metadata/{fname}",
            "N",
            "",
            "SKIP",
            "Windows system file — do not migrate to GCS",
        )

    # ── Unknowns / archives ───────────────────────────────────────────────────
    if detected_type == "archive_zip":
        return (
            "unknown",
            f"{base}/aem/raw/leveled_xyz/UNZIPPED/{fname}",
            "Y",
            "Must be unzipped and inventoried before GCS path can be assigned. "
            "Contents unknown — likely raw GeoTech acquisition data or reports.",
            "FLAG_UNKNOWN",
            "Open and re-run mapper on contents before moving",
        )

    if detected_type == "edi_mt":
        return (
            "minimally_processed",
            f"surveys/mimbres_mt/aem/raw/leveled_xyz/{fname}",
            "N",
            "",
            "MOVE",
            "MT EDI file — separate survey_id from AEM. "
            "Parse with mt_metadata or mtpy.",
        )

    # ── Catch-all ─────────────────────────────────────────────────────────────
    return (
        "unknown",
        f"{base}/REVIEW_NEEDED/{fname}",
        "Y",
        "File type not recognized — review before assigning GCS path.",
        "FLAG_UNKNOWN",
        f"Unrecognized type: {detected_type}",
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────

rows = []

for folder_name, survey_id in SURVEY_ID_MAP.items():
    folder_path = Path(ROOT) / folder_name
    if not folder_path.exists():
        print(f"[SKIP] Folder not found: {folder_path}")
        continue

    print(f"Scanning {folder_name} ...")
    for dirpath, dirnames, filenames in os.walk(folder_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname.startswith("."):
                continue
            fpath = Path(dirpath) / fname
            try:
                size = fpath.stat().st_size
            except Exception:
                size = 0

            detected = detect_type(fpath)
            stage, gcs_path, norm_yn, norm_notes, action, action_notes = propose(
                fpath, detected, survey_id, folder_name
            )

            rows.append(
                {
                    "source_path": str(fpath),
                    "file_name": fname,
                    "extension": fpath.suffix.lower(),
                    "size_bytes": size,
                    "size_human": (
                        f"{size/1e6:.1f} MB" if size > 1e6 else f"{size/1e3:.1f} KB"
                    ),
                    "detected_type": detected,
                    "survey_folder": folder_name,
                    "survey_id": survey_id,
                    "processing_stage": stage,
                    "proposed_gcs_path": gcs_path,
                    "normalization_needed": norm_yn,
                    "normalization_notes": norm_notes,
                    "action": action,
                    "action_notes": action_notes,
                }
            )

# Sort: survey → processing stage → filename
STAGE_ORDER = {
    "raw_acquisition": 0,
    "acquisition_metadata": 1,
    "minimally_processed": 2,
    "manually_processed": 3,
    "preliminary_inversion": 4,
    "refined_inversion": 5,
    "final_inversion": 6,
    "interpreted": 7,
    "reports": 8,
    "metadata": 9,
    "unknown": 10,
}
rows.sort(
    key=lambda r: (
        r["survey_id"],
        STAGE_ORDER.get(r["processing_stage"], 99),
        r["file_name"].lower(),
    )
)

# Write CSV
fieldnames = [
    "survey_id",
    "survey_folder",
    "processing_stage",
    "detected_type",
    "action",
    "normalization_needed",
    "file_name",
    "extension",
    "size_human",
    "size_bytes",
    "source_path",
    "proposed_gcs_path",
    "normalization_notes",
    "action_notes",
]

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# Summary to console
print(f"\nMapped {len(rows)} files → {OUTPUT_CSV}")
print()

from collections import Counter, defaultdict

action_counts = Counter(r["action"] for r in rows)
stage_counts = Counter(r["processing_stage"] for r in rows)
norm_count = sum(1 for r in rows if r["normalization_needed"] == "Y")

print("── ACTION SUMMARY ──────────────────────────────────────────────")
for action, count in sorted(action_counts.items()):
    print(f"  {action:<20} {count:>4} files")
print()
print("── BY PROCESSING STAGE ─────────────────────────────────────────")
for stage, count in sorted(
    stage_counts.items(), key=lambda x: STAGE_ORDER.get(x[0], 99)
):
    print(f"  {stage:<30} {count:>4} files")
print()
print(f"  Files needing normalization before ingest: {norm_count}")
print()

# Per-survey breakdown
print("── BY SURVEY ───────────────────────────────────────────────────")
per_survey = defaultdict(lambda: defaultdict(int))
for r in rows:
    per_survey[r["survey_id"]][r["action"]] += 1
for sid, actions in sorted(per_survey.items()):
    print(f"  {sid}")
    for a, n in sorted(actions.items()):
        print(f"    {a:<20} {n}")
print()
print("── FLAGS TO REVIEW BEFORE ANY MOVE ────────────────────────────")
flags = [r for r in rows if r["action"] in ("FLAG_UNKNOWN", "FLAG_REVIEW", "HOLD")]
for r in flags:
    print(f"  [{r['action']}] {r['survey_id']} / {r['file_name']}")
    if r["action_notes"]:
        print(f"    → {r['action_notes'][:80]}")
