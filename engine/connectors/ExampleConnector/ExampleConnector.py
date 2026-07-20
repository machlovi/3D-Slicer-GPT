"""
ExampleConnector -- A fully commented starter template for Talk2View connectors.

=== ARCHITECTURE OVERVIEW ===

A connector is a Python class that runs inside Talk2View Core (a separate process
from 3D Slicer). The AI model decides which tool functions to call based on the
user's request. Each tool function runs here in Core, and can call back into
Slicer via RPyC (Remote Python Call) to read/modify the scene.

    User  -->  AI Model  -->  [your tool function]  -->  RPyC  -->  3D Slicer

=== NAMING RULE ===

The directory name, .py filename, and class name MUST all match exactly:
    ExampleConnector/ExampleConnector.py  -->  class ExampleConnector

=== GETTING STARTED ===

1. Duplicate this connector (use the Duplicate button) and give it a new name
2. Enable your copy in Browse Connectors (Settings panel)
3. Edit the tools to do what you need
4. Start a chat -- the AI will see your tools and can call them
"""
import logging
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode


# ---------------------------------------------------------------------------
# INPUT SCHEMAS
# ---------------------------------------------------------------------------
# Each tool that takes arguments needs a Pydantic model defining its inputs.
# The AI reads the Field descriptions to understand what to pass, so write
# them clearly. Tools with no arguments don't need a schema.

class _HelloInput(BaseModel):
    """Input schema for the hello tool."""
    name: str = Field(description="The name to greet. Example: 'Alice'")


# ---------------------------------------------------------------------------
# CONNECTOR CLASS
# ---------------------------------------------------------------------------

class ExampleConnector:
    """
    Example Talk2View connector with two demo tools.

    This connector is disabled by default. Enable it in Browse Connectors
    (Settings) to try it out, then duplicate it to start your own.
    """

    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn

        # -----------------------------------------------------------------
        # TOOL REGISTRATION
        # -----------------------------------------------------------------
        # List every tool the AI can call. The tool() wrapper registers
        # each method. Use args_schema to define typed inputs.
        #
        # return_direct=True  -> The tool's return string goes straight to the
        #                        user without the AI rephrasing it.
        # return_direct=False -> (default) The AI reads the result and decides
        #                        how to present it.

        self.tools = [
            tool(self.hello, args_schema=_HelloInput, return_direct=True),
            tool(self.get_slicer_version),
        ]
        self.tool_node = ToolNode(self.tools)

        logging.info("ExampleConnector initialized")

    # -----------------------------------------------------------------
    # TOOL FUNCTIONS
    # -----------------------------------------------------------------
    # Rules for tool functions:
    # 1. Return a string -- this is what the AI (or user) sees
    # 2. Never raise exceptions -- return error strings instead
    # 3. Only catch specific, expected exceptions (e.g. ValueError for
    #    bad user input). Never use bare except: or except Exception:.
    # 4. If there's no expected user error, don't add try/except --
    #    let bugs crash loudly so they get fixed.
    # 5. The docstring is shown to the AI as the tool description

    def hello(self, name: str = "World") -> str:
        """
        Return a friendly greeting. This is a minimal example tool that
        doesn't interact with Slicer.

        Args:
            name: The name to greet.

        Returns:
            A greeting string.
        """
        return f"Hello, {name}! This response came from ExampleConnector."

    def get_slicer_version(self) -> str:
        """
        Get the 3D Slicer application version. Demonstrates calling Slicer
        via RPyC.

        Returns:
            The Slicer version string.
        """
        # RPyC call pattern: self.talk2view_core.root.<method>(args)
        # Core exposes methods that run inside Slicer's Python environment.
        #
        # Common methods:
        #   slicer_eval("slicer.app.applicationVersion")
        #   slicer_util_getNodesByClass('vtkMRMLSegmentationNode')
        #   slicer_util_getModuleLogic("SampleData")
        #
        # Pass only simple types (str, int, list, dict) across RPyC.
        # Returned objects are RPyC proxies -- access attributes normally.

        version = self.talk2view_core.root.slicer_eval(
            "slicer.app.applicationVersion"
        )
        return f"3D Slicer version: {version}"


# ---------------------------------------------------------------------------
# OPTIONAL FEATURES (not used in this example)
# ---------------------------------------------------------------------------
#
# set_llm(self, llm):
#     Implement this method if your connector needs to make its own LLM calls
#     (e.g. for multi-step workflows, summarization, or name resolution).
#     See the SlicerSampleData connector for an example.
#
# ConnectorBase:
#     If your connector needs pip packages that aren't already installed,
#     inherit from ConnectorBase instead of writing a plain class:
#
#       from utils.connector_base import ConnectorBase
#
#       class MyConnector(ConnectorBase):
#           REQUIRED_PACKAGES = ["some-package>=1.0.0"]
#
#           def __init__(self, rpyc_conn):
#               super().__init__(rpyc_conn)  # auto-installs missing packages
#               ...
#
#     See utils/connector_base.py for full documentation.
