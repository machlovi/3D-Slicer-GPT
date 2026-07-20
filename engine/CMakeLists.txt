#-----------------------------------------------------------------------------
# RadAssistant scripted module
#-----------------------------------------------------------------------------
set(MODULE_NAME RadAssistant)

#-----------------------------------------------------------------------------
# The module entry-point script.
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

# Files copied verbatim next to the module (icon, etc.).
set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  )

#-----------------------------------------------------------------------------
# RadAssistant is more than a single .py: it ships a support package
# (radassistant_lib), a progressive-disclosure skill library (skills), and the
# connector adapters (connectors). Install those directory trees next to the
# module script so `import radassistant_lib`, SkillLibrary, and the connectors
# all resolve from the module's own directory at runtime.
foreach(_dir radassistant_lib skills connectors)
  install(DIRECTORY ${_dir}
    DESTINATION ${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
    COMPONENT RuntimeLibraries
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE
    )
endforeach()
