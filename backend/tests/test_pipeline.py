"""
tests/test_pipeline.py — Unit tests for the TerraDelta backend pipeline.
Run with: pytest tests/ -v
"""
import sys
import numpy as np
import pytest
from pathlib import Path

# Allow importing from parent
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Preprocessing tests ───────────────────────────────────────────────────────

class TestPreprocessing:
    def setup_method(self):
        self.bands = {
            'B02': np.random.uniform(0, 0.35, (50, 50)).astype(np.float32),
            'B03': np.random.uniform(0, 0.35, (50, 50)).astype(np.float32),
            'B04': np.random.uniform(0, 0.35, (50, 50)).astype(np.float32),
            'B08': np.random.uniform(0, 0.50, (50, 50)).astype(np.float32),
            'B11': np.random.uniform(0, 0.30, (50, 50)).astype(np.float32),
            'B12': np.random.uniform(0, 0.25, (50, 50)).astype(np.float32),
        }

    def test_spectral_indices_range(self):
        from pipeline.preprocessing import compute_spectral_indices
        indices = compute_spectral_indices(self.bands)
        for name, arr in indices.items():
            assert arr.min() >= -1.0, f"{name} below -1"
            assert arr.max() <= 1.0,  f"{name} above 1"
            assert arr.dtype == np.float32

    def test_spectral_indices_keys(self):
        from pipeline.preprocessing import compute_spectral_indices
        indices = compute_spectral_indices(self.bands)
        assert set(indices.keys()) == {'NDVI', 'NDBI', 'NDWI', 'BSI'}

    def test_clip_reflectance(self):
        from pipeline.preprocessing import clip_reflectance
        noisy = {k: v + 5.0 for k, v in self.bands.items()}  # out of range
        clipped = clip_reflectance(noisy)
        for v in clipped.values():
            assert v.max() <= 1.0
            assert v.min() >= 0.0

    def test_rgb_output_shape(self):
        from pipeline.preprocessing import bands_to_rgb
        rgb = bands_to_rgb(self.bands)
        assert rgb.shape == (50, 50, 3)
        assert rgb.dtype == np.uint8
        assert rgb.max() <= 255


# ── Feature engineering tests ─────────────────────────────────────────────────

class TestFeatures:
    def setup_method(self):
        self.H, self.W = 30, 30
        self.t1_bands = {
            b: np.random.uniform(0, 0.3, (self.H, self.W)).astype(np.float32)
            for b in ['B02', 'B03', 'B04', 'B08', 'B11', 'B12']
        }
        self.t2_bands = {
            b: np.random.uniform(0, 0.3, (self.H, self.W)).astype(np.float32)
            for b in ['B02', 'B03', 'B04', 'B08', 'B11', 'B12']
        }
        from pipeline.preprocessing import compute_spectral_indices
        self.t1_idx = compute_spectral_indices(self.t1_bands)
        self.t2_idx = compute_spectral_indices(self.t2_bands)

    def test_feature_array_shape(self):
        from pipeline.features import build_feature_array
        feats = build_feature_array(self.t1_bands, self.t2_bands,
                                    self.t1_idx, self.t2_idx,
                                    use_texture=False)
        # Without texture: 6+6+4+4+6+4+6 = 36
        assert feats.shape[:2] == (self.H, self.W)
        assert feats.shape[2] > 30, "Expected >30 features"

    def test_no_nan_in_features(self):
        from pipeline.features import build_feature_array
        feats = build_feature_array(self.t1_bands, self.t2_bands,
                                    self.t1_idx, self.t2_idx, use_texture=False)
        assert not np.isnan(feats).any(), "NaN values in feature array"

    def test_feature_dtype(self):
        from pipeline.features import build_feature_array
        feats = build_feature_array(self.t1_bands, self.t2_bands,
                                    self.t1_idx, self.t2_idx, use_texture=False)
        assert feats.dtype == np.float32


# ── Post-processing tests ─────────────────────────────────────────────────────

class TestPostProcessing:
    def test_threshold(self):
        from pipeline.postprocessing import threshold_probability
        prob = np.array([[0.3, 0.7], [0.4, 0.9]])
        binary = threshold_probability(prob, threshold=0.5)
        expected = np.array([[0, 1], [0, 1]], dtype=np.uint8)
        np.testing.assert_array_equal(binary, expected)

    def test_small_component_removal(self):
        from pipeline.postprocessing import remove_small_components
        binary = np.zeros((20, 20), dtype=np.uint8)
        binary[5:7, 5:7] = 1    # 4 pixels — below threshold
        binary[10:15, 10:15] = 1  # 25 pixels — above threshold
        result = remove_small_components(binary, min_pixels=9)
        assert result[5, 5] == 0,  "Small component should be removed"
        assert result[12, 12] == 1, "Large component should remain"

    def test_vectorize_returns_geojson_features(self):
        from pipeline.postprocessing import vectorize_changes
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[10:20, 10:20] = 1
        mask[30:40, 30:40] = 1
        bbox = [72.0, 18.0, 73.0, 19.0]
        features = vectorize_changes(mask, bbox)
        assert len(features) == 2
        for f in features:
            assert f['type'] == 'Feature'
            assert 'geometry' in f
            assert 'properties' in f
            assert f['properties']['area_pixels'] > 0

    def test_postprocess_full_pipeline(self):
        from pipeline.postprocessing import postprocess_change_map
        prob = np.zeros((30, 30), dtype=np.float32)
        prob[10:20, 10:20] = 0.8   # large change blob
        prob[0, 0] = 0.9           # isolated single pixel noise
        result = postprocess_change_map(prob, threshold=0.5, min_area_pixels=9)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0,   "Isolated pixel should be removed"
        assert result[15, 15] == 1, "Large blob should remain"


