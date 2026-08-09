import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

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


def extract_google_chrome_setup_from_msi(msi_path, output_path):
    """
    MSI
      -> Binary.GoogleChromeInstaller
        -> updater.7z
          -> bin/Offline/{GUID}/{GUID}/{version}_chrome_installer.exe
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

    with tempfile.TemporaryDirectory(prefix="chrome_msi_") as temp_dir:
        temp = Path(temp_dir)

        # ============================================================
        # 1. Extract Binary.GoogleChromeInstaller from the MSI
        # ============================================================

        msi_extract = temp / "msi"
        msi_extract.mkdir()

        print("[1/5] Extracting Binary.GoogleChromeInstaller...")

        _run_7z(
            "e",
            str(msi_path),
            "Binary.GoogleChromeInstaller",
            f"-o{msi_extract}",
            "-y",
        )

        binary = msi_extract / "Binary.GoogleChromeInstaller"

        if not binary.is_file():
            # In case 7-Zip gives it a slightly different filename.
            candidates = list(msi_extract.iterdir())

            if len(candidates) == 1:
                binary = candidates[0]
            else:
                raise FileNotFoundError(
                    "Binary.GoogleChromeInstaller was not found "
                    "after extracting the MSI."
                )

        print(f"      Found: {binary}")

        # ============================================================
        # 2. Binary.GoogleChromeInstaller -> updater.7z
        #
        # IMPORTANT:
        # Binary.GoogleChromeInstaller is itself an archive.
        # ============================================================

        binary_extract = temp / "binary"
        binary_extract.mkdir()

        print("[2/5] Extracting updater.7z from Binary.GoogleChromeInstaller...")

        _run_7z(
            "x",
            str(binary),
            f"-o{binary_extract}",
            "-y",
        )

        updater_zip = binary_extract / "updater.7z"

        if not updater_zip.is_file():
            candidates = list(binary_extract.rglob("updater.7z"))

            if not candidates:
                raise FileNotFoundError(
                    "updater.7z was not found inside "
                    "Binary.GoogleChromeInstaller."
                )

            updater_zip = candidates[0]

        print(f"      Found: {updater_zip}")

        # ============================================================
        # 3. Extract bin/ from updater.7z
        # ============================================================

        updater_extract = temp / "updater"
        updater_extract.mkdir()

        print("[3/5] Extracting bin/ from updater.7z...")

        _run_7z(
            "x",
            str(updater_zip),
            "bin\\*",
            f"-o{updater_extract}",
            "-y",
        )

        bin_dir = updater_extract / "bin"

        if not bin_dir.is_dir():
            raise FileNotFoundError(
                f"bin directory was not found in {updater_zip}"
            )

        # ============================================================
        # 4. Find Offline/{GUID}/{GUID}
        # ============================================================

        offline_dir = bin_dir / "Offline"

        if not offline_dir.is_dir():
            raise FileNotFoundError(
                f"Offline directory was not found: {offline_dir}"
            )

        print("[4/5] Searching for Chrome installer...")

        first_guid_dirs = [
            p
            for p in offline_dir.iterdir()
            if p.is_dir() and _GUID_RE.fullmatch(p.name)
        ]

        if not first_guid_dirs:
            raise FileNotFoundError(
                f"No GUID directory found in {offline_dir}"
            )

        first_guid = first_guid_dirs[0]

        print(f"      First GUID:  {first_guid.name}")

        second_guid_dirs = [
            p
            for p in first_guid.iterdir()
            if p.is_dir() and _GUID_RE.fullmatch(p.name)
        ]

        if not second_guid_dirs:
            raise FileNotFoundError(
                f"No second GUID directory found in {first_guid}"
            )

        second_guid = second_guid_dirs[0]

        print(f"      Second GUID: {second_guid.name}")

        installers = list(
            second_guid.glob("*_chrome_installer.exe")
        )

        if not installers:
            raise FileNotFoundError(
                f"No *_chrome_installer.exe found in {second_guid}"
            )

        chrome_installer = installers[0]

        print(f"      Chrome installer: {chrome_installer.name}")

        # ============================================================
        # 5. Copy final installer
        # ============================================================

        print("[5/5] Copying Chrome installer...")

        shutil.copy2(
            chrome_installer,
            output_path,
        )

        print(f"      Output: {output_path}")

        return output_path

def extract_chrome_install_from_setup(setup_path, output_path):
    """
    Extract a Chrome setup executable.

    Extraction chain:

        setup.exe
          └── chrome.7z
                └── Chrome-Bin/
                      ├── chrome.exe
                      ├── ...
                      └── ...

    The contents of Chrome-Bin are copied directly into output_path.
    """

    setup_path = Path(setup_path)
    output_path = Path(output_path)

    if not setup_path.is_file():
        raise FileNotFoundError(
            f"Chrome setup executable does not exist: {setup_path}"
        )

    if not Path(SEVEN_ZIP).is_file():
        raise FileNotFoundError(
            f"7-Zip was not found: {SEVEN_ZIP}"
        )

    output_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="chrome_setup_") as temp_dir:
        temp = Path(temp_dir)

        # ============================================================
        # 1. Extract setup.exe
        # ============================================================

        setup_extract = temp / "setup"
        setup_extract.mkdir()

        print("[1/3] Extracting Chrome setup executable...")

        _run_7z(
            "x",
            str(setup_path),
            f"-o{setup_extract}",
            "-y",
        )

        # ============================================================
        # 2. Find and extract chrome.7z
        # ============================================================

        chrome_7z = setup_extract / "chrome.7z"

        if not chrome_7z.is_file():
            candidates = list(setup_extract.rglob("chrome.7z"))

            if not candidates:
                raise FileNotFoundError(
                    "chrome.7z was not found inside the Chrome setup executable."
                )

            chrome_7z = candidates[0]

        print(f"[2/3] Found: {chrome_7z}")

        chrome_extract = temp / "chrome"
        chrome_extract.mkdir()

        print("      Extracting chrome.7z...")

        _run_7z(
            "x",
            str(chrome_7z),
            f"-o{chrome_extract}",
            "-y",
        )

        # ============================================================
        # 3. Copy Chrome-Bin contents to output_path
        # ============================================================

        chrome_bin = chrome_extract / "Chrome-Bin"

        if not chrome_bin.is_dir():
            # Handle archives where Chrome-Bin is nested somewhere.
            candidates = [
                p
                for p in chrome_extract.rglob("Chrome-Bin")
                if p.is_dir()
            ]

            if not candidates:
                raise FileNotFoundError(
                    "Chrome-Bin directory was not found inside chrome.7z."
                )

            chrome_bin = candidates[0]

        print(f"[3/3] Copying Chrome-Bin contents...")
        print(f"      Source: {chrome_bin}")
        print(f"      Output: {output_path}")

        # Copy the CONTENTS of Chrome-Bin, not Chrome-Bin itself.
        for item in chrome_bin.iterdir():
            destination = output_path / item.name

            if item.is_dir():
                shutil.copytree(
                    item,
                    destination,
                    dirs_exist_ok=True,
                )
            else:
                shutil.copy2(
                    item,
                    destination,
                )

        print("      Done!")

    return output_path

def main():
    app_dir = os.path.dirname(__file__)
    msi_file_name_list = ["googlechromestandaloneenterprise.msi", "googlechromestandaloneenterprise64.msi"]
    for item in msi_file_name_list:
        msi_path = os.path.join(app_dir, item)
        if os.path.exists(msi_path):
            print("Found " + item  + " at " + msi_path)
            print("Extracting chrome_installer.exe")
            exe_path = os.path.join(app_dir, "chrome_installer.exe")
            extract_google_chrome_setup_from_msi(msi_path, exe_path)
            print("Generating chrome directory...")
            dir_path = os.path.join(app_dir, "chrome")
            extract_chrome_install_from_setup(exe_path, dir_path)
            print("Finalizing files...")
            launch_bat_path = os.path.join(app_dir, "launch.bat")
            with open(launch_bat_path, "w") as f:
                f.write(r"""
"%~dp0chrome\chrome.exe" --password-store=basic --user-data-dir="%~dp0UserData"
""")
            print("install.py finished!")
            return
    print("No msi files found :(")
    raise Exception("No msi files found :(")

if __name__ == "__main__":
    main()
