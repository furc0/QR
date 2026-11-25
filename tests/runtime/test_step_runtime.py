from install_step_runtime import (
    EXPECTED_GIT_BLOB_SHA1,
    EXPECTED_SIZE,
    git_blob_sha1_bytes,
)


def test_git_blob_sha1_uses_git_object_format():
    assert git_blob_sha1_bytes(b"hello world\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_step_runtime_is_pinned_to_expected_binary():
    assert EXPECTED_SIZE == 7_604_031
    assert EXPECTED_GIT_BLOB_SHA1 == "29458885e6b030850d352cff33ab0c22a7e36c35"