# ── Human filter tests ────────────────────────────────────────────────────────

class TestFiltering:
    def setup_method(self):
        self.H, self.W = 20, 20
        self.change_mask = np.ones((self.H, self.W), dtype=np.uint8)
        # Base indices — no change
        self.t1_idx = {
            'NDVI': np.full((self.H, self.W), 0.4, dtype=np.float32),
            'NDBI': np.full((self.H, self.W), -0.2, dtype=np.float32),
            'NDWI': np.full((self.H, self.W), -0.1, dtype=np.float32),
            'BSI':  np.full((self.H, self.W), -0.1, dtype=np.float32),
        }

    def test_flood_suppression(self):
        from pipeline.filtering import human_change_filter
        # T2 with large NDWI increase (flood)
        t2_idx = {
            'NDVI': np.full((self.H, self.W), 0.3, dtype=np.float32),
            'NDBI': np.full((self.H, self.W), -0.18, dtype=np.float32),
            'NDWI': np.full((self.H, self.W), 0.35, dtype=np.float32),  # flood
            'BSI':  np.full((self.H, self.W), -0.1, dtype=np.float32),
        }
        result = human_change_filter(self.change_mask, self.t1_idx, t2_idx,
                                     ndwi_threshold=0.15)
        assert result.sum() == 0, "Flood signal should be completely suppressed"

    def test_builtup_preserved(self):
        from pipeline.filtering import human_change_filter
        # T2 with NDBI increase (new building)
        t2_idx = {
            'NDVI': np.full((self.H, self.W), 0.2, dtype=np.float32),
            'NDBI': np.full((self.H, self.W), 0.0, dtype=np.float32),   # NDBI +0.2
            'NDWI': np.full((self.H, self.W), -0.1, dtype=np.float32),
            'BSI':  np.full((self.H, self.W), 0.0, dtype=np.float32),
        }
        result = human_change_filter(self.change_mask, self.t1_idx, t2_idx)
        assert result.sum() > 0, "Built-up expansion should be preserved"


# ── Statistics tests ──────────────────────────────────────────────────────────

class TestStatistics:
    def test_zero_change(self):
        from pipeline.statistics import compute_statistics
        mask = np.zeros((50, 50), dtype=np.uint8)
        prob = np.zeros((50, 50), dtype=np.float32)
        stats = compute_statistics(mask, prob)
        assert stats['changed_area_ha'] == 0.0
        assert stats['change_percent']  == 0.0
        assert stats['num_clusters']    == 0

    def test_stats_consistency(self):
        from pipeline.statistics import compute_statistics
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 1  # 400 pixels = 4 ha
        prob = np.full((100, 100), 0.75, dtype=np.float32)
        stats = compute_statistics(mask, prob, pixel_area_m2=100)
        assert stats['changed_area_ha'] == pytest.approx(4.0, rel=0.01)
        assert stats['change_percent']  == pytest.approx(4.0, rel=0.01)
        assert stats['num_clusters']    == 1
        assert stats['mean_confidence'] == pytest.approx(0.75, rel=0.01)


# ── Interpretation tests ──────────────────────────────────────────────────────

class TestInterpretation:
    def test_no_change_message(self):
        from pipeline.filtering import generate_interpretation
        import numpy as np
        idx = {'NDVI': np.zeros((10,10)), 'NDBI': np.zeros((10,10)),
               'NDWI': np.zeros((10,10)), 'BSI': np.zeros((10,10))}
        msg = generate_interpretation({'changed_area_ha': 0, 'change_percent': 0,
                                        'num_clusters': 0, 'mean_confidence': 0},
                                       idx, idx, [0, 0, 1, 1])
        assert 'no significant' in msg.lower()

    def test_significant_change_message(self):
        from pipeline.filtering import generate_interpretation
        import numpy as np
        t1 = {'NDVI': np.full((10,10), 0.4), 'NDBI': np.full((10,10), -0.2),
               'NDWI': np.zeros((10,10)), 'BSI': np.zeros((10,10))}
        t2 = {'NDVI': np.full((10,10), 0.1), 'NDBI': np.full((10,10), 0.1),
               'NDWI': np.zeros((10,10)), 'BSI': np.zeros((10,10))}
        stats = {'changed_area_ha': 250, 'change_percent': 25,
                 'num_clusters': 5, 'mean_confidence': 0.82}
        msg = generate_interpretation(stats, t1, t2, [0, 0, 1, 1])
        assert len(msg) > 50
        assert '250' in msg or '25' in msg
