"""Tests for categories.py — category definitions, YAML loading, and validation."""

import pytest
import yaml

from cull.categories import (
    DEFAULT_CATEGORIES,
    IMAGE_CATEGORIES,
    NON_CLIP_CATEGORIES,
    VIDEO_CATEGORIES,
    VIDEO_CATEGORY_NAMES,
    load_categories_yaml,
    merge_with_defaults,
    validate_categories,
)


class TestCategoryDefinitions:
    """Verify category data structures are well-formed."""

    def test_default_categories_combined(self):
        """DEFAULT_CATEGORIES should include both image and video categories."""
        assert len(DEFAULT_CATEGORIES) == len(IMAGE_CATEGORIES) + len(VIDEO_CATEGORIES)

    def test_image_categories_have_prompts(self):
        """Every image category should have at least one prompt."""
        for name, prompts in IMAGE_CATEGORIES.items():
            assert len(prompts) >= 1, f"{name} has no prompts"

    def test_video_categories_have_prompts(self):
        """Every video category should have at least one prompt."""
        for name, prompts in VIDEO_CATEGORIES.items():
            assert len(prompts) >= 1, f"{name} has no prompts"

    def test_video_category_names_set(self):
        """VIDEO_CATEGORY_NAMES should match the video category keys."""
        assert VIDEO_CATEGORY_NAMES == set(VIDEO_CATEGORIES.keys())

    @pytest.mark.parametrize("cat", ["person", "screenshot", "meme", "NSFW"])
    def test_common_categories_exist(self, cat: str):
        """Commonly used image categories should be present."""
        assert cat in IMAGE_CATEGORIES

    @pytest.mark.parametrize("cat", ["screencast", "video_call", "gaming"])
    def test_common_video_categories_exist(self, cat: str):
        """Commonly used video categories should be present."""
        assert cat in VIDEO_CATEGORIES

    def test_non_clip_categories(self):
        """PDF should be the only non-CLIP category."""
        assert "pdf" in NON_CLIP_CATEGORIES


class TestYAMLLoading:
    """Test loading custom categories from YAML files."""

    def test_load_categories(self, temp_dir):
        """Should parse a valid YAML categories file."""
        yaml_path = temp_dir / "cats.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "categories": {
                        "cat": ["a photo of a cat"],
                        "dog": ["a photo of a dog", "a canine"],
                    }
                }
            )
        )
        result = load_categories_yaml(yaml_path)
        assert "cat" in result
        assert result["cat"] == ["a photo of a cat"]
        assert result["dog"] == ["a photo of a dog", "a canine"]

    def test_load_single_prompt_string(self, temp_dir):
        """A single prompt as a string (not list) should be wrapped in a list."""
        yaml_path = temp_dir / "single.yaml"
        yaml_path.write_text("categories:\n  cat: a photo of a cat\n")
        result = load_categories_yaml(yaml_path)
        assert result["cat"] == ["a photo of a cat"]

    def test_file_not_found(self):
        """Should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_categories_yaml("/tmp/nonexistent_cats.yaml")

    def test_missing_categories_key(self, temp_dir):
        """Should raise ValueError when 'categories' key is missing."""
        yaml_path = temp_dir / "bad.yaml"
        yaml_path.write_text("foo: bar\n")
        with pytest.raises(ValueError, match="categories"):
            load_categories_yaml(yaml_path)

    def test_invalid_prompts_type(self, temp_dir):
        """Should raise ValueError when prompts aren't strings."""
        yaml_path = temp_dir / "bad2.yaml"
        yaml_path.write_text("categories:\n  cat: [1, 2, 3]\n")
        with pytest.raises(ValueError, match="prompts"):
            load_categories_yaml(yaml_path)


class TestMergeWithDefaults:
    """Test merging custom categories with built-in defaults."""

    def test_returns_defaults_when_no_custom(self):
        """merge_with_defaults(None) should return all defaults."""
        merged = merge_with_defaults(None)
        assert merged == DEFAULT_CATEGORIES

    def test_returns_defaults_when_empty(self):
        """merge_with_defaults({}) should return all defaults."""
        merged = merge_with_defaults({})
        assert merged == DEFAULT_CATEGORIES

    def test_adds_new_category(self):
        """A custom category that doesn't exist in defaults should be added."""
        merged = merge_with_defaults({"alien": ["a photo of an alien"]})
        assert "alien" in merged
        assert merged["alien"] == ["a photo of an alien"]

    def test_overrides_existing(self):
        """A custom category with the same name should override the default."""
        merged = merge_with_defaults({"person": ["a photo of a yogi"]})
        assert merged["person"] == ["a photo of a yogi"]

    def test_defaults_unchanged(self):
        """Original DEFAULT_CATEGORIES should not be mutated."""
        before = dict(DEFAULT_CATEGORIES)
        merge_with_defaults({"alien": ["a photo of an alien"]})
        assert DEFAULT_CATEGORIES == before


class TestCategoryValidation:
    """Test the validation helper."""

    def test_valid_categories_no_warnings(self):
        """Default categories should pass validation."""
        warnings = validate_categories(DEFAULT_CATEGORIES)
        for w in warnings:
            assert False, f"Unexpected warning: {w}"

    def test_invalid_name_warning(self):
        """A category name with spaces should trigger a warning."""
        categories = {"bad name": ["a prompt"]}
        warnings = validate_categories(categories)
        assert any("bad name" in w for w in warnings)

    def test_empty_prompts_warning(self):
        """A category with no prompts should trigger a warning."""
        categories = {"empty_cat": []}
        warnings = validate_categories(categories)
        assert any("empty_cat" in w for w in warnings)

    def test_short_prompt_warning(self):
        """A very short prompt should trigger a warning."""
        categories = {"shorty": ["ab"]}
        warnings = validate_categories(categories)
        assert any("shorty" in w for w in warnings)
