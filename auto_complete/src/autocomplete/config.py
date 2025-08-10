"""
Configuration Module for Autocomplete System

This module contains all configuration constants and settings used throughout
the autocomplete system. It centralizes configuration values to make them
easy to modify and maintain.

The configuration includes:
- Search parameters (TOP_K, GRAM)
- Feature flags (BUILD_INDEX)
- File processing settings (ENCODING, GLOB_PATTERN)

All constants are documented with their purpose and usage context.
Modifying these values will affect the behavior of the entire system.

Author: Google Team 4
"""

# src/autocomplete/config.py

# Search and ranking configuration
TOP_K = 5
"""
Maximum number of completion suggestions to return.
This controls how many results are shown to the user.
"""

GRAM = 3
"""
N-gram size for building inverted index (if enabled).
Larger values provide more context but increase memory usage.
"""

BUILD_INDEX = False
"""
Flag to control whether to build an n-gram inverted index.
When True, builds an index for faster substring matching.
When False, uses linear search through all sentences.
"""

# File processing configuration
ENCODING = "utf-8"
"""
Text encoding for reading input files.
Used when opening .txt files for corpus loading.
"""

GLOB_PATTERN = "*.txt"
"""
File pattern for corpus loading.
Only files matching this pattern will be processed.
Supports standard glob syntax (e.g., "*.txt", "**/*.md").
"""
