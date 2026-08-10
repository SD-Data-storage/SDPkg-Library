import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sdpkg import extract_zip

def main():
    print("Preparing...")
    app_dir = os.path.dirname(__file__)
    neoprogrammer_dir = os.path.join(app_dir, "neoprogrammer")
    print("Extracting zip...")
    extract_zip(os.path.join(app_dir, "neoprogrammer.rar.zip", neoprogrammer_dir))
    print("Extraction finished!")

if __name__ == "__main__":
    main()
