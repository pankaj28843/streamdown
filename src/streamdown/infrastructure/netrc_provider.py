"""Netrc credential provider for HTTP authentication."""

import logging
import netrc
import os
import stat
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NetrcCredentialProvider:
    """Provides HTTP authentication credentials from netrc file.
    
    Follows aria2c conventions:
    - Default path: ~/.netrc
    - File permissions must be 600 (Unix only)
    - Disabled if no_netrc is True
    - Gracefully handles missing or malformed files
    """

    def __init__(
        self,
        netrc_path: Optional[Path] = None,
        enabled: bool = True,
    ):
        """Initialize netrc credential provider.
        
        Args:
            netrc_path: Custom path to netrc file. If None, uses ~/.netrc
            enabled: Whether netrc support is enabled
        """
        self.enabled = enabled
        self.netrc_path = netrc_path or Path.home() / ".netrc"
        self._netrc: Optional[netrc.netrc] = None
        
        if self.enabled:
            self.load_netrc()
    
    def load_netrc(self) -> None:
        """Load and parse netrc file with validation.
        
        Validates file permissions and handles errors gracefully.
        Logs warnings for permission issues or syntax errors.
        """
        if not self.netrc_path.exists():
            logger.debug(f"Netrc file not found at {self.netrc_path}, proceeding without netrc")
            return
        
        # Validate file permissions on Unix systems
        if os.name != 'nt':  # Not Windows
            file_stat = self.netrc_path.stat()
            file_mode = stat.S_IMODE(file_stat.st_mode)
            
            if file_mode != 0o600:
                logger.warning(
                    f"Netrc file {self.netrc_path} has insecure permissions {oct(file_mode)}. "
                    f"Expected 0o600. Ignoring netrc file for security."
                )
                return
        
        # Parse netrc file
        try:
            self._netrc = netrc.netrc(str(self.netrc_path))
            logger.debug(f"Successfully loaded netrc from {self.netrc_path}")
        except netrc.NetrcParseError as e:
            logger.warning(f"Failed to parse netrc file {self.netrc_path}: {e}. Proceeding without netrc.")
        except Exception as e:
            logger.warning(f"Unexpected error loading netrc file {self.netrc_path}: {e}. Proceeding without netrc.")
    
    def get_credentials(self, host: str) -> Optional[tuple[str, str]]:
        """Get credentials for a specific host.
        
        Args:
            host: Hostname to look up credentials for
            
        Returns:
            Tuple of (username, password) if credentials exist, None otherwise
        """
        if not self.enabled or self._netrc is None:
            return None
        
        try:
            auth = self._netrc.authenticators(host)
            if auth:
                # netrc.authenticators returns (login, account, password)
                # We use login and password for HTTP Basic Auth
                login, _, password = auth
                return (login, password)
        except Exception as e:
            logger.debug(f"Error retrieving credentials for {host}: {e}")
        
        return None
