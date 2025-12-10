# PyInstaller hook for paddlex
# This ensures all paddlex dependencies and data files are collected

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# Collect all paddlex components
datas, binaries, hiddenimports = collect_all('paddlex')

# Explicitly include key submodules that paddleocr imports
hiddenimports += [
    'paddlex',
    'paddlex.utils',
    'paddlex.utils.deps',
    'paddlex.inference',
    'paddlex.inference.utils',
    'paddlex.inference.utils.benchmark',
    'paddlex.inference.pipelines',
    'paddlex.inference.pipelines.ocr',
    'paddlex.modules',
]

# Collect ALL submodules to ensure nothing is missed
try:
    hiddenimports += collect_submodules('paddlex')
except Exception:
    pass

try:
    hiddenimports += collect_submodules('paddlex.inference')
except Exception:
    pass

try:
    hiddenimports += collect_submodules('paddlex.modules')
except Exception:
    pass

try:
    hiddenimports += collect_submodules('paddlex.utils')
except Exception:
    pass
