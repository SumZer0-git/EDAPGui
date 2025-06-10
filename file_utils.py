"""
File utilities for EDAP

Provides encoding detection and consistent file reading across the codebase.
"""

import json
import os
from sys import platform
from EDlogger import logger

# Encoding constants in order of likelihood for Elite Dangerous files
ENCODING_UTF8 = 'utf-8'
ENCODING_UTF8_BOM = 'utf-8-sig'  # UTF-8 with Byte Order Mark
ENCODING_WINDOWS = 'windows-1252'  # Western European legacy encoding
ENCODING_CANDIDATES = [ENCODING_UTF8, ENCODING_UTF8_BOM, ENCODING_WINDOWS]

# Global encoding to use for files - detected at startup
_detected_encoding = None


def detect_encoding():
    """
    Detect the best encoding to use for JSON files.
    
    This function attempts to read a known ED JSON file (Status.json) with different
    encodings to determine which one works. Falls back to UTF-8 if no file exists.
    
    Returns:
        str: The detected encoding (one of ENCODING_CANDIDATES)
    """
    global _detected_encoding
    
    # Already detected
    if _detected_encoding is not None:
        return _detected_encoding

    # Get the EDAP folder path
    try:
        from WindowsKnownPaths import get_path, FOLDERID, UserHandle
        ed_folder = get_path(FOLDERID.SavedGames, UserHandle.current) + "/Frontier Developments/Elite Dangerous"
        test_file = os.path.join(ed_folder, "Status.json")
    except Exception:
        # Fallback if WindowsKnownPaths fails
        test_file = "./Status.json"
    
    # If test file exists, try to read it to detect encoding
    if os.path.exists(test_file):
        logger.info(f"Detecting encoding using test file: {test_file}")
        for encoding in ENCODING_CANDIDATES:
            try:
                logger.debug(f"Trying encoding: {encoding}")
                with open(test_file, 'r', encoding=encoding) as file:
                    json.load(file)  # Try to parse JSON
                logger.info(f"Detected Elite Dangerous file encoding: {encoding}")
                _detected_encoding = encoding
                return encoding
            except (UnicodeDecodeError, UnicodeError) as e:
                logger.debug(f"Encoding {encoding} failed with Unicode error: {e}")
                continue
            except json.JSONDecodeError as e:
                logger.debug(f"Encoding {encoding} succeeded but JSON parsing failed: {e}")
                continue
            except OSError as e:
                logger.warning(f"OS error reading test file {test_file}: {e}")
                break
    
    # Default to UTF-8 if no file exists or all encodings failed
    logger.info("No Elite Dangerous files found for encoding detection, defaulting to UTF-8")
    _detected_encoding = ENCODING_UTF8
    return _detected_encoding


def get_encoding():
    """
    Get the detected encoding for Elite Dangerous JSON files.
    
    Returns:
        str: The encoding to use for JSON files
    """
    if _detected_encoding is None:
        return detect_encoding()
    return _detected_encoding


def read_json_file(file_path):
    """
    Read a JSON file using the detected encoding.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        dict: Parsed JSON data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
        UnicodeDecodeError: If file can't be decoded with detected encoding
    """
    encoding = get_encoding()
    
    try:
        with open(file_path, 'r', encoding=encoding) as file:
            return json.load(file)
    except (UnicodeDecodeError, UnicodeError) as e:
        logger.warning(f"Failed to read JSON file {file_path} with detected encoding {encoding}: {e}")
        # Try UTF-8 as fallback
        if encoding != ENCODING_UTF8:
            logger.info(f"Retrying {file_path} with UTF-8 fallback")
            try:
                with open(file_path, 'r', encoding=ENCODING_UTF8) as file:
                    return json.load(file)
            except (UnicodeDecodeError, UnicodeError) as e2:
                raise UnicodeDecodeError(
                    f"Could not read {file_path} with {encoding} or UTF-8 fallback. "
                    f"File may contain unsupported characters or be corrupted."
                ) from e
        else:
            raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        raise
    except OSError as e:
        logger.error(f"OS error reading file {file_path}: {e}")
        raise


def read_text_file(file_path):
    """
    Read any text file using the detected encoding.
    
    Args:
        file_path (str): Path to the text file
        
    Returns:
        str: File contents as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        UnicodeDecodeError: If file can't be decoded with detected encoding
    """
    encoding = get_encoding()
    
    try:
        with open(file_path, 'r', encoding=encoding) as file:
            return file.read()
    except (UnicodeDecodeError, UnicodeError) as e:
        logger.warning(f"Failed to read text file {file_path} with detected encoding {encoding}: {e}")
        # Try UTF-8 as fallback
        if encoding != ENCODING_UTF8:
            logger.info(f"Retrying {file_path} with UTF-8 fallback")
            try:
                with open(file_path, 'r', encoding=ENCODING_UTF8) as file:
                    return file.read()
            except (UnicodeDecodeError, UnicodeError) as e2:
                raise UnicodeDecodeError(
                    f"Could not read {file_path} with {encoding} or UTF-8 fallback. "
                    f"File may contain unsupported characters or be corrupted."
                ) from e
        else:
            raise
    except OSError as e:
        logger.error(f"OS error reading file {file_path}: {e}")
        raise


def open_text_file(file_path, mode='r'):
    """
    Open a text file with the detected encoding.
    
    Args:
        file_path (str): Path to the text file
        mode (str): File open mode (default: 'r')
        
    Returns:
        file object: Opened file handle
        
    Note:
        Caller is responsible for closing the file handle
    """
    encoding = get_encoding()
    return open(file_path, mode, encoding=encoding)