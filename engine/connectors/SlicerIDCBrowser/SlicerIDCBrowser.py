"""
SlicerIDCBrowser connector for Talk2View.

Provides access to the NCI Imaging Data Commons (IDC) for browsing,
querying, and downloading public cancer imaging data (CT, MR, PET,
pathology). Requires the IDCBrowser Slicer extension to be installed.
"""

import logging
import time
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from utils.connector_base import log_and_return_error


class _IDCSearchInput(BaseModel):
    """Input schema for IDC metadata search."""
    model_config = ConfigDict(extra="forbid")

    sql: str = Field(
        description=(
            'SQL SELECT query against the IDC "index" table. '
            "Key columns: collection_id, PatientID, StudyInstanceUID, "
            "SeriesInstanceUID, Modality, BodyPartExamined, "
            "StudyDescription, SeriesDescription, Manufacturer, "
            "PatientAge, PatientSex, license_short_name, series_size_MB. "
            'Example: "SELECT collection_id, Modality, COUNT(*) as n '
            "FROM index WHERE Modality = 'CT' "
            'GROUP BY collection_id, Modality LIMIT 20"'
        )
    )
    max_rows: int = Field(
        default=50,
        description="Maximum number of rows to return (1-200)",
        ge=1,
        le=200,
    )


class _IDCDownloadInput(BaseModel):
    """Input schema for downloading IDC data."""
    model_config = ConfigDict(extra="forbid")

    series_instance_uid: str = Field(
        description=(
            "DICOM SeriesInstanceUID to download. "
            "Use idc_search first to find the UID."
        )
    )


class _IDCCollectionInfoInput(BaseModel):
    """Input schema for getting collection info."""
    model_config = ConfigDict(extra="forbid")

    collection_id: str = Field(
        description=(
            "IDC collection identifier (e.g. 'tcga_luad', 'nlst', 'rider_pilot'). "
            "Use idc_list_collections to see available collections."
        )
    )


