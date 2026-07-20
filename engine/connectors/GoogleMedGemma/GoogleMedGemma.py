# GoogleMedGemma Connector
#
# This connector provides access to GoogleMedGemma functionality through Talk2View.

import time
import logging
import json
import requests
import base64
import rpyc
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing import Literal

from utils.connector_base import log_and_return_error

# Pydantic schemas for tool inputs - not to be instantiated as tools
class _AskMedGemmaInput(BaseModel):
    """Input schema for asking MedGemma a text-only question."""
    message: str = Field(description="The medical question or query to send to MedGemma.")
    model: Literal["mlx-community/medgemma-27b-it-8bit", "mlx-community/medgemma-4b-it-8bit"] = Field(
        default="mlx-community/medgemma-27b-it-8bit",
        description="The MedGemma model to use. Options: 'mlx-community/medgemma-27b-it-8bit' (larger, more capable), 'mlx-community/medgemma-4b-it-8bit' (smaller, faster)"
    )

class _AskMedGemmaImageInput(BaseModel):
    """Input schema for asking MedGemma a question with a screenshot of the current view."""
    message: str = Field(description="The medical question or query about the current medical scans or 3D model displayed in the Slicer view.")
    model: Literal["mlx-community/medgemma-27b-it-8bit", "mlx-community/medgemma-4b-it-8bit"] = Field(
        default="mlx-community/medgemma-27b-it-8bit",
        description="The MedGemma model to use. Options: 'mlx-community/medgemma-27b-it-8bit' (larger, more capable), 'mlx-community/medgemma-4b-it-8bit' (smaller, faster)"
    )

