"""Property-based tests for netrc credential provider."""

import os
import stat
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.infrastructure.netrc_provider import NetrcCredentialProvider


# Feature: streamdown, Property 32: Netrc credentials loaded at startup
# Validates: Requirements 15.1
@settings(max_examples=100)
@given(
    hostname=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: "." not in x and " " not in x),
    username=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: " " not in x),
    password=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@$%^&*()-_=+[]{}|;:,.<>?/",
        min_size=1,
        max_size=30,
    ),
)
def test_netrc_credentials_loaded_at_startup(hostname: str, username: str, password: str):
    """For any download with netrc enabled and a valid netrc file present,
    credentials must be loaded during initialization before any downloads begin."""
    
    # Create a temporary netrc file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f:
        netrc_path = Path(f.name)
        f.write(f"machine {hostname}\n")
        f.write(f"login {username}\n")
        f.write(f"password {password}\n")
    
    try:
        # Set correct permissions (600)
        if os.name != 'nt':
            os.chmod(netrc_path, 0o600)
        
        # Initialize provider with netrc enabled
        provider = NetrcCredentialProvider(netrc_path=netrc_path, enabled=True)
        
        # Verify credentials are loaded
        creds = provider.get_credentials(hostname)
        assert creds is not None, f"Credentials should be loaded for {hostname}"
        assert creds[0] == username, f"Username should match: expected {username}, got {creds[0]}"
        assert creds[1] == password, f"Password should match: expected {password}, got {creds[1]}"
    finally:
        # Cleanup
        netrc_path.unlink(missing_ok=True)


# Feature: streamdown, Property 34: Netrc disabled with no-netrc flag
# Validates: Requirements 15.4
@settings(max_examples=100)
@given(
    hostname=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: "." not in x and " " not in x),
    username=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: " " not in x),
    password=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@$%^&*()-_=+[]{}|;:,.<>?/",
        min_size=1,
        max_size=30,
    ),
)
def test_netrc_disabled_with_flag(hostname: str, username: str, password: str):
    """For any download with no-netrc set to true, the netrc file must not be read
    and no netrc credentials must be used."""
    
    # Create a temporary netrc file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f:
        netrc_path = Path(f.name)
        f.write(f"machine {hostname}\n")
        f.write(f"login {username}\n")
        f.write(f"password {password}\n")
    
    try:
        # Set correct permissions (600)
        if os.name != 'nt':
            os.chmod(netrc_path, 0o600)
        
        # Initialize provider with netrc disabled
        provider = NetrcCredentialProvider(netrc_path=netrc_path, enabled=False)
        
        # Verify credentials are NOT loaded
        creds = provider.get_credentials(hostname)
        assert creds is None, "Credentials should not be loaded when netrc is disabled"
    finally:
        # Cleanup
        netrc_path.unlink(missing_ok=True)


# Feature: streamdown, Property 35: Custom netrc path respected
# Validates: Requirements 15.5
@settings(max_examples=100)
@given(
    hostname=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: "." not in x and " " not in x),
    username=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=20,
    ).filter(lambda x: " " not in x),
    password=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@$%^&*()-_=+[]{}|;:,.<>?/",
        min_size=1,
        max_size=30,
    ),
)
def test_custom_netrc_path_respected(hostname: str, username: str, password: str):
    """For any download with netrc-path specified, credentials must be read from
    the specified path instead of the default ~/.netrc location."""
    
    # Create two temporary netrc files with different credentials
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f1:
        custom_path = Path(f1.name)
        f1.write(f"machine {hostname}\n")
        f1.write(f"login {username}\n")
        f1.write(f"password {password}\n")
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f2:
        default_path = Path(f2.name)
        f2.write(f"machine {hostname}\n")
        f2.write(f"login wrong_user\n")
        f2.write(f"password wrong_pass\n")
    
    try:
        # Set correct permissions (600)
        if os.name != 'nt':
            os.chmod(custom_path, 0o600)
            os.chmod(default_path, 0o600)
        
        # Initialize provider with custom path
        provider = NetrcCredentialProvider(netrc_path=custom_path, enabled=True)
        
        # Verify credentials from custom path are used
        creds = provider.get_credentials(hostname)
        assert creds is not None, f"Credentials should be loaded from custom path"
        assert creds[0] == username, f"Should use custom path credentials: expected {username}, got {creds[0]}"
        assert creds[1] == password, f"Should use custom path credentials: expected {password}, got {creds[1]}"
        
        # Verify it's not using default path
        assert creds[0] != "wrong_user", "Should not use default path credentials"
    finally:
        # Cleanup
        custom_path.unlink(missing_ok=True)
        default_path.unlink(missing_ok=True)


# Unit tests for edge cases
def test_missing_netrc_file():
    """Test graceful handling when netrc file doesn't exist."""
    non_existent = Path("/tmp/nonexistent_netrc_file_12345.netrc")
    provider = NetrcCredentialProvider(netrc_path=non_existent, enabled=True)
    
    creds = provider.get_credentials("example.com")
    assert creds is None, "Should return None when netrc file doesn't exist"


@pytest.mark.skipif(os.name == 'nt', reason="Permission checks not applicable on Windows")
def test_incorrect_permissions():
    """Test that netrc file with incorrect permissions is ignored."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f:
        netrc_path = Path(f.name)
        f.write("machine example.com\n")
        f.write("login testuser\n")
        f.write("password testpass\n")
    
    try:
        # Set incorrect permissions (644)
        os.chmod(netrc_path, 0o644)
        
        provider = NetrcCredentialProvider(netrc_path=netrc_path, enabled=True)
        
        # Verify credentials are NOT loaded due to permission issue
        creds = provider.get_credentials("example.com")
        assert creds is None, "Should not load credentials with incorrect permissions"
    finally:
        netrc_path.unlink(missing_ok=True)


def test_malformed_netrc_file():
    """Test graceful handling of malformed netrc file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f:
        netrc_path = Path(f.name)
        # Write invalid netrc syntax
        f.write("this is not valid netrc syntax\n")
        f.write("machine without login\n")
    
    try:
        if os.name != 'nt':
            os.chmod(netrc_path, 0o600)
        
        provider = NetrcCredentialProvider(netrc_path=netrc_path, enabled=True)
        
        # Should handle gracefully and return None
        creds = provider.get_credentials("example.com")
        assert creds is None, "Should return None for malformed netrc file"
    finally:
        netrc_path.unlink(missing_ok=True)


def test_host_not_in_netrc():
    """Test that None is returned for hosts not in netrc."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".netrc") as f:
        netrc_path = Path(f.name)
        f.write("machine example.com\n")
        f.write("login testuser\n")
        f.write("password testpass\n")
    
    try:
        if os.name != 'nt':
            os.chmod(netrc_path, 0o600)
        
        provider = NetrcCredentialProvider(netrc_path=netrc_path, enabled=True)
        
        # Query for a different host
        creds = provider.get_credentials("different.com")
        assert creds is None, "Should return None for hosts not in netrc"
    finally:
        netrc_path.unlink(missing_ok=True)
