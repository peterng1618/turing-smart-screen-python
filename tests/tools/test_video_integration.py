
import pytest
import av
import numpy as np
from unittest.mock import patch

from theme_editor.utils.video_processor import process_video

@pytest.fixture
def temp_theme_dir(tmp_path):
    """Create a temporary theme directory structure."""
    theme_dir = tmp_path / "test_theme"
    theme_dir.mkdir()
    
    # Create valid theme.yaml
    theme_yaml = theme_dir / "theme.yaml"
    with open(theme_yaml, "w") as f:
        f.write("""
display:
    DISPLAY_SIZE: '5"'
    DISPLAY_ORIENTATION: 'landscape'
    DISPLAY_RGB_LED: '255, 255, 255'

video_background:
    LOOP_FADE_DURATION: 0.5
    ROTATE: 90
    FLIP: 'horizontal'
    START_OFFSET: '00:00'
    DURATION: '00:02'

ui_elements: []
dynamic_elements: []
static_images: {}
""")
    return theme_dir

@pytest.fixture
def dummy_video(tmp_path):
    """Create a dummy mp4 video using PyAV."""
    video_path = tmp_path / "input.mp4"
    
    container = av.open(str(video_path), mode='w')
    stream = container.add_stream('libx264', rate=30)
    stream.width = 640
    stream.height = 480
    stream.pix_fmt = 'yuv420p'
    
    # Create 90 frames (3 seconds at 30 fps)
    for i in range(90):
        # Create a frame with changing color
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:, :, 0] = i * 2  # Red gradient
        img[:, :, 1] = 255 - (i * 2) # Green gradient
        
        frame = av.VideoFrame.from_ndarray(img, format='rgb24')
        for packet in stream.encode(frame):
            container.mux(packet)
            
    for packet in stream.encode():
        container.mux(packet)
        
    container.close()
    return video_path

def test_process_video_pipeline(temp_theme_dir, dummy_video):
    """
    Test the full process_video pipeline.
    Verifies output exists, has correct dimensions (flipped/rotated), and no audio.
    """
    output_path = temp_theme_dir / "output.mp4"
    
    # Mock UiRenderer to avoid needing complex font/asset setup
    with patch('theme_editor.utils.video_processor.UiRenderer') as MockRenderer:
        # Mock renderer instance
        renderer_instance = MockRenderer.return_value
        renderer_instance.width = 800
        renderer_instance.height = 480
        
        # Mock generate_overlay to return a transparent image
        from PIL import Image
        renderer_instance.generate_overlay.return_value = Image.new('RGBA', (800, 480), (0, 0, 0, 0))
        
        # Run processing
        result = process_video(str(temp_theme_dir), str(dummy_video), str(output_path))
        
        assert result is True
        assert output_path.exists()
        
        # Verify output properties
        container = av.open(str(output_path))
        stream = container.streams.video[0]
        
        # Check dimensions
        # Target was 5" landscape (800x480)
        assert stream.width == 800
        assert stream.height == 480
        
        # Check codec
        assert stream.codec_context.name == 'h264'
        
        # Check audio
        assert len(container.streams.audio) == 0
        
        container.close()

def test_process_video_invalid_paths():
    """Test process_video handles missing files gracefully."""
    assert process_video("non_existent_theme", "non_existent_video.mp4") is False
