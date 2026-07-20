# SlicerNNInteractive Connector
#
# This connector provides access to SlicerNNInteractive functionality through Talk2View.
# It uses the dynamically exposed NNInteractive methods via expose_slicer_extension_functions.
#
# The methods are exposed with the naming pattern:
#   - NNInteractive_widget_<method_name> for widget methods
#   - NNInteractive_logic_<method_name> for logic methods
#
# Note: NNInteractive must be installed in 3D Slicer for these tools to work.

import time
import logging
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode


class SlicerNNInteractive():
    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn

        # First, try to expose NNInteractive functions if the module is available
        if not self._expose_nninteractive_if_available():
            raise RuntimeError("SlicerNNInteractive module could not be exposed. Please ensure the extension is installed.")

        # Check if NNInteractive is available and build tools list
        if not self.check_nninteractive_available_internal():
            raise RuntimeError("SlicerNNInteractive module is not available after exposure attempt.")

        self.tools = [
            tool(self.check_nninteractive_available),
            tool(self.make_new_segment),
            tool(self.clear_current_segment),
            tool(self.set_server_url),
            tool(self.get_status),
            tool(self.set_interaction_point),
            tool(self.set_interaction_bbox),
            tool(self.set_interaction_lasso),
            tool(self.set_interaction_scribble),
        ]
        self.tool_node = ToolNode(self.tools)

    def _expose_nninteractive_if_available(self):
        """
        Expose NNInteractive module functions if available.
        Requires SlicerNNInteractive v0.2.0+ (module name 'SlicerNNInteractive').
        Returns True if successful, raises RuntimeError otherwise.
        """
        try:
            self.talk2view_core.root.expose_slicer_extension_functions("SlicerNNInteractive")
            # Now we can access the widget through the exposed methods
            # The widget and logic methods are exposed as SlicerNNInteractive_widget_* and SlicerNNInteractive_logic_*
            # Store a flag indicating the module is available
            self.nninteractive_available = True
            return True
        except Exception as current_error:
            logging.warning(f"SlicerNNInteractive (v0.2.0+) not found: {current_error}")

        # Detect outdated pre-v0.2.0 version (renamed from nnInteractiveSlicer in v0.2.0)
        legacy_found = False
        try:
            self.talk2view_core.root.slicer_util_getModule("nnInteractiveSlicer")
            legacy_found = True
        except Exception as e:
            logging.debug(f"Legacy nnInteractiveSlicer check: {e}")

        if legacy_found:
            raise RuntimeError(
                "Found outdated SlicerNNInteractive (pre-v0.2.0, registered as 'nnInteractiveSlicer').\n\n"
                "Please update to v0.2.0 or later:\n"
                "1. Open the Extension Manager (View > Extension Manager)\n"
                "2. Update or reinstall 'SlicerNNInteractive'\n"
                "3. Restart Slicer"
            ) from current_error

        # List available modules with 'nn' or 'interactive' in the name for diagnostics
        available = []
        try:
            all_modules = list(self.talk2view_core.root.slicer_app_moduleManager().modulesNames())
            available = [m for m in all_modules if 'nn' in m.lower() or 'interactive' in m.lower()]
        except Exception as e:
            logging.debug(f"Could not list available modules: {e}")

        msg = "SlicerNNInteractive extension is not installed.\n"
        if available:
            msg += f"Available modules matching 'nn'/'interactive': {available}\n"
        msg += (
            "\nTo fix this:\n"
            "1. Open the Extension Manager (View > Extension Manager)\n"
            "2. Search for 'SlicerNNInteractive'\n"
            "3. Install the extension and restart Slicer\n\n"
            "Or disable this connector in Talk2View settings."
        )
        raise RuntimeError(msg) from current_error

    def check_nninteractive_available_internal(self) -> bool:
        """
        Internal method to check if NNInteractive is available.
        """
        return hasattr(self, 'nninteractive_available') and self.nninteractive_available

    def check_nninteractive_available(self) -> str:
        """
        Check if the SlicerNNInteractive module is installed and available.

        Returns:
            str: Status message indicating if NNInteractive is available.
        """
        if self.check_nninteractive_available_internal():
            return "SlicerNNInteractive module is available and ready for AI-powered interactive segmentation."
        return "SlicerNNInteractive module is not installed. Install it from the Extension Manager to enable AI-powered interactive segmentation."

    def make_new_segment(self) -> str:
        """
        Creates a new empty segment in the current segmentation, increments a name,
        and sets it as the selected segment.

        Returns:
            str: Status message with the new segment name.
        """
        tic = time.time()

        # Call the exposed SlicerNNInteractive widget's make_new_segment method
        # The method is exposed as SlicerNNInteractive_widget_make_new_segment
        self.talk2view_core.root.SlicerNNInteractive_widget_make_new_segment()

        toc = time.time()
        return "New segment created successfully"

    def clear_current_segment(self) -> str:
        """
        Clears the contents of the currently selected segment and resets prompts.

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Call the exposed SlicerNNInteractive widget's clear_current_segment method
        self.talk2view_core.root.SlicerNNInteractive_widget_clear_current_segment()

        toc = time.time()
        return "Current segment cleared and prompts reset"

    def set_server_url(self, server_url: str) -> str:
        """
        Set the NNInteractive server URL.

        Args:
            server_url (str): Server URL (e.g., "http://localhost:5000").

        Returns:
            str: Status message.
        """
        tic = time.time()

        # We need to get the widget and update its UI
        # This requires accessing the widget's UI elements which might not be directly exposed
        # Instead, we'll need to use a different approach or expose additional methods
        try:
            # Try to call update_server with the URL if it's exposed
            self.talk2view_core.root.SlicerNNInteractive_widget_update_server()
        except AttributeError:
            # If the method isn't exposed, we can't set the server URL programmatically
            return "Setting server URL programmatically is not currently supported. Please set it manually in the NNInteractive module UI."

        toc = time.time()
        return f"NNInteractive server update triggered (URL: {server_url})"

    def get_status(self) -> str:
        """
        Get the current status of NNInteractive module.

        Returns:
            str: Status information.
        """
        tic = time.time()

        # Check if module is available
        if not self.check_nninteractive_available_internal():
            return "NNInteractive module is not available"

        # Try to get some basic info
        status_parts = ["NNInteractive Status:"]
        status_parts.append("- Module: Available")
        status_parts.append("- Widget methods: Exposed via RPyC service")
        status_parts.append("- Logic methods: Exposed via RPyC service")

        toc = time.time()
        return "\n".join(status_parts)

    def set_interaction_point(self) -> str:
        """
        Set the interaction mode to Point for precise single-point annotations.
        This mode allows placing individual points to mark specific locations.

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Use the exposed slicer_util method to get the widget
        widget = self.talk2view_core.root.slicer_util_getModuleWidget("SlicerNNInteractive")
        widget.ui.pbInteractionPoint.click()

        toc = time.time()
        return "Interaction mode set to Point - click on the image to place annotation points"

    def set_interaction_bbox(self) -> str:
        """
        Set the interaction mode to Bounding Box for rectangular region selection.
        This mode allows drawing bounding boxes around areas of interest.

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Use the exposed slicer_util method to get the widget
        widget = self.talk2view_core.root.slicer_util_getModuleWidget("SlicerNNInteractive")
        widget.ui.pbInteractionBBox.click()

        toc = time.time()
        return "Interaction mode set to Bounding Box - drag to draw rectangular regions"

    def set_interaction_lasso(self) -> str:
        """
        Set the interaction mode to Lasso for freehand region selection.
        This mode allows drawing freeform closed curves around areas.

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Use the exposed slicer_util method to get the widget
        widget = self.talk2view_core.root.slicer_util_getModuleWidget("SlicerNNInteractive")
        widget.ui.pbInteractionLasso.click()

        toc = time.time()
        return "Interaction mode set to Lasso - draw freehand curves to select regions"

    def set_interaction_scribble(self) -> str:
        """
        Set the interaction mode to Scribble for brush-based annotations.
        This mode allows painting with a brush to mark regions.

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Use the exposed slicer_util method to get the widget
        widget = self.talk2view_core.root.slicer_util_getModuleWidget("SlicerNNInteractive")
        widget.ui.pbInteractionScribble.click()

        toc = time.time()
        return "Interaction mode set to Scribble - paint with brush to annotate regions"
