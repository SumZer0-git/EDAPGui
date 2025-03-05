#!/usr/bin/env python3
"""
Pre-downloads PaddleOCR models to ensure they're available for packaging.
This prevents the need to download models at runtime when the app is packaged.
"""

import os
import sys
from paddleocr import PaddleOCR

def main():
    # Redirect stdout to avoid tqdm progress bar issues
    original_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    
    try:
        # Initialize PaddleOCR which will download models
        ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        
        # Restore stdout for our messages
        sys.stdout = original_stdout
        
        # Print info about downloaded models
        paddleocr_dir = os.path.join(os.path.expanduser('~'), '.paddleocr')
        print(f'PaddleOCR models downloaded to: {paddleocr_dir}')
        
        if os.path.exists(paddleocr_dir):
            print("Downloaded model files:")
            for root, dirs, files in os.walk(paddleocr_dir):
                for file in files:
                    print(f"  {os.path.join(root, file)}")
        else:
            print("Warning: PaddleOCR directory not found!")
            
    except Exception as e:
        # Restore stdout in case of error
        sys.stdout = original_stdout
        print(f"Error downloading PaddleOCR models: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 