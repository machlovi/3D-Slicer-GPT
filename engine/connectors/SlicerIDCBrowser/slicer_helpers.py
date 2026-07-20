# SlicerIDCBrowser Slicer-side helpers
#
# These functions run locally inside 3D Slicer (no RPyC overhead).
# They are loaded by load_connector_helpers() and registered as
# SlicerIDCBrowser_<name> on the RPyC service.
#
# Requires the IDCBrowser extension to be installed in Slicer,
# which provides the idc-index Python package.

import logging
import re
import tempfile
import threading
import time

_client = None
_client_lock = threading.Lock()

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE)\b",
    re.IGNORECASE,
)


def _ensure_idc_available():
    """Ensure IDCBrowser extension is installed and idc-index is available.

    Uses a targeted hasattr check for module existence so that only the
    "not installed" case is caught. Any other error from getModuleLogic
    or setupPythonRequirements bubbles up with its real message.

    Raises:
        RuntimeError: If the IDCBrowser extension is not installed.
    """
    import slicer

    # Targeted check: only tests module registration, nothing else.
    if not hasattr(slicer.modules, "idcbrowser"):
        raise RuntimeError(
            "SlicerIDCBrowser extension is not installed.\n\n"
            "To fix this:\n"
            "1. Open the Extension Manager (View > Extension Manager)\n"
            "2. Search for 'IDCBrowser'\n"
            "3. Install the extension and restart Slicer"
        )

    # If the module IS registered but getModuleLogic or
    # setupPythonRequirements fails, that's a real bug — let it crash.
    logic = slicer.util.getModuleLogic("IDCBrowser")
    logic.setupPythonRequirements()


def _get_client():
    """Get or create the singleton IDCClient instance (thread-safe)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        # Double-checked locking: another thread may have initialized
        # while we waited for the lock.
        if _client is None:
            _ensure_idc_available()
            from idc_index import index as idc_index
            logging.info("[IDCBrowser] Initializing IDCClient...")
            tic = time.time()
            _client = idc_index.IDCClient()
            logging.info(
                "[IDCBrowser] IDCClient initialized in %.2fs",
                time.time() - tic,
            )
    return _client


def initialize():
    """Eagerly start IDCClient initialization in a background thread.

    Called when the connector is enabled so the index is ready
    before the user's first query.
    """
    def _init():
        try:
            _get_client()
        except Exception as e:
            logging.error("[IDCBrowser] Background init failed: %s", e)

    threading.Thread(target=_init, daemon=True).start()


def list_collections():
    """List available IDC collections with summary statistics.

    Returns:
        Dict with 'collections' list and 'total' count.
    """
    logging.info("[IDCBrowser] Listing collections")
    tic = time.time()

    client = _get_client()
    df = client.sql_query("""
        SELECT
            collection_id,
            COUNT(DISTINCT PatientID) as patients,
            COUNT(DISTINCT SeriesInstanceUID) as series,
            ROUND(SUM(series_size_MB), 1) as size_mb
        FROM index
        GROUP BY collection_id
        ORDER BY collection_id
    """)
    rows = df.to_dict(orient="records")

    logging.info(
        "[IDCBrowser] Listed %d collections in %.2fs",
        len(rows), time.time() - tic,
    )
    return {"collections": rows, "total": len(rows)}


def search(sql, max_rows=50):
    """Execute a SELECT SQL query against the IDC index.

    Args:
        sql: A SELECT SQL query. The table name "index" refers to the
            primary IDC metadata table.
        max_rows: Maximum number of rows to return.

    Returns:
        Dict with total_rows, showing, and rows keys, or 'error' key.
    """
    sql = sql.strip()
    logging.info("[IDCBrowser] Search query: %s", sql[:200])

    upper = sql.upper()
    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        return {"error": "Only SELECT queries are allowed."}
    if _FORBIDDEN_SQL.search(sql):
        return {"error": "DML/DDL statements are not permitted."}

    tic = time.time()
    client = _get_client()
    df = client.sql_query(sql)

    total = len(df)
    truncated = df.head(max_rows)
    rows = truncated.to_dict(orient="records")

    logging.info(
        "[IDCBrowser] Search returned %d rows (showing %d) in %.2fs",
        total, len(rows), time.time() - tic,
    )
    return {
        "total_rows": total,
        "showing": len(rows),
        "rows": rows,
    }


def download_series(series_instance_uid):
    """Download a DICOM series from IDC to a temp directory.

    This function is IDC-specific: it only fetches bytes. Indexing into
    Slicer's DICOM database and loading into the scene are handled by
    the generic SlicerTools methods (import_dicom_directory and
    load_dicom_series), which the idc_download tool composes with this.

    Args:
        series_instance_uid: The DICOM SeriesInstanceUID to download.

    Returns:
        Dict with keys:
            success: bool
            directory: str  (path to the temp directory on success)
            file_count: int
            message: str
    """
    import os

    client = _get_client()

    download_dir = tempfile.mkdtemp(prefix="idc_")
    logging.info(
        "[IDCBrowser] Downloading series %s to %s",
        series_instance_uid, download_dir,
    )
    tic = time.time()

    client.download_from_selection(
        seriesInstanceUID=series_instance_uid,
        downloadDir=download_dir,
        dirTemplate="",
    )

    file_count = sum(
        1 for _, _, files in os.walk(download_dir)
        for f in files if not f.startswith('.')
    )

    download_time = time.time() - tic
    logging.info(
        "[IDCBrowser] Downloaded %d files in %.2fs",
        file_count, download_time,
    )

    if file_count == 0:
        return {
            "success": False,
            "directory": download_dir,
            "file_count": 0,
            "message": f"No files downloaded for series {series_instance_uid}",
        }

    return {
        "success": True,
        "directory": download_dir,
        "file_count": file_count,
        "message": f"Downloaded {file_count} files in {download_time:.2f}s",
    }


def get_collection_info(collection_id):
    """Get metadata summary for a specific IDC collection.

    Args:
        collection_id: The IDC collection identifier.

    Returns:
        Dict with collection metadata or 'error' key.
    """
    logging.info("[IDCBrowser] Getting info for collection: %s", collection_id)
    tic = time.time()

    # Escape single quotes to prevent SQL injection
    safe_id = collection_id.replace("'", "''")

    client = _get_client()
    df = client.sql_query(f"""
        SELECT
            Modality,
            BodyPartExamined,
            COUNT(DISTINCT PatientID) as patients,
            COUNT(DISTINCT SeriesInstanceUID) as series,
            ROUND(SUM(series_size_MB), 1) as size_mb
        FROM index
        WHERE collection_id = '{safe_id}'
        GROUP BY Modality, BodyPartExamined
        ORDER BY series DESC
    """)

    if len(df) == 0:
        return {"error": f"Collection '{collection_id}' not found."}

    rows = df.to_dict(orient="records")

    totals = client.sql_query(f"""
        SELECT
            COUNT(DISTINCT PatientID) as patients,
            COUNT(DISTINCT StudyInstanceUID) as studies,
            COUNT(DISTINCT SeriesInstanceUID) as series,
            ROUND(SUM(series_size_MB), 1) as size_mb
        FROM index
        WHERE collection_id = '{safe_id}'
    """)
    total_info = totals.to_dict(orient="records")[0]

    logging.info(
        "[IDCBrowser] Collection %s: %d patients, %d series in %.2fs",
        collection_id, total_info["patients"], total_info["series"],
        time.time() - tic,
    )

    return {
        "collection_id": collection_id,
        "totals": total_info,
        "breakdown": rows,
    }
