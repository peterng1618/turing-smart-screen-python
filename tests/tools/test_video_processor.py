"""
Unit tests for the video_processor tool.

Tests the helper functions and processing logic using PyAV.
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from video_processor import (
    parse_time_string,
    apply_rotation,
    apply_flip,
    resize_and_crop,
    crossfade_frames,
)


class TestParseTimeString:
    """Tests for the parse_time_string function."""
    
    def test_standard_format(self):
        """Test standard mm:ss format."""
        assert parse_time_string("01:30") == 90.0
        assert parse_time_string("00:45") == 45.0
        assert parse_time_string("10:00") == 600.0
        
    def test_zero(self):
        """Test zero values."""
        assert parse_time_string("00:00") == 0.0
        assert parse_time_string("0") == 0.0
        
    def test_seconds_only(self):
        """Test seconds-only format."""
        assert parse_time_string("45") == 45.0
        assert parse_time_string("120") == 120.0
        
    def test_fractional_seconds(self):
        """Test fractional seconds."""
        assert parse_time_string("01:30.5") == 90.5
        
    def test_empty_string(self):
        """Test empty string returns 0."""
        assert parse_time_string("") == 0.0
        assert parse_time_string(None) == 0.0
        
    def test_large_values(self):
        """Test large minute values."""
        assert parse_time_string("99:59") == 99 * 60 + 59


class TestApplyRotation:
    """Tests for the apply_rotation function."""
    
    @pytest.fixture
    def sample_frame(self):
        """Create a sample asymmetric frame for rotation testing."""
        # Create a 4x6 RGB frame with unique pattern
        frame = np.zeros((4, 6, 3), dtype=np.uint8)
        frame[0, 0] = [255, 0, 0]  # Red at top-left
        frame[0, 5] = [0, 255, 0]  # Green at top-right
        return frame
    
    def test_rotation_0(self, sample_frame):
        """Test 0 degree rotation (no change)."""
        result = apply_rotation(sample_frame, 0)
        np.testing.assert_array_equal(result, sample_frame)
        
    def test_rotation_90(self, sample_frame):
        """Test 90 degree clockwise rotation."""
        result = apply_rotation(sample_frame, 90)
        # After 90° CW: (4, 6) -> (6, 4)
        assert result.shape == (6, 4, 3)
        # Top-left red should move to top-right
        np.testing.assert_array_equal(result[0, 3], [255, 0, 0])
        
    def test_rotation_180(self, sample_frame):
        """Test 180 degree rotation."""
        result = apply_rotation(sample_frame, 180)
        # Shape preserved
        assert result.shape == sample_frame.shape
        # Top-left red should move to bottom-right
        np.testing.assert_array_equal(result[3, 5], [255, 0, 0])
        
    def test_rotation_270(self, sample_frame):
        """Test 270 degree (counter-clockwise 90) rotation."""
        result = apply_rotation(sample_frame, 270)
        # After 270° CW: (4, 6) -> (6, 4)
        assert result.shape == (6, 4, 3)
        # Top-left red should move to bottom-left
        np.testing.assert_array_equal(result[5, 0], [255, 0, 0])
        
    def test_invalid_rotation(self, sample_frame):
        """Test invalid rotation value returns unchanged frame."""
        result = apply_rotation(sample_frame, 45)
        np.testing.assert_array_equal(result, sample_frame)


class TestApplyFlip:
    """Tests for the apply_flip function."""
    
    @pytest.fixture
    def sample_frame(self):
        """Create a sample frame for flip testing."""
        frame = np.zeros((3, 4, 3), dtype=np.uint8)
        frame[0, 0] = [255, 0, 0]  # Red at top-left
        frame[2, 3] = [0, 255, 0]  # Green at bottom-right
        return frame
    
    def test_no_flip(self, sample_frame):
        """Test None flip (no change)."""
        result = apply_flip(sample_frame, None)
        np.testing.assert_array_equal(result, sample_frame)
        
    def test_horizontal_flip(self, sample_frame):
        """Test horizontal flip."""
        result = apply_flip(sample_frame, "horizontal")
        # Top-left red should move to top-right
        np.testing.assert_array_equal(result[0, 3], [255, 0, 0])
        # Bottom-right green should move to bottom-left
        np.testing.assert_array_equal(result[2, 0], [0, 255, 0])
        
    def test_vertical_flip(self, sample_frame):
        """Test vertical flip."""
        result = apply_flip(sample_frame, "vertical")
        # Top-left red should move to bottom-left
        np.testing.assert_array_equal(result[2, 0], [255, 0, 0])
        # Bottom-right green should move to top-right
        np.testing.assert_array_equal(result[0, 3], [0, 255, 0])
        
    def test_both_flip(self, sample_frame):
        """Test flip in both directions."""
        result = apply_flip(sample_frame, "both")
        # Top-left red should move to bottom-right
        np.testing.assert_array_equal(result[2, 3], [255, 0, 0])
        # Bottom-right green should move to top-left
        np.testing.assert_array_equal(result[0, 0], [0, 255, 0])
        
    def test_case_insensitive(self, sample_frame):
        """Test flip is case insensitive."""
        result1 = apply_flip(sample_frame, "HORIZONTAL")
        result2 = apply_flip(sample_frame, "horizontal")
        np.testing.assert_array_equal(result1, result2)
        
    def test_invalid_flip(self, sample_frame):
        """Test invalid flip value returns unchanged frame."""
        result = apply_flip(sample_frame, "diagonal")
        np.testing.assert_array_equal(result, sample_frame)


class TestResizeAndCrop:
    """Tests for the resize_and_crop function."""
    
    def test_exact_size(self):
        """Test frame already at target size."""
        frame = np.random.randint(0, 255, (480, 800, 3), dtype=np.uint8)
        result = resize_and_crop(frame, 800, 480)
        assert result.shape == (480, 800, 3)
        
    def test_downscale_wide(self):
        """Test downscaling a wider frame."""
        frame = np.random.randint(0, 255, (480, 1600, 3), dtype=np.uint8)
        result = resize_and_crop(frame, 800, 480)
        assert result.shape == (480, 800, 3)
        
    def test_downscale_tall(self):
        """Test downscaling a taller frame."""
        frame = np.random.randint(0, 255, (960, 800, 3), dtype=np.uint8)
        result = resize_and_crop(frame, 800, 480)
        assert result.shape == (480, 800, 3)
        
    def test_upscale(self):
        """Test upscaling a smaller frame."""
        frame = np.random.randint(0, 255, (240, 400, 3), dtype=np.uint8)
        result = resize_and_crop(frame, 800, 480)
        assert result.shape == (480, 800, 3)
        
    def test_portrait_orientation(self):
        """Test portrait target dimensions."""
        frame = np.random.randint(0, 255, (800, 480, 3), dtype=np.uint8)
        result = resize_and_crop(frame, 480, 800)
        assert result.shape == (800, 480, 3)


class TestCrossfadeFrames:
    """Tests for the crossfade_frames function."""
    
    def test_basic_crossfade(self):
        """Test basic frame crossfade."""
        # Create simple black and white frames
        black = np.zeros((2, 2, 3), dtype=np.uint8)
        white = np.ones((2, 2, 3), dtype=np.uint8) * 255
        
        frames_a = [black.copy() for _ in range(3)]
        frames_b = [white.copy() for _ in range(3)]
        
        result = crossfade_frames(frames_a, frames_b)
        
        assert len(result) == 3
        # First frame should be mostly black (alpha=0)
        assert np.mean(result[0]) < 10
        # Middle frame should be gray (alpha=0.5)
        assert 120 < np.mean(result[1]) < 135
        # Last frame should be mostly white (alpha=1)
        assert np.mean(result[2]) > 245
        
    def test_single_frame_crossfade(self):
        """Test crossfade with single frame."""
        black = np.zeros((2, 2, 3), dtype=np.uint8)
        white = np.ones((2, 2, 3), dtype=np.uint8) * 255
        
        result = crossfade_frames([black], [white])
        
        assert len(result) == 1
        # Single frame should be 50% blend
        assert 120 < np.mean(result[0]) < 135
        
    def test_crossfade_length_mismatch(self):
        """Test crossfade raises error on mismatched lengths."""
        frames_a = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]
        frames_b = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(5)]
        
        with pytest.raises(ValueError):
            crossfade_frames(frames_a, frames_b)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