class SlicerIDCBrowser:
    """
    Talk2View connector for the NCI Imaging Data Commons.

    Provides tools to search IDC metadata, browse collections, and
    download DICOM data directly into Slicer. Requires the IDCBrowser
    extension to be installed in 3D Slicer.
    """

    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn

        # Load Slicer-side helpers (registered as
        # SlicerIDCBrowser_<name> on the RPyC service).
        self.talk2view_core.root.load_connector_helpers("SlicerIDCBrowser")

        # Start IDCClient initialization in background so the index
        # is downloaded before the user's first query.
        self.talk2view_core.root.SlicerIDCBrowser_initialize()

        self.tools = [
            tool(self.idc_list_collections),
            tool(self.idc_search, args_schema=_IDCSearchInput),
            tool(self.idc_download, args_schema=_IDCDownloadInput),
            tool(self.idc_get_collection_info, args_schema=_IDCCollectionInfoInput),
        ]
        self.tool_node = ToolNode(self.tools)

        logging.info("SlicerIDCBrowser connector initialized")

    def idc_list_collections(self) -> str:
        """
        List all available collections in the NCI Imaging Data Commons.

        Returns a summary of each collection with patient count, series
        count, and total size. Use this to discover what imaging data is
        available before searching or downloading.

        Returns:
            Formatted list of IDC collections.
        """
        tic = time.time()
        result = self.talk2view_core.root.SlicerIDCBrowser_list_collections()
        toc = time.time()

        if "error" in result:
            return f"Error: {result['error']}"

        collections = result["collections"]
        logging.info(
            "idc_list_collections: %d collections in %.2fs",
            len(collections), toc - tic,
        )

        lines = [f"**IDC Collections** ({result['total']} total):\n"]
        for c in collections:
            lines.append(
                f"- `{c['collection_id']}`: "
                f"{c['patients']} patients, "
                f"{c['series']} series, "
                f"{c['size_mb']} MB"
            )

        lines.append(
            "\n---\n"
            "*Use idc_get_collection_info(collection_id) for details, "
            "or idc_search(sql) for custom queries.*"
        )
        return "\n".join(lines)

    def idc_search(self, sql: str, max_rows: int = 50) -> str:
        """
        Search IDC metadata using SQL queries.

        Query the IDC index table to find imaging data by modality,
        body part, collection, patient, or other metadata. Only SELECT
        queries are allowed.

        The table name is "index". Key columns:
        - collection_id, PatientID, StudyInstanceUID, SeriesInstanceUID
        - Modality (CT, MR, PT, SM, etc.), BodyPartExamined
        - StudyDescription, SeriesDescription
        - Manufacturer, ManufacturerModelName
        - PatientAge, PatientSex, StudyDate
        - license_short_name, series_size_MB

        Example queries:
        - "SELECT DISTINCT Modality, COUNT(*) FROM index GROUP BY Modality"
        - "SELECT SeriesInstanceUID, PatientID, Modality FROM index
           WHERE collection_id = 'rider_pilot' AND Modality = 'CT' LIMIT 10"

        Args:
            sql: SQL SELECT query against the IDC index table.
            max_rows: Maximum rows to return (default 50).

        Returns:
            Query results as formatted text.
        """
        # User-provided SQL can fail with syntax errors — expected.
        try:
            tic = time.time()
            result = self.talk2view_core.root.SlicerIDCBrowser_search(
                sql, max_rows
            )
            toc = time.time()
        except Exception as e:
            return log_and_return_error(e, f"SQL query failed: {e}")

        if "error" in result:
            return f"Error: {result['error']}"

        rows = result["rows"]
        if not rows:
            return "No results found."

        logging.info(
            "idc_search: %d/%d rows in %.2fs",
            result["showing"], result["total_rows"], toc - tic,
        )

        # UID columns are placed last so the chat preview (first 200
        # chars) shows human-readable fields first.
        _uid_columns = {
            "SeriesInstanceUID", "StudyInstanceUID", "SOPInstanceUID",
            "FrameOfReferenceUID",
        }

        lines = [
            f"**Results** (showing {result['showing']} "
            f"of {result['total_rows']}):\n"
        ]
        for i, row in enumerate(rows, 1):
            readable = []
            uids = []
            for k, v in row.items():
                if k in _uid_columns:
                    uids.append(f"{k}={v}")
                else:
                    readable.append(f"{k}={v}")
            parts = readable + uids
            lines.append(f"{i}. " + ", ".join(parts))

        return "\n".join(lines)

    def idc_download(self, series_instance_uid: str) -> str:
        """
        Download a DICOM series from IDC and load it into 3D Slicer.

        Composes IDC-specific download with the generic SlicerTools
        DICOM pipeline: download to temp dir, index into Slicer's DICOM
        database (with copy_files=True so the data survives temp dir
        cleanup), then load the series into the scene.

        Use idc_search first to find the SeriesInstanceUID you want.
        Note: Some series can be large. Check series_size_MB in search
        results before downloading.

        Args:
            series_instance_uid: The DICOM SeriesInstanceUID to download.

        Returns:
            Success or error message with loaded node names.
        """
        # Downloads can fail due to network errors, invalid UIDs — expected.
        try:
            logging.info(
                "idc_download: requesting series %s", series_instance_uid
            )
            tic = time.time()

            dl = self.talk2view_core.root.SlicerIDCBrowser_download_series(
                series_instance_uid
            )
            if not dl.get("success"):
                return f"Download failed: {dl.get('message', 'Unknown error')}"

            # copy_files=True: the IDC temp dir is ephemeral, so the
            # database needs its own copy of the bytes.
            imp = self.talk2view_core.root.import_dicom_directory(
                dl["directory"], True
            )
            if not imp.get("success"):
                return (
                    f"Downloaded {dl['file_count']} files but indexing failed: "
                    f"{imp.get('message', 'Unknown error')}"
                )

            ld = self.talk2view_core.root.load_dicom_series(
                series_instance_uid
            )
            toc = time.time()
        except Exception as e:
            return log_and_return_error(
                e, f"Error processing series '{series_instance_uid}': {e}"
            )

        if not ld.get("success"):
            return (
                f"Downloaded {dl['file_count']} files and indexed them, "
                f"but loading failed: {ld.get('message', 'Unknown error')}"
            )

        loaded = ld.get("loaded_node_names", [])
        logging.info(
            "idc_download: completed in %.2fs, loaded nodes: %s",
            toc - tic, loaded,
        )
        return (
            f"Downloaded {dl['file_count']} files. "
            f"Loaded: {', '.join(loaded)}"
        )

    def idc_get_collection_info(self, collection_id: str) -> str:
        """
        Get detailed metadata about a specific IDC collection.

        Shows modalities, body parts examined, patient counts, series
        counts, and total data size for the collection.

        Args:
            collection_id: IDC collection identifier (e.g. 'tcga_luad').

        Returns:
            Formatted collection summary.
        """
        tic = time.time()
        result = self.talk2view_core.root.SlicerIDCBrowser_get_collection_info(
            collection_id
        )
        toc = time.time()

        if "error" in result:
            return f"Error: {result['error']}"

        totals = result["totals"]
        logging.info(
            "idc_get_collection_info: %s (%d patients, %d series) in %.2fs",
            collection_id, totals["patients"], totals["series"],
            toc - tic,
        )

        lines = [
            f"**Collection: `{result['collection_id']}`**\n",
            f"- Patients: {totals['patients']}",
            f"- Studies: {totals['studies']}",
            f"- Series: {totals['series']}",
            f"- Total size: {totals['size_mb']} MB",
            "\n**Breakdown by modality and body part:**\n",
        ]

        for row in result["breakdown"]:
            modality = row.get("Modality", "N/A")
            body_part = row.get("BodyPartExamined", "N/A")
            lines.append(
                f"- {modality} / {body_part}: "
                f"{row['patients']} patients, "
                f"{row['series']} series, "
                f"{row['size_mb']} MB"
            )

        lines.append(
            "\n---\n"
            "*Use idc_search(sql) to query specific series, "
            "then idc_download(series_instance_uid) to load into Slicer.*"
        )
        return "\n".join(lines)
