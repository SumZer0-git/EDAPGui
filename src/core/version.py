"""Version of the application. This is the single place where the version is defined.

The release workflow checks that the pushed tag (v<version>) matches __version__."""

__version__ = "1.7.0"

# Shown in the footer and the log
EDAP_VERSION = f"V{__version__}"
