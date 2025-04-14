import json
import os
import pytest
from unittest.mock import patch

# Assuming src is importable
from src import storage

# --- Fixtures ---

@pytest.fixture
def temp_storage_file(tmp_path):
    """Creates a temporary file path for storage tests."""
    return tmp_path / "test_known_urls.json"

@pytest.fixture(autouse=True)
def mock_local_storage_path(mocker, temp_storage_file):
    """Mocks the LOCAL_STORAGE_PATH constant to use the temporary file."""
    mocker.patch('src.storage.LOCAL_STORAGE_PATH', str(temp_storage_file))
    # Ensure the file doesn't exist before each test unless explicitly created
    if temp_storage_file.exists():
        temp_storage_file.unlink()
    yield str(temp_storage_file) # Provide the path to tests if needed
    # Clean up after test if file exists
    if temp_storage_file.exists():
        temp_storage_file.unlink()


# --- Test Cases for load_known_urls ---

def test_load_known_urls_file_not_exists(temp_storage_file):
    """Test load_known_urls when the file does not exist."""
    assert not temp_storage_file.exists()
    known_urls = storage.load_known_urls()
    assert known_urls == set()

def test_load_known_urls_success(temp_storage_file):
    """Test load_known_urls with a valid JSON file."""
    urls_list = ["http://a.pdf", "http://b.pdf"]
    temp_storage_file.write_text(json.dumps(urls_list), encoding='utf-8')
    known_urls = storage.load_known_urls()
    assert known_urls == set(urls_list)

def test_load_known_urls_empty_file(temp_storage_file):
    """Test load_known_urls with an empty file (invalid JSON)."""
    temp_storage_file.write_text("", encoding='utf-8')
    known_urls = storage.load_known_urls()
    assert known_urls == set() # Should handle JSONDecodeError

def test_load_known_urls_invalid_json(temp_storage_file):
    """Test load_known_urls with invalid JSON content."""
    temp_storage_file.write_text("{invalid json", encoding='utf-8')
    known_urls = storage.load_known_urls()
    assert known_urls == set() # Should handle JSONDecodeError

def test_load_known_urls_not_a_list(temp_storage_file):
    """Test load_known_urls when JSON content is not a list."""
    temp_storage_file.write_text(json.dumps({"key": "value"}), encoding='utf-8')
    known_urls = storage.load_known_urls()
    assert known_urls == set() # Should handle non-list content

def test_load_known_urls_io_error(temp_storage_file, mocker):
    """Test load_known_urls handles IOError during file read."""
    # Create the file first
    temp_storage_file.write_text("[]", encoding='utf-8')
    # Mock open to raise IOError
    mocker.patch('builtins.open', side_effect=IOError("Failed to read"))
    known_urls = storage.load_known_urls()
    assert known_urls == set() # Expect empty set on error

# --- Test Cases for save_known_urls ---

def test_save_known_urls_success(temp_storage_file):
    """Test save_known_urls successfully saves data."""
    urls_to_save = {"http://c.pdf", "http://a.pdf", "http://b.pdf"}
    storage.save_known_urls(urls_to_save)

    assert temp_storage_file.exists()
    content = temp_storage_file.read_text(encoding='utf-8')
    loaded_list = json.loads(content)
    # Check content and sorting
    assert loaded_list == ["http://a.pdf", "http://b.pdf", "http://c.pdf"]
    assert set(loaded_list) == urls_to_save

def test_save_known_urls_empty_set(temp_storage_file):
    """Test save_known_urls with an empty set."""
    urls_to_save = set()
    storage.save_known_urls(urls_to_save)

    assert temp_storage_file.exists()
    content = temp_storage_file.read_text(encoding='utf-8')
    loaded_list = json.loads(content)
    assert loaded_list == []

def test_save_known_urls_io_error(temp_storage_file, mocker):
    """Test save_known_urls handles IOError during file write."""
    urls_to_save = {"http://error.pdf"}
    # Mock open to raise IOError
    mocker.patch('builtins.open', side_effect=IOError("Failed to write"))
    # We expect the function to log the error but not raise it
    storage.save_known_urls(urls_to_save)
    # Assert file doesn't exist or is empty (depending on when error occurs)
    assert not temp_storage_file.exists() or temp_storage_file.read_text() == ""

