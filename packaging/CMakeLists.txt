cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(RadAssistant)

#-----------------------------------------------------------------------------
# Extension meta-information
# NOTE: replace the REPLACE-ME URLs below with your real repository before
# submitting to the Slicer Extensions Index (Level 2). They are not required
# for a local build / "Install from file" (Level 1).
set(EXTENSION_HOMEPAGE "https://github.com/REPLACE-ME/RadAssistant")
set(EXTENSION_CATEGORY "Utilities")
set(EXTENSION_CONTRIBUTORS "RadAssistant contributors")
set(EXTENSION_DESCRIPTION "Natural-language agentic assistant for 3D Slicer. Bring your own model (local via Ollama / OpenAI-compatible, or Anthropic cloud). It drives Slicer's validated tools and shows its work. Research/visualization aid, not a diagnostic device.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/REPLACE-ME/RadAssistant/main/RadAssistant.png")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA") # a list of extension names this one depends on, or "NA"

#-----------------------------------------------------------------------------
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Modules provided by this extension
add_subdirectory(RadAssistant)
add_subdirectory(SlicerGPT)
add_subdirectory(test)
add_subdirectory(test)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
