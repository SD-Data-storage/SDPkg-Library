import re
from pathlib import Path
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sdpkg import fetch_contents, extract_zip, download_file


DOWNLOAD_PAGE = "https://obsproject.com/download"


def main():
    package_dir = Path(__file__).resolve().parent
    obs_dir = package_dir / "obs"
    zip_path = package_dir / "obs.zip"

    print("Fetching OBS Studio download page...")

    page = fetch_contents(DOWNLOAD_PAGE)

    match = re.search(
        r'href="(https://cdn-fastly\.obsproject\.com/downloads/OBS-Studio-[^"]+-Windows-x64\.zip)"',
        page,
    )

    if not match:
        raise RuntimeError(
            "Could not find the latest OBS Studio Windows x64 ZIP URL "
            "in the OBS download page."
        )

    download_url = match.group(1)

    print(f"Found OBS Studio ZIP: {download_url}")
    print("Downloading OBS Studio...")

    download_file(download_url, zip_path)

    print(f"Extracting OBS Studio to: {obs_dir}")

    obs_dir.mkdir(parents=True, exist_ok=True)
    extract_zip(zip_path, obs_dir)

    zip_path.unlink()

    print("OBS Studio installation completed.")


if __name__ == "__main__":
    main()
