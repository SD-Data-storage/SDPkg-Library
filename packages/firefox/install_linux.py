import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sdpkg import extract_tar

def main():
    app_dir = os.path.dirname(__file__)
    tar_file_name_list = ["firefox-amd64.tar.gz", "firefox-i686.tar.gz", "firefox-arm64.tar.gz"]
    for item in tar_file_name_list:
        tar_path = os.path.join(app_dir, item)
        if os.path.exists(tar_path):
            print("Found " + item  + " at " + tar_path)
            print("Extracting firefox installation...")
            dir_path = os.path.join(app_dir, "firefox")
            extract_tar(tar_path, dir_path)
            print("Finalizing files...")
            launch_bat_path = os.path.join(app_dir, "launch.bat")
            with open(launch_bat_path, "w") as f:
                f.write(r"""
"%~dp0firefox\firefox.exe" -profile="%~dp0Profile"
""")
            print("install.py finished!")
            return
    print("No tar.gz files found :(")
    raise Exception("No tar.gz files found :(")

if __name__ == "__main__":
    main()
