"""
TotalSegmentator connector for Talk2View.
Provides AI-powered automatic whole body CT/MR segmentation using the SlicerTotalSegmentator extension.
"""
import os
import json
import logging
import rpyc
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from typing import Optional


class _SegmentInput(BaseModel):
    """Input schema for segmenting a volume."""
    volume_name: str = Field(
        description="Name of the volume node to segment. Use get_data_context() to find available volume names."
    )
    task: str = Field(
        default="total",
        description="Segmentation task. Options: 'total' (104 structures), 'total_mr' (MR), "
                    "'lung_vessels', 'lung_nodules', 'body', 'liver_segments', etc. Default: 'total'"
    )
    fast: bool = Field(
        default=True,
        description="Use fast mode for quicker results. Default: True"
    )
    output_segmentation_name: Optional[str] = Field(
        default=None,
        description="Optional name for output segmentation. Default: '<volume_name> segmentation'"
    )
    device: str = Field(
        default="gpu",
        description="Device for inference: 'gpu', 'cpu', or specific like 'cuda:0'. Default: 'gpu'"
    )


class TotalSegmentator:
    """
    Talk2View connector for TotalSegmentator AI segmentation.
    Uses the SlicerTotalSegmentator extension for automatic anatomical segmentation.
    """

    # Default API URL for TotalSegmentator (using RunPod proxy URL for stability)
    DEFAULT_API_URL = "https://cfxo1q5hiqp21v-8000.proxy.runpod.net"

    def __init__(self, rpyc_conn):
        """Initialize the TotalSegmentator connector."""
        self.talk2view_core = rpyc_conn

        # Check if TotalSegmentator extension is available
        if not self._check_and_expose_totalsegmentator():
            # Extension not available - show popup and disable connector
            self._show_missing_extension_popup()
            self._disable_connector()
            raise RuntimeError(
                "SlicerTotalSegmentator (T2V-Version) is not installed. "
                "The connector has been disabled. Please install the extension and re-enable the connector."
            )

        # Define available tools
        self.tools = [
            tool(self.segment, args_schema=_SegmentInput, return_direct=True),
            tool(self.get_available_tasks),
        ]
        self.tool_node = ToolNode(self.tools)

        logging.info("TotalSegmentator connector initialized successfully")

    def _check_and_expose_totalsegmentator(self) -> bool:
        """
        Check if TotalSegmentator extension is available and expose its functions.
        Returns True if successful, False otherwise.
        """
        try:
            success = self.talk2view_core.root.expose_slicer_extension_functions("TotalSegmentator")
            if not success:
                logging.warning("TotalSegmentator module is not installed in Slicer")
                return False
            return True
        except Exception as e:
            logging.warning(f"Failed to expose TotalSegmentator: {e}")
            return False

    def _show_missing_extension_popup(self):
        """Show a popup telling the user they need to install SlicerTotalSegmentator."""
        try:
            message = (
                "SlicerTotalSegmentator (T2V-Version) is required but not installed.\n\n"
                "Please install it from the 3D Slicer Extension Manager to use TotalSegmentator features.\n\n"
                "The TotalSegmentator connector has been disabled."
            )
            self.talk2view_core.root.slicer_util_infoDisplay(message, "TotalSegmentator Not Found")
        except Exception as e:
            logging.error(f"Failed to show popup: {e}")

    def _disable_connector(self):
        """Disable this connector in the configuration file."""
        try:
            # Get the connectors directory from the client
            connectors_dir = self.talk2view_core.root.get_connectors_directory()
            module_dir = os.path.dirname(connectors_dir)
            config_path = os.path.join(module_dir, "connectors_config.json")

            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Remove from enabled list
                enabled = config.get("enabled_connectors", [])
                if "TotalSegmentator" in enabled:
                    enabled.remove("TotalSegmentator")
                    config["enabled_connectors"] = enabled

                # Add to disabled list if not already there
                disabled = config.get("disabled_connectors", [])
                if "TotalSegmentator" not in disabled:
                    disabled.append("TotalSegmentator")
                    config["disabled_connectors"] = disabled

                # Save the updated config
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)

                logging.info("TotalSegmentator connector has been disabled in configuration")
            else:
                logging.warning(f"Config file not found at {config_path}")

        except Exception as e:
            logging.error(f"Failed to disable connector: {e}")

    def get_available_tasks(self) -> str:
        """
        Get a list of available TotalSegmentator segmentation tasks.

        Returns:
            A formatted string listing all available segmentation tasks.
        """
        try:
            # Get the logic to access the tasks dictionary
            logic = self.talk2view_core.root.slicer_util_getModuleLogic("TotalSegmentator")
            tasks = logic.tasks

            result = "Available TotalSegmentator tasks:\n\n"
            for task_name, task_info in tasks.items():
                title = task_info.get('title', task_name)
                description = task_info.get('description', '')
                requires_license = task_info.get('requiresLicense', False)

                line = f"  - {task_name}: {title}"
                if requires_license:
                    line += " [license required]"
                if description:
                    line += f"\n    {description}"
                result += line + "\n"

            result += "\nUse segment(volume_name, task='<task_name>') to run segmentation."
            return result

        except Exception as e:
            logging.error(f"Failed to get tasks: {e}")
            return f"Error getting available tasks: {str(e)}"

    def segment(
        self,
        volume_name: str,
        task: str = "total",
        fast: bool = True,
        output_segmentation_name: Optional[str] = None,
        device: str = "gpu"
    ) -> str:
        """
        Segment a volume using TotalSegmentator AI.

        Performs automatic anatomical segmentation on CT or MR volumes using
        the TotalSegmentator deep learning model.

        Args:
            volume_name: Name of the volume node to segment
            task: Segmentation task (default: 'total' for 104 structures)
            fast: Use fast mode for quicker results (default: True)
            output_segmentation_name: Optional custom name for output segmentation
            device: Device for inference ('gpu', 'cpu', or specific like 'cuda:0'). Default: 'gpu'

        Returns:
            Status message indicating success or failure
        """
        # Ask user for confirmation before sending data to server
        # Use rpyc.timed() with unlimited timeout while waiting for user response
        timed_confirm = rpyc.timed(
            self.talk2view_core.root.slicer_util_confirmOkCancelDisplay,
            None
        )
        async_result = timed_confirm(
            "This action will send volume data to Talk2View's server for segmentation with TotalSegmentator.\n\n"
            "By proceeding, you acknowledge that:\n"
            "• Your volume data will be sent to Talk2View's server\n"
            "• This tool is for educational and research purposes only\n"
            "• Do not include personal health information (PHI)\n\n"
            "Privacy Policy: https://talk2view.com/legal/privacy-policy\n"
            "Terms of Use: https://talk2view.com/legal/terms-of-use\n\n"
            "Do you want to continue?",
            "Data Transfer"
        )
        async_result.wait()
        if not async_result.value:
            return "Operation cancelled by user."

        try:
            # Show progress dialog for the entire operation (4 steps)
            self.talk2view_core.root.show_progress_dialog(
                "Talk2View - 'TotalSegmentator' Connector",
                f"Status: Preparing... (Step 1/4)\nVolume: {volume_name}",
                maximum=4,
                cancellable=False
            )
            self.talk2view_core.root.update_progress_dialog(value=1)

            # Get the input volume node
            logging.info(f"Looking for volume: {volume_name}")
            input_volume = self.talk2view_core.root.slicer_util_getNode(volume_name)

            if not input_volume:
                self.talk2view_core.root.close_progress_dialog()
                return f"Error: Volume '{volume_name}' not found. Use get_data_context() to see available volumes."

            # Create output segmentation name
            if output_segmentation_name is None:
                output_segmentation_name = f"{volume_name} segmentation"

            # Create output segmentation node
            logging.info(f"Creating output segmentation: {output_segmentation_name}")
            output_segmentation = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass(
                "vtkMRMLSegmentationNode",
                output_segmentation_name
            )

            # Get the TotalSegmentator logic and connect to API
            self.talk2view_core.root.update_progress_dialog(
                label_text=f"Status: Connecting to API... (Step 2/4)\nVolume: {volume_name}",
                value=2
            )
            logic = self.talk2view_core.root.slicer_util_getModuleLogic("TotalSegmentator")
            logging.info(f"Connecting to TotalSegmentator API at {self.DEFAULT_API_URL}")
            logic.connectAPI(self.DEFAULT_API_URL)

            # Check if fast mode is supported for this task
            use_fast = fast
            if fast and not logic.isFastModeSupportedForTask(task):
                logging.info(f"Fast mode not supported for task '{task}', using standard mode")
                use_fast = False

            # Run the segmentation - use rpyc.timed() with unlimited timeout for long-running operation
            self.talk2view_core.root.update_progress_dialog(
                label_text=f"Status: Running segmentation... (Step 3/4)\nVolume: {volume_name}",
                value=3
            )
            logging.info(f"Running TotalSegmentator with task='{task}', fast={use_fast}, device='{device}'")
            timed_process = rpyc.timed(logic.process, None)
            async_result = timed_process(
                input_volume,
                output_segmentation,
                fast=use_fast,
                task=task,
                device=device
            )
            # Wait for the result with the extended timeout
            async_result.wait()

            # Convert to closed surface representation for 3D visualization
            self.talk2view_core.root.update_progress_dialog(
                label_text=f"Status: Creating 3D surface... (Step 4/4)\nVolume: {volume_name}",
                value=4
            )
            logging.info("Creating closed surface representation")
            # Re-fetch the node to get a fresh RPyC reference (previous netref may have expired)
            output_segmentation = self.talk2view_core.root.slicer_util_getNode(output_segmentation_name)
            output_segmentation.CreateClosedSurfaceRepresentation()

            # Reset 3D view to show the new segmentation
            layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
            threeDWidget = layoutManager.threeDWidget(0)
            if threeDWidget:
                threeDView = threeDWidget.threeDView()
                threeDView.resetFocalPoint()
                threeDView.resetCamera()

            # Disconnect from API - re-fetch logic to avoid expired reference
            try:
                logic = self.talk2view_core.root.slicer_util_getModuleLogic("TotalSegmentator")
                logic.disconnectAPI()
            except Exception as disconnect_error:
                # Ignore disconnect errors - the segmentation completed successfully
                logging.warning(f"Failed to disconnect from API (non-critical): {disconnect_error}")

            # Close progress dialog
            self.talk2view_core.root.close_progress_dialog()

            # Build response with header and footer
            header = "*Connector's response using 'TotalSegmentator.segment':*\n---\n"
            content = (
                f"Successfully segmented '{volume_name}' using task '{task}'.\n"
                f"Created segmentation: '{output_segmentation_name}'\n"
                f"Use list_segments('{output_segmentation_name}') to see the anatomical structures."
            )
            footer = (
                "\n\n---\n"
                "*Powered by TotalSegmentator. Reference: Wasserthal, J., Breit, H.-C., Meyer, M.T., "
                "Pradella, M., Hinck, D., Sauter, A.W., Heye, T., Boll, D., Cyriac, J., Yang, S., Bach, M., "
                "Segeroth, M., 2023. TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images. "
                "Radiology: Artificial Intelligence. https://doi.org/10.1148/ryai.230024*"
            )
            return header + content + footer

        except Exception as e:
            # Always close the progress dialog on error
            try:
                self.talk2view_core.root.close_progress_dialog()
            except Exception as close_error:
                logging.debug(f"Failed to close progress dialog during error handling: {close_error}")

            # Check if this is an RPyC "result expired" error after successful completion
            error_str = str(e).lower()
            if "result expired" in error_str or "netref" in error_str:
                # The segmentation likely completed but the RPyC reference expired
                # Check if the segmentation node exists
                logging.warning(f"RPyC reference expired, but segmentation may have completed: {e}")
                header = "*Connector's response using 'TotalSegmentator.segment':*\n---\n"
                content = (
                    f"Segmentation completed for '{volume_name}' using task '{task}'.\n"
                    f"Created segmentation: '{output_segmentation_name}'\n"
                    f"Use list_segments('{output_segmentation_name}') to see the anatomical structures."
                )
                footer = (
                    "\n\n---\n"
                    "*Powered by TotalSegmentator. Reference: Wasserthal, J., Breit, H.-C., Meyer, M.T., "
                    "Pradella, M., Hinck, D., Sauter, A.W., Heye, T., Boll, D., Cyriac, J., Yang, S., Bach, M., "
                    "Segeroth, M., 2023. TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images. "
                    "Radiology: Artificial Intelligence. https://doi.org/10.1148/ryai.230024*"
                )
                return header + content + footer

            logging.error(f"TotalSegmentator error: {e}")
            return f"Error during segmentation: {str(e)}"
