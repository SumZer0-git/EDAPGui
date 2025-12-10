"""
Post-build script to patch paddlex dependency checking in PyInstaller bundle.

This script modifies the bundled paddlex source files to bypass runtime dependency
checks that fail in PyInstaller environments.

Run this after PyInstaller builds but before packaging the artifact.
"""

import os
import sys
import re
from pathlib import Path


def find_deps_module(internal_dir: Path) -> Path | None:
    """
    Find the paddlex.utils.deps module in the bundle.
    It could be in several locations depending on how PyInstaller bundled it.
    """
    possible_paths = [
        internal_dir / 'paddlex' / 'utils' / 'deps.py',
        internal_dir / 'paddlex' / 'utils' / 'deps.pyc',
    ]
    
    # Also search recursively for deps.py in paddlex directories
    for paddlex_dir in internal_dir.glob('**/paddlex'):
        deps_path = paddlex_dir / 'utils' / 'deps.py'
        if deps_path.exists():
            return deps_path
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def patch_deps_file(deps_path: Path) -> bool:
    """
    Patch the deps.py file to make require_extra a no-op.
    Uses a comprehensive approach that replaces function bodies and adds overrides.
    """
    print(f"Patching {deps_path}")
    
    try:
        content = deps_path.read_text(encoding='utf-8')
        original_content = content
        
        # Check if already patched
        if '# PATCHED_FOR_PYINSTALLER' in content:
            print(f"File already patched: {deps_path}")
            return True
        
        # Strategy: Replace function bodies with pass statements
        # Match function definitions with their entire bodies (until next def/class or end of file)
        
        # Pattern 1: Replace require_extra function body
        # This matches: def require_extra(...): ... everything until next def/class/end
        require_extra_pattern = r'(def require_extra\s*\([^)]*\)\s*:)(.*?)(?=\n\s*(?:def |class |@|\Z))'
        
        def replace_require_extra(match):
            func_def = match.group(1)
            return f"{func_def}\n    \"\"\"Patched: Skip dependency check in PyInstaller bundle.\"\"\"\n    return  # Skip check in bundle\n"
        
        content = re.sub(require_extra_pattern, replace_require_extra, content, flags=re.DOTALL)
        
        # Pattern 2: Replace check_deps function body
        check_deps_pattern = r'(def check_deps\s*\([^)]*\)\s*:)(.*?)(?=\n\s*(?:def |class |@|\Z))'
        
        def replace_check_deps(match):
            func_def = match.group(1)
            return f"{func_def}\n    \"\"\"Patched: Skip dependency check in PyInstaller bundle.\"\"\"\n    return  # Skip check in bundle\n"
        
        content = re.sub(check_deps_pattern, replace_check_deps, content, flags=re.DOTALL)
        
        # Pattern 3: Replace _wrapper function if it exists (this is the decorator that calls require_extra)
        wrapper_pattern = r'(def _wrapper\s*\([^)]*\)\s*:)(.*?)(?=\n\s*(?:def |class |@|\Z))'
        
        def replace_wrapper(match):
            func_def = match.group(1)
            # Keep the wrapper structure but make require_extra call a no-op
            wrapper_body = match.group(2)
            # Replace any calls to require_extra with pass
            wrapper_body = re.sub(r'require_extra\([^)]*\)', 'pass  # Patched: skip dep check', wrapper_body)
            return f"{func_def}{wrapper_body}"
        
        content = re.sub(wrapper_pattern, replace_wrapper, content, flags=re.DOTALL)
        
        # Write regex changes if any were made
        if content != original_content:
            deps_path.write_text(content, encoding='utf-8')
            print(f"Applied regex patches to {deps_path}")
        
        # Always apply the comprehensive end-of-file override (most reliable method)
        return patch_deps_file_alternative(deps_path)
            
    except Exception as e:
        print(f"Error patching {deps_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def patch_deps_file_alternative(deps_path: Path) -> bool:
    """
    Alternative patching approach: append override code at the end of the file.
    This is more reliable than regex replacement.
    """
    try:
        content = deps_path.read_text(encoding='utf-8')
        
        # Check if already patched
        if '# PATCHED_FOR_PYINSTALLER_OVERRIDE' in content:
            print(f"File already patched: {deps_path}")
            return True
        
        # Add comprehensive override at the end of the file
        # This runs after all functions are defined, so it will override them
        override_code = '''

# ============================================================================
# PATCHED_FOR_PYINSTALLER_OVERRIDE
# This code overrides dependency checking functions to skip checks in bundles
# ============================================================================
import sys as _pyinstaller_sys_check

if hasattr(_pyinstaller_sys_check, '_MEIPASS'):
    # We're in a PyInstaller bundle - override all dependency check functions
    
    # Store original functions if they exist
    _original_require_extra = globals().get('require_extra')
    _original_check_deps = globals().get('check_deps')
    _original_wrapper = globals().get('_wrapper')
    
    # Override require_extra to do nothing - never raise DependencyError
    def require_extra(*args, **kwargs):
        """Patched: Skip dependency check in PyInstaller bundle."""
        # Do absolutely nothing - dependencies are bundled
        return None
    
    # Override check_deps to do nothing
    def check_deps(*args, **kwargs):
        """Patched: Skip dependency check in PyInstaller bundle."""
        return
    
    # Override _wrapper to catch and ignore DependencyError
    # The wrapper calls require_extra, which we've patched, but we also catch errors as backup
    if _original_wrapper is not None:
        def _wrapper(*args, **kwargs):
            """Patched wrapper that catches and ignores DependencyError."""
            try:
                return _original_wrapper(*args, **kwargs)
            except DependencyError:
                # Silently ignore - dependencies are bundled
                return
            except Exception as e:
                # Check if it's a DependencyError by name or message
                error_type = type(e).__name__
                error_msg = str(e)
                if 'DependencyError' in error_type or 'requires additional dependencies' in error_msg:
                    # Silently ignore - dependencies are bundled
                    return
                # Re-raise other exceptions
                raise
        globals()['_wrapper'] = _wrapper
    
    # Also patch any other functions that might check dependencies
    if 'is_dep_available' in globals():
        def is_dep_available(*args, **kwargs):
            """Always return True in bundle."""
            return True
        globals()['is_dep_available'] = is_dep_available
    
    # Make sure the overrides are in the module namespace
    globals()['require_extra'] = require_extra
    globals()['check_deps'] = check_deps
    
    print("PaddleX dependency checks disabled for PyInstaller bundle")
# ============================================================================
'''
        
        content += override_code
        deps_path.write_text(content, encoding='utf-8')
        print(f"Successfully patched {deps_path} using alternative approach (end-of-file override)")
        return True
        
    except Exception as e:
        print(f"Error in alternative patching {deps_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_deps_stub(internal_dir: Path) -> bool:
    """
    Create a stub deps.py file that does nothing.
    This is used if we can't find the original to patch.
    """
    paddlex_utils_dir = internal_dir / 'paddlex' / 'utils'
    paddlex_utils_dir.mkdir(parents=True, exist_ok=True)
    
    deps_path = paddlex_utils_dir / 'deps.py'
    
    stub_content = '''"""
Stub module for paddlex.utils.deps
Created by PyInstaller post-build patch script.
All dependency checks are disabled in bundled applications.
"""

class DependencyError(Exception):
    """Exception for missing dependencies (never raised in bundle)."""
    pass


def require_extra(*args, **kwargs):
    """No-op: Dependencies are bundled with the application."""
    pass


def check_deps(*args, **kwargs):
    """No-op: Dependencies are bundled with the application."""
    pass


def is_dep_available(*args, **kwargs):
    """Always returns True: Dependencies are bundled."""
    return True


def ensure_deps(*args, **kwargs):
    """No-op: Dependencies are bundled with the application."""
    pass


def get_extra_deps(*args, **kwargs):
    """Returns empty dict: No extra deps needed in bundle."""
    return {}
'''
    
    try:
        deps_path.write_text(stub_content, encoding='utf-8')
        print(f"Created stub deps module at {deps_path}")
        
        # Also create __init__.py if it doesn't exist
        init_path = paddlex_utils_dir / '__init__.py'
        if not init_path.exists():
            init_path.write_text('# paddlex.utils package\n', encoding='utf-8')
            print(f"Created {init_path}")
        
        return True
    except Exception as e:
        print(f"Error creating stub: {e}")
        return False


def patch_pipeline_init(internal_dir: Path) -> bool:
    """
    Patch paddlex pipeline __init__ files that might import and check deps.
    """
    patterns_to_find = [
        '**/paddlex/**/pipelines/**/__init__.py',
        '**/paddlex/**/pipelines/**/ocr*.py',
        '**/paddlex/**/__init__.py',
    ]
    
    patched_any = False
    
    for pattern in patterns_to_find:
        for filepath in internal_dir.glob(pattern):
            try:
                content = filepath.read_text(encoding='utf-8')
                
                # Skip if already patched
                if '# DEPS_PATCHED' in content:
                    continue
                
                # Check if file imports or uses require_extra
                if 'require_extra' in content or 'from .deps import' in content or 'from ..deps import' in content:
                    # Add a patch at the start of the file
                    patch = '''# DEPS_PATCHED
import sys as _patch_sys
if hasattr(_patch_sys, '_MEIPASS'):
    # In PyInstaller bundle, mock the require_extra function
    import paddlex.utils.deps as _deps_module
    _deps_module.require_extra = lambda *a, **kw: None
    if hasattr(_deps_module, 'check_deps'):
        _deps_module.check_deps = lambda *a, **kw: None

'''
                    content = patch + content
                    filepath.write_text(content, encoding='utf-8')
                    print(f"Patched {filepath}")
                    patched_any = True
                    
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
    
    return patched_any


def main():
    """Main entry point for the patch script."""
    # Determine the bundle directory
    if len(sys.argv) > 1:
        bundle_dir = Path(sys.argv[1])
    else:
        # Default location
        bundle_dir = Path('.') / 'dist' / 'EDAP-Autopilot'
    
    internal_dir = bundle_dir / '_internal'
    
    if not internal_dir.exists():
        print(f"ERROR: Bundle directory not found: {internal_dir}")
        print("Usage: python patch_paddlex_bundle.py [bundle_directory]")
        sys.exit(1)
    
    print(f"Patching PaddleX in bundle: {internal_dir}")
    print("=" * 60)
    
    success = True
    
    # Step 1: Try to find and patch the deps module
    deps_path = find_deps_module(internal_dir)
    if deps_path:
        print(f"Found deps module: {deps_path}")
        if not patch_deps_file(deps_path):
            success = False
        
        # Verify the patch was applied
        print(f"\nVerifying patch in {deps_path}...")
        try:
            patched_content = deps_path.read_text(encoding='utf-8')
            if 'PATCHED_FOR_PYINSTALLER' in patched_content or 'PATCHED_FOR_PYINSTALLER_OVERRIDE' in patched_content:
                print("[OK] Patch verification: Override code found in file")
            if 'def require_extra' in patched_content:
                # Check if it's been patched
                if 'return None' in patched_content or 'return  # Skip' in patched_content or 'PATCHED' in patched_content:
                    print("[OK] Patch verification: require_extra appears to be patched")
                else:
                    print("[WARN] Warning: require_extra found but may not be fully patched")
        except Exception as e:
            print(f"[WARN] Warning: Could not verify patch: {e}")
    else:
        print("deps.py not found, creating stub module")
        if not create_deps_stub(internal_dir):
            success = False
    
    # Step 2: Patch any pipeline files that use require_extra
    print("\nPatching pipeline files...")
    patch_pipeline_init(internal_dir)
    
    # Step 3: Create/verify the .version file
    version_file = internal_dir / 'paddlex' / '.version'
    if not version_file.exists():
        try:
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text('3.3.10', encoding='utf-8')
            print(f"Created version file: {version_file}")
        except Exception as e:
            print(f"Error creating version file: {e}")
    else:
        print(f"Version file exists: {version_file}")
    
    print("\n" + "=" * 60)
    if success:
        print("Patching completed successfully!")
    else:
        print("Patching completed with some errors (see above)")
        sys.exit(1)


if __name__ == '__main__':
    main()

