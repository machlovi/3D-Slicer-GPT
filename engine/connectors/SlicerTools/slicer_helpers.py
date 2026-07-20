# SlicerTools Slicer-side helpers
#
# These functions run locally inside 3D Slicer (no RPyC overhead).
# They are loaded by load_connector_helpers() and registered as
# SlicerTools_<name> on the RPyC service.

import logging


def create_linear_transform(name, translation=None, rotation=None):
    """Create a linear transform node with optional translation and rotation.

    Must run on the Slicer side because vtk.vtkTransform() can't be
    constructed over RPyC.

    Args:
        name: Name for the transform node.
        translation: [x, y, z] translation in mm, or None.
        rotation: [rx, ry, rz] rotation in degrees, or None.

    Returns:
        The created vtkMRMLLinearTransformNode.
    """
    import vtk
    import slicer

    transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    transformNode.SetName(name)

    transform = vtk.vtkTransform()
    if rotation:
        transform.RotateX(rotation[0])
        transform.RotateY(rotation[1])
        transform.RotateZ(rotation[2])
    if translation:
        transform.Translate(translation[0], translation[1], translation[2])

    transformNode.SetMatrixTransformToParent(transform.GetMatrix())

    logging.info(f"[SlicerTools] Created linear transform '{name}'")
    return transformNode
