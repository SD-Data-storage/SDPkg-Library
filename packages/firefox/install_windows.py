import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sdpkg import copy_directory_contents

SEVEN_ZIP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "7-zip", "7zip", "Files", "7-Zip", "7z.exe") #r"D:\Programs\7-Zip\7z.exe"

_GUID_RE = re.compile(
    r"^\{[0-9A-Fa-f]{8}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{12}\}$"
)


def _run_7z(*args):
    result = subprocess.run(
        [SEVEN_ZIP, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"7-Zip failed with exit code {result.returncode}\n"
            f"Command: {SEVEN_ZIP} {' '.join(args)}\n\n"
            f"stdout:\n{result.stdout}\n\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def extract_firefox_installation_from_msi(msi_path, output_path):
    """
    MSI
      -> Binary.WrappedExe
        -> core/
    """

    msi_path = Path(msi_path)
    output_path = Path(output_path)

    if not msi_path.is_file():
        raise FileNotFoundError(
            f"MSI file does not exist: {msi_path}"
        )

    if not Path(SEVEN_ZIP).is_file():
        raise FileNotFoundError(
            f"7-Zip was not found: {SEVEN_ZIP}"
        )

    with tempfile.TemporaryDirectory(prefix="firefox_msi_") as temp_dir:
        temp = Path(temp_dir)

        # ============================================================
        # 1. Extract Binary.GoogleChromeInstaller from the MSI
        # ============================================================

        msi_extract = temp / "msi"
        msi_extract.mkdir()

        print("[1/3] Extracting Binary.WrappedExe...")

        _run_7z(
            "e",
            str(msi_path),
            "Binary.WrappedExe",
            f"-o{msi_extract}",
            "-y",
        )

        binary = msi_extract / "Binary.WrappedExe"

        if not binary.is_file():
            # In case 7-Zip gives it a slightly different filename.
            candidates = list(msi_extract.iterdir())

            if len(candidates) == 1:
                binary = candidates[0]
            else:
                raise FileNotFoundError(
                    "Binary.WrappedExe was not found "
                    "after extracting the MSI."
                )

        print(f"      Found: {binary}")

        # ============================================================
        # 2. Binary.WrappedExe -> core/
        #
        # IMPORTANT:
        # Binary.WrappedExe is itself an archive.
        # ============================================================

        binary_extract = temp / "binary"
        binary_extract.mkdir()

        print("[2/3] Extracting core/ from Binary.WrappedExe...")

        _run_7z(
            "x",
            str(binary),
            f"-o{binary_extract}",
            "-y",
        )

        core_dir = binary_extract / "core"

        if not core_dir.is_dir():
            candidates = list(binary_extract.rglob("core"))

            if not candidates:
                raise FileNotFoundError(
                    "core/ was not found inside "
                    "Binary.WrappedExe."
                )

            updater_zip = candidates[0]

        print(f"      Found: {core_dir}")

        # ============================================================
        # 3. Copy core/ from Binary.WrappedExe
        # ============================================================

        print("[3/3] Copying core/ from Binary.WrappedExe...")
        os.makedirs(output_path, exist_ok=True)
        copy_directory_contents(core_dir, output_path)

        return output_path

def main():
    app_dir = os.path.dirname(__file__)
    msi_file_name_list = ["Firefox Setup amd64.msi", "Firefox Setup i686.msi", "Firefox Setup arm64.msi"]
    for item in msi_file_name_list:
        msi_path = os.path.join(app_dir, item)
        if os.path.exists(msi_path):
            print("Found " + item  + " at " + msi_path)
            print("Extracting firefox installation...")
            dir_path = os.path.join(app_dir, "firefox")
            extract_firefox_installation_from_msi(msi_path, dir_path)
            print("Finalizing files...")
            launch_bat_path = os.path.join(app_dir, "launch.bat")
            with open(launch_bat_path, "w") as f:
                f.write(r"""
"%~dp0firefox\firefox.exe" -profile="%~dp0Profile"
""")
            print("install.py finished!")
            return
    print("No msi files found :(")
    raise Exception("No msi files found :(")

if __name__ == "__main__":
    main()