class GoogleMedGemma():
    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn
        self.supabase_manager = None

        # ask_medgemma is always available (text-only)
        self.tools = [
            tool(self.ask_medgemma, args_schema=_AskMedGemmaInput, return_direct=True)
        ]

        # Add screenshot tool if ScreenCapture module is available
        if self._expose_screen_capture_if_available():
            self.tools.append(tool(self.ask_medgemma_image, args_schema=_AskMedGemmaImageInput, return_direct=True))
        else:
            msg = "GoogleMedGemma: ScreenCapture module not available. ask_medgemma_image disabled."
            logging.warning(msg)

        self.tool_node = ToolNode(self.tools)
    
    def set_supabase_manager(self, supabase_manager):
        """Set the supabase manager instance for API key access."""
        self.supabase_manager = supabase_manager

    def _expose_screen_capture_if_available(self):
        """
        Expose screen capture module functions if available.
        This needs to be done before we can use the dynamically exposed methods.
        Returns True if successful, raises RuntimeError otherwise.
        """
        if self.talk2view_core.root.expose_slicer_extension_functions("ScreenCapture"):
            return True
        else:
            logging.error(f"Failed to expose ScreenCapture.")
            return False

    def ask_medgemma(self, message: str, model: str = "mlx-community/medgemma-27b-it-8bit") -> str:
        """
        Sends a text query to Google's MedGemma model. Use this tool when the user says "Ask MedGemma..." followed by a general medical question that does NOT require looking at the current screen, scans, or 3D model. This is for text-only medical questions like asking about conditions, symptoms, treatments, or medical concepts.

        Examples of when to use this tool:
        - "Ask MedGemma what are the symptoms of appendicitis?"
        - "Ask MedGemma to explain what a CT scan shows"

        Do NOT use this tool if the user wants MedGemma to look at or analyze the current view/image - use ask_medgemma_image instead.
        """
        # Ask user for confirmation before sending data to server
        # Use rpyc.timed() with unlimited timeout while waiting for user response
        timed_confirm = rpyc.timed(
            self.talk2view_core.root.slicer_util_confirmOkCancelDisplay,
            None
        )
        async_result = timed_confirm(
            "This action will send your query to Talk2View's server for processing with MedGemma.\n\n"
            "By proceeding, you acknowledge that:\n"
            "• Your data will be sent to Talk2View's server\n"
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

        tic = time.time()

        try:
            # Get API key from supabase manager
            if not self.supabase_manager:
                return "GoogleMedGemma.ask_medgemma: No API key available - connector not properly initialized"

            api_key = self.supabase_manager.get_litellm_api_key()
            if not api_key:
                return "GoogleMedGemma.ask_medgemma: No API key found for user"

            url = f"https://t2v4-staging.talk2view.com/chat/completions"
            headers = {
                'Content-Type': 'application/json',
                'x-litellm-api-key': f"Bearer {api_key}"
            }
            data = {
                "model": f"openai/{model}",
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "max_tokens": 1024
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            logging.debug(f"MedGemma API response: {result}")

            # Extract message content from the API response
            choices = result.get('choices', [])
            if not choices:
                return "GoogleMedGemma.ask_medgemma: No response from MedGemma server"

            message_content = choices[0].get('message', {}).get('content', '')

            if not message_content:
                return "GoogleMedGemma.ask_medgemma: Empty response from MedGemma server"

            # Get the actual model name from the response
            model_used = result.get('model', model)

            # Add header
            header = f"*Connector's response using 'GoogleMedGemma.ask_medgemma':*\n---\n"

            # Add disclaimer footer
            disclaimer = f"\n\n---\n*The information above was generated using {model_used} by Google. This is an AI-generated analysis and should not be used as a substitute for professional medical advice.*"

            toc = time.time()
            logging.info(f"GoogleMedGemma.ask_medgemma executed in {toc - tic:.4f} seconds")
            return header + message_content + disclaimer

        except requests.exceptions.RequestException as e:
            toc = time.time()
            return log_and_return_error(e, f"Failed in {toc - tic:.4f}s. Failed to send query to MedGemma server: {str(e)}")

    def ask_medgemma_image(self, message: str, model: str = "mlx-community/medgemma-27b-it-8bit") -> str:
        """
        Captures a screenshot of the current scan/view/model and sends it to Google's MedGemma Model. Use this tool when the user says "Ask MedGemma..." and wants MedGemma to look at, analyze, or comment on the current view, medical scans, or 3D model.

        Examples of when to use this tool:
        - "Ask MedGemma what do you see in this scan?"
        - "Ask MedGemma to analyze this image"
        - "Ask MedGemma what abnormalities are visible here?"

        Use this tool whenever the user's question implies MedGemma should SEE or LOOK AT the current view, medical scans, or 3D model. Use ask_medgemma (without image) for general medical questions that don't need visual context.
        """
        # Ask user for confirmation before sending data to server
        # Use rpyc.timed() with unlimited timeout while waiting for user response
        timed_confirm = rpyc.timed(
            self.talk2view_core.root.slicer_util_confirmOkCancelDisplay,
            None
        )
        async_result = timed_confirm(
            "This action will capture a screenshot and send it along with your query to Talk2View's server for processing with MedGemma.\n\n"
            "By proceeding, you acknowledge that:\n"
            "• Your screenshot and query will be sent to Talk2View's server\n"
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

        tic = time.time()

        # Hide view controllers before capture
        self.talk2view_core.root.ScreenCapture_logic_showViewControllers(False)

        # Get temporary path
        temporary_path = self.talk2view_core.root.get_slicer_temp_path() + "/screenshot.png"

        self.talk2view_core.root.ScreenCapture_logic_captureImageFromView(None, temporary_path)

        # Show view controllers again
        self.talk2view_core.root.ScreenCapture_logic_showViewControllers(True)

        # Send screenshot to MedGemma server
        try:
            # Get API key from supabase manager
            if not self.supabase_manager:
                return "GoogleMedGemma.ask_medgemma_image: No API key available - connector not properly initialized"
            
            api_key = self.supabase_manager.get_litellm_api_key()
            if not api_key:
                return "GoogleMedGemma.ask_medgemma_image: No API key found for user"
            
            # Convert image to base64
            try:
                with open(temporary_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                    image_url = f"data:image/png;base64,{image_data}"
            except OSError as e:
                toc = time.time()
                return log_and_return_error(e, f"Failed in {toc - tic:.4f}s. Failed to read screenshot file: {str(e)}")
            
            url = f"https://t2v4-staging.talk2view.com/chat/completions"
            headers = {
                'Content-Type': 'application/json',
                'x-litellm-api-key': f"Bearer {api_key}"
            }
            data = {
                "model": f"openai/{model}",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            },
                            {
                                "type": "text",
                                "text": message
                            }
                        ]
                    }
                ],
                "max_tokens": 2048
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            logging.debug(f"MedGemma API response: {result}")

            # Extract message content from the API response
            choices = result.get('choices', [])
            if not choices:
                return "GoogleMedGemma.ask_medgemma_image: No response from MedGemma server"

            message_content = choices[0].get('message', {}).get('content', '')

            if not message_content:
                return "GoogleMedGemma.ask_medgemma_image: Empty response from MedGemma server"

            # Get the actual model name from the response
            model_used = result.get('model', model)

            # Add header
            header = f"*Connector's response using 'GoogleMedGemma.ask_medgemma_image':*\n---\n"

            # Add disclaimer footer
            disclaimer = f"\n\n---\n*The information above was generated using {model_used} by Google. This is an AI-generated analysis and should not be used as a substitute for professional medical advice.*"

            toc = time.time()
            logging.info(f"GoogleMedGemma.ask_medgemma_image executed in {toc - tic:.4f} seconds")
            return header + message_content + disclaimer

        except requests.exceptions.RequestException as e:
            toc = time.time()
            return log_and_return_error(e, f"Failed in {toc - tic:.4f}s. Failed to send screenshot to MedGemma server: {str(e)}")