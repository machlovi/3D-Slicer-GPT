import os
from radassistant_deep import MockSlicerSession, ToolOutcome

def test_recording_and_mimic_tools_in_session():
    # 1. Initialize MockSlicerSession
    session = MockSlicerSession()
    
    # 2. Test start_segmentation_recording
    res = session.start_segmentation_recording("mock_log.json")
    assert not res.is_error
    assert "Started recording" in res.text
    assert session.calls[-1] == ("start_segmentation_recording", {"output_filename": "mock_log.json"})
    
    # 3. Test get_segmentation_recording_status
    res = session.get_segmentation_recording_status()
    assert not res.is_error
    assert "Recording status" in res.text
    assert session.calls[-1] == ("get_segmentation_recording_status", {})
    
    # 4. Test stop_segmentation_recording
    res = session.stop_segmentation_recording()
    assert not res.is_error
    assert "Stopped recording" in res.text
    assert session.calls[-1] == ("stop_segmentation_recording", {})
    
    # 5. Test mimic_segmentation_cleanup
    res = session.mimic_segmentation_cleanup(
        trajectory_path="mock_log.json", 
        target_segmentation="Segmentation_Node",
        source_volume="CTChest",
        target_volume="CTChest_Aligned"
    )
    assert not res.is_error
    assert "Successfully replayed" in res.text
    assert session.calls[-1] == (
        "mimic_segmentation_cleanup",
        {
            "trajectory_path": "mock_log.json",
            "target_segmentation": "Segmentation_Node",
            "source_volume": "CTChest",
            "target_volume": "CTChest_Aligned"
        }
    )
