"""
SlicerSampleData connector for Talk2View.
Provides access to 3D Slicer's built-in sample datasets with intelligent name resolution.
"""
import logging
import rpyc
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from utils.connector_base import log_and_return_error


class _DownloadSampleDataInput(BaseModel):
    """Input schema for downloading sample data."""
    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(
        description="Name or description of the dataset to download. Examples: 'MRHead', 'CT Chest', 'head and neck atlas', 'brain MRI'"
    )


class SlicerSampleData:
    """
    Talk2View connector for 3D Slicer's SampleData module.
    Uses a LangGraph workflow to intelligently resolve dataset names before downloading.
    """

    # Timeout for download operations (5 minutes)
    DOWNLOAD_TIMEOUT = 300

    def __init__(self, rpyc_conn):
        """Initialize the SlicerSampleData connector."""
        self.talk2view_core = rpyc_conn
        self.llm = None
        self._cached_datasets = None  # Cache dataset list

        self.tools = [
            tool(self.list_sample_data),
            tool(self.download_sample_data, args_schema=_DownloadSampleDataInput),
        ]
        self.tool_node = ToolNode(self.tools)

        logging.info("SlicerSampleData connector initialized")

    def set_llm(self, llm):
        """Set the LLM instance from Talk2View Core."""
        self.llm = llm

    def _get_available_datasets(self) -> dict:
        """Get available datasets from Slicer's SampleData module.

        Returns:
            Dict mapping dataset names to their descriptions.
        """
        if self._cached_datasets is not None:
            return self._cached_datasets

        logic = self.talk2view_core.root.slicer_util_getModuleLogic("SampleData")
        sources_by_category = logic.sampleDataSourcesByCategory()

        datasets = {}
        for category, sources in sources_by_category.items():
            for source in sources:
                name = source.sampleName
                description = getattr(source, 'sampleDescription', '') or ''
                datasets[name] = {
                    'category': category,
                    'description': description
                }

        self._cached_datasets = datasets
        return datasets

    def _format_dataset_list(self, datasets: dict) -> str:
        """Format dataset list for LLM consumption."""
        lines = []
        for name, info in datasets.items():
            desc = info['description']
            if desc:
                lines.append(f"- {name}: {desc}")
            else:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def list_sample_data(self) -> str:
        """
        List all available sample datasets from 3D Slicer's SampleData module.

        Returns:
            A formatted string listing available samples grouped by category.
        """
        logic = self.talk2view_core.root.slicer_util_getModuleLogic("SampleData")
        sources_by_category = logic.sampleDataSourcesByCategory()

        content = ""
        item_num = 1
        for category, sources in sources_by_category.items():
            content += f"**{category}:**\n"
            for source in sources:
                name = source.sampleName
                description = getattr(source, 'sampleDescription', '') or ''
                content += f"  {item_num}. `{name}`"
                if description:
                    content += f" - {description}"
                content += "\n"
                item_num += 1
            content += "\n"

        footer = (
            "---\n"
            "*Sample datasets provided by 3D Slicer's SampleData module. "
            "Use download_sample_data(dataset) to load a dataset.*\n\n"
            "*When presenting options to the user, use numbered lists so they can select by number.*"
        )

        return content + footer

    def download_sample_data(self, dataset: str) -> str:
        """
        Download and load a sample dataset into the scene.

        Uses an intelligent workflow to resolve the dataset name, handling variations
        like 'head and neck atlas' -> 'SPL_Head_and_Neck_Atlas'.

        Args:
            dataset: Name or description of the dataset (e.g., 'MRHead', 'head neck atlas', 'brain MRI')

        Returns:
            Success or error message.
        """
        try:
            logging.info(f"Download request for dataset: '{dataset}'")

            # If no LLM, fall back to direct download (legacy behavior)
            if not self.llm:
                logging.info("LLM not available, using direct download (legacy mode)")
                return self._direct_download(dataset)

            # Use workflow for intelligent name resolution
            logging.info("Using LLM-assisted name resolution")
            return self._workflow_download(dataset)

        except Exception as e:
            return log_and_return_error(e, f"Error downloading '{dataset}': {e}")

    def _direct_download(self, dataset: str) -> str:
        """Direct download without LLM name resolution (legacy behavior)."""
        try:
            logic = self.talk2view_core.root.slicer_util_getModuleLogic("SampleData")

            timed_download = rpyc.timed(logic.downloadSample, self.DOWNLOAD_TIMEOUT)
            async_result = timed_download(dataset)
            async_result.wait()
            result = async_result.value

            if result is None:
                logging.warning(f"Dataset '{dataset}' not found in direct download")
                return f"Error: Dataset '{dataset}' not found. Use list_sample_data() to see available options."

            # Get loaded node names
            if isinstance(result, list):
                node_names = [node.GetName() for node in result if node]
            else:
                node_names = [result.GetName()] if result else []

            logging.info(f"Direct download complete. Loaded nodes: {node_names}")

            header = "*Connector's response using 'SlicerSampleData.download_sample_data':*\n---\n"

            if node_names:
                content = f"Successfully downloaded `{dataset}`.\n\nLoaded nodes: {', '.join(node_names)}"
            else:
                content = f"Successfully downloaded `{dataset}`."

            footer = "\n\n---\n*Sample datasets provided by 3D Slicer's SampleData module.*"

            return header + content + footer

        except Exception as e:
            return log_and_return_error(e, f"Error downloading '{dataset}': {e}")

    def _workflow_download(self, user_request: str) -> str:
        """Download using LangGraph workflow with intelligent name resolution."""
        try:
            llm = self.llm

            # Get available datasets
            datasets = self._get_available_datasets()
            dataset_list = self._format_dataset_list(datasets)
            dataset_names = list(datasets.keys())
            logging.debug(f"Available datasets: {len(dataset_names)} datasets found")

            # Check if user_request is already an exact match
            if user_request in dataset_names:
                # Skip LLM resolution for exact matches
                resolved_name = user_request
                logging.info(f"Exact match found: '{user_request}'")
            else:
                # Use LLM to resolve the name
                logging.info(f"No exact match for '{user_request}', invoking LLM for resolution")
                resolve_prompt = f"""Given the user's request: "{user_request}"

Find the EXACT dataset name from this list that best matches their request:

{dataset_list}

Rules:
1. Return ONLY the exact dataset name, nothing else
2. Match based on meaning, not just exact text (e.g., "head and neck atlas" matches "SPL_Head_and_Neck_Atlas")
3. If no good match exists, return "NOT_FOUND"

Dataset name:"""

                response = llm.invoke(resolve_prompt)
                resolved_name = response.content.strip()
                logging.debug(f"LLM raw response: '{resolved_name}'")

                # Clean up the response (remove quotes, extra text)
                resolved_name = resolved_name.strip('"\'`')
                if '\n' in resolved_name:
                    resolved_name = resolved_name.split('\n')[0].strip()
                logging.info(f"LLM resolved '{user_request}' to '{resolved_name}'")

            # Validate the resolved name
            if resolved_name == "NOT_FOUND" or resolved_name not in dataset_names:
                logging.info(f"LLM resolution failed or invalid, trying fuzzy match")
                # Try fuzzy matching as fallback
                resolved_name = self._fuzzy_match(user_request, dataset_names)
                if resolved_name:
                    logging.info(f"Fuzzy match found: '{resolved_name}'")
                else:
                    logging.warning(f"No match found for '{user_request}'")

            if not resolved_name:
                return (
                    f"Error: Could not find a dataset matching '{user_request}'.\n\n"
                    f"Use list_sample_data() to see available options."
                )

            # Download the resolved dataset
            logging.info(f"Downloading dataset: '{resolved_name}'")

            logic = self.talk2view_core.root.slicer_util_getModuleLogic("SampleData")
            timed_download = rpyc.timed(logic.downloadSample, self.DOWNLOAD_TIMEOUT)
            async_result = timed_download(resolved_name)
            async_result.wait()
            result = async_result.value

            if result is None:
                logging.error(f"Download returned None for '{resolved_name}'")
                return f"Error: Failed to download '{resolved_name}'. The dataset may be unavailable."

            # Get loaded node names
            if isinstance(result, list):
                node_names = [node.GetName() for node in result if node]
            else:
                node_names = [result.GetName()] if result else []

            logging.info(f"Download complete. Loaded nodes: {node_names}")

            # Build response
            header = "*Connector's response using 'SlicerSampleData.download_sample_data':*\n---\n"

            content = f"Successfully downloaded `{resolved_name}`."
            if user_request.lower() != resolved_name.lower():
                content = f"Resolved '{user_request}' to `{resolved_name}`.\n\n{content}"

            if node_names:
                content += f"\n\nLoaded nodes: {', '.join(node_names)}"

            footer = "\n\n---\n*Sample datasets provided by 3D Slicer's SampleData module.*"

            return header + content + footer

        except Exception as e:
            return log_and_return_error(e, f"Error downloading '{user_request}': {e}")

    def _fuzzy_match(self, user_request: str, dataset_names: List[str]) -> Optional[str]:
        """Simple fuzzy matching as fallback when LLM resolution fails."""
        user_lower = user_request.lower().replace('_', ' ').replace('-', ' ')
        user_words = set(user_lower.split())

        best_match = None
        best_score = 0

        for name in dataset_names:
            name_lower = name.lower().replace('_', ' ').replace('-', ' ')
            name_words = set(name_lower.split())

            # Calculate word overlap
            common = len(user_words & name_words)
            if common > best_score:
                best_score = common
                best_match = name

            # Also check substring match
            if user_lower in name_lower or name_lower in user_lower:
                return name

        # Only return if we have at least 1 word match
        return best_match if best_score >= 1 else None