# --- Test Cases for find_new_urls ---

def test_find_new_urls_first_run(temp_storage_file):
    """Test find_new_urls on the first run (no existing file)."""
    current_urls = {"http://first.pdf", "http://second.pdf"}
    assert not temp_storage_file.exists()

    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == set() # No new URLs reported on first run
    # Check if the file was created and contains the current URLs
    assert temp_storage_file.exists()
    saved_urls = storage.load_known_urls() # Use load function to verify
    assert saved_urls == current_urls

def test_find_new_urls_no_new(temp_storage_file):
    """Test find_new_urls when there are no new URLs."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    storage.save_known_urls(initial_urls) # Setup initial state

    current_urls = {"http://b.pdf", "http://a.pdf"} # Same URLs, different order
    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == set()
    # Verify file content remains unchanged
    saved_urls = storage.load_known_urls()
    assert saved_urls == initial_urls

def test_find_new_urls_with_new(temp_storage_file):
    """Test find_new_urls when new URLs are found."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    storage.save_known_urls(initial_urls) # Setup initial state

    current_urls = {"http://b.pdf", "http://c.pdf", "http://d.pdf"}
    expected_new = {"http://c.pdf", "http://d.pdf"}
    expected_saved = {"http://a.pdf", "http://b.pdf", "http://c.pdf", "http://d.pdf"}

    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == expected_new
    # Verify the known URLs file was updated correctly
    saved_urls = storage.load_known_urls()
    assert saved_urls == expected_saved

def test_find_new_urls_current_is_subset(temp_storage_file):
    """Test find_new_urls when current URLs are a subset of known URLs."""
    initial_urls = {"http://a.pdf", "http://b.pdf", "http://c.pdf"}
    storage.save_known_urls(initial_urls) # Setup initial state

    current_urls = {"http://b.pdf", "http://a.pdf"}
    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == set()
    # Verify file content remains unchanged
    saved_urls = storage.load_known_urls()
    assert saved_urls == initial_urls

def test_find_new_urls_empty_current(temp_storage_file):
    """Test find_new_urls when the current URL list is empty."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    storage.save_known_urls(initial_urls) # Setup initial state

    current_urls = set()
    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == set()
     # Verify file content remains unchanged
    saved_urls = storage.load_known_urls()
    assert saved_urls == initial_urls

def test_find_new_urls_load_error(temp_storage_file, mocker):
    """Test find_new_urls handles error during load_known_urls."""
    current_urls = {"http://a.pdf", "http://b.pdf"}
    # Mock load_known_urls to simulate an error (e.g., return None or raise)
    # Let's simulate it returning an empty set due to an internal error
    mocker.patch('src.storage.load_known_urls', return_value=set())
    mock_save = mocker.patch('src.storage.save_known_urls') # Also mock save

    new_urls = storage.find_new_urls(current_urls)

    # If load fails (returns empty), it should behave like the first run
    assert new_urls == set()
    # Check that save was called with the current URLs
    mock_save.assert_called_once_with(current_urls)


def test_find_new_urls_save_error(temp_storage_file, mocker):
    """Test find_new_urls handles error during save_known_urls."""
    initial_urls = {"http://a.pdf"}
    storage.save_known_urls(initial_urls) # Setup initial state

    current_urls = {"http://a.pdf", "http://b.pdf"}
    expected_new = {"http://b.pdf"}

    # Mock save_known_urls to simulate an error (e.g., raise Exception)
    mock_save = mocker.patch('src.storage.save_known_urls', side_effect=IOError("Disk full"))

    # Even if save fails, find_new_urls should still return the new URLs found
    new_urls = storage.find_new_urls(current_urls)

    assert new_urls == expected_new
    # Check that save was called (even though it failed)
    mock_save.assert_called_once_with(initial_urls.union(expected_new))
    # The original file should remain unchanged because save failed
    saved_urls = storage.load_known_urls() # Read the actual file content
    assert saved_urls == initial_urls


# Consider adding tests for error handling during file I/O within find_new_urls
# by mocking open() or json.dump/load to raise exceptions.
