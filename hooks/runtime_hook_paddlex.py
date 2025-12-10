# PyInstaller runtime hook for paddlex
# This hook MUST run BEFORE paddlex is imported anywhere
#
# Strategy:
# 1. Use an import hook to intercept paddlex.utils.deps and patch it after loading
# 2. Create the .version file for paddlex
# 3. Set environment variables to signal we're in a bundled app
#
# IMPORTANT: We must NOT inject fake parent modules (paddlex, paddlex.utils)
# as this would prevent the real modules from loading!

import os
import sys
import types


def setup_import_hook():
    """
    Set up an import hook that patches paddlex.utils.deps when it's loaded.
    This allows the real paddlex package to load normally, but patches
    the dependency checker to skip runtime checks.
    """
    if not hasattr(sys, '_MEIPASS'):
        return  # Only needed in PyInstaller bundle

    class PaddlexDepsImportHook:
        """
        Import hook that patches paddlex.utils.deps after it loads.
        """
        _patched = False
        
        def find_module(self, fullname, path=None):
            # Intercept paddlex.utils.deps import
            if fullname == 'paddlex.utils.deps' and not self._patched:
                return self
            return None

        def load_module(self, fullname):
            # If already in sys.modules and patched, return it
            if fullname in sys.modules and self._patched:
                return sys.modules[fullname]

            # Remove this finder temporarily to allow normal import
            if self in sys.meta_path:
                sys.meta_path.remove(self)
            
            try:
                import importlib
                module = importlib.import_module(fullname)

                # Patch the module functions
                self._patch_module(module)
                self._patched = True
                
                print(f"Runtime hook: Patched {fullname}")
                return module
            except ImportError as e:
                print(f"Runtime hook: Could not import {fullname}: {e}")
                # Create a stub module if import fails
                module = self._create_stub_module(fullname)
                self._patched = True
                return module
            finally:
                # Re-add this finder for any future imports
                if self not in sys.meta_path:
                    sys.meta_path.insert(0, self)
        
        def _patch_module(self, module):
            """Patch the deps module to skip dependency checks."""
            def patched_require_extra(*args, **kwargs):
                """No-op: Dependencies are bundled."""
                return None  # Never raise DependencyError

            module.require_extra = patched_require_extra
            
            # Patch other functions if they exist
            if hasattr(module, 'check_deps'):
                module.check_deps = lambda *a, **kw: None
            if hasattr(module, 'is_dep_available'):
                module.is_dep_available = lambda *a, **kw: True
            if hasattr(module, 'ensure_deps'):
                module.ensure_deps = lambda *a, **kw: None
            
            # Patch _wrapper if it exists - this is the decorator that calls require_extra
            if hasattr(module, '_wrapper'):
                original_wrapper = module._wrapper
                def patched_wrapper(*args, **kwargs):
                    """Patched wrapper that catches DependencyError."""
                    try:
                        return original_wrapper(*args, **kwargs)
                    except Exception as e:
                        # Check if it's a DependencyError
                        error_type = type(e).__name__
                        error_msg = str(e)
                        if 'DependencyError' in error_type or 'requires additional dependencies' in error_msg:
                            # Silently ignore - dependencies are bundled
                            return None
                        raise
                module._wrapper = patched_wrapper
                print("Runtime hook: Patched _wrapper function")
        
        def _create_stub_module(self, fullname):
            """Create a stub module if the real one can't be imported."""
            print(f"Runtime hook: Creating stub module for {fullname}")
            
            stub = types.ModuleType(fullname)
            stub.require_extra = lambda *a, **kw: None
            stub.check_deps = lambda *a, **kw: None
            stub.is_dep_available = lambda *a, **kw: True
            stub.ensure_deps = lambda *a, **kw: None
            
            class DependencyError(Exception):
                pass
            stub.DependencyError = DependencyError
            
            sys.modules[fullname] = stub
            return stub

    # Install the import hook at the start of meta_path
    sys.meta_path.insert(0, PaddlexDepsImportHook())
    print("Runtime hook: Installed paddlex.utils.deps import hook")


def ensure_paddlex_version():
    """Create the paddlex .version file if it doesn't exist."""
    version = '3.3.10'  # Will be updated by build script

    if not hasattr(sys, '_MEIPASS'):
        return  # Not needed when running normally

    base_path = sys._MEIPASS
    paddlex_dir = os.path.join(base_path, 'paddlex')
    version_file = os.path.join(paddlex_dir, '.version')

    # Create directory if it doesn't exist
    try:
        os.makedirs(paddlex_dir, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create paddlex directory: {e}")
        return

    # Create .version file if it doesn't exist
    if not os.path.exists(version_file):
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(version)
            print(f"Runtime hook: Created {version_file} with version {version}")
        except Exception as e:
            print(f"Warning: Could not create .version file: {e}")


def set_environment_flags():
    """Set environment variables to signal we're in a bundled app."""
    if hasattr(sys, '_MEIPASS'):
        os.environ['PADDLEX_SKIP_DEPS_CHECK'] = '1'
        os.environ['PADDLEX_BUNDLED'] = '1'
        os.environ['PYINSTALLER_BUNDLED'] = '1'


# Run all setup functions immediately when this hook is loaded
# Order matters!
set_environment_flags()
setup_import_hook()
ensure_paddlex_version()

print("Runtime hook: PaddleX setup complete")
