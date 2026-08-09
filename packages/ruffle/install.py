import os
import re
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(__file__)
        )
    )
)

from sdpkg import (
    download_file,
    fetch_contents,
    extract_tar,
    copy_directory_contents,
    remove_directory,
)


DOWNLOADS_URL = "https://ruffle.rs/downloads"


def fetch_download_page():
    """
    Download the Ruffle downloads page.
    """

    return fetch_contents(DOWNLOADS_URL)


def parse_download_links(html):
    """
    Parse EVERY href= instance from the Ruffle downloads page.

    Only .tar.gz downloads are retained.
    """

    links = re.findall(
        r'''href\s*=\s*["']([^"']+\.tar\.gz(?:\?[^"']*)?)["']''',
        html,
        re.IGNORECASE
    )

    results = []

    for url in links:
        # Convert relative URLs to absolute URLs.
        if url.startswith("//"):
            url = "https:" + url

        elif url.startswith("/"):
            url = "https://ruffle.rs" + url

        elif not url.startswith(("http://", "https://")):
            url = "https://ruffle.rs/" + url.lstrip("/")

        results.append(url)

    return results


def extract_version(url):
    """
    Extract a semantic version from a Ruffle download URL.

    Examples:

        ruffle-nightly-0.5.0-windows-x86_64.tar.gz
            -> 0.5.0

        ruffle-0.5.0-windows-x86_64.tar.gz
            -> 0.5.0
    """

    match = re.search(
        r'(?<!\d)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)(?!\d)',
        url
    )

    if not match:
        return None

    return match.group(1)


def parse_releases(html):
    """
    Parse all Ruffle .tar.gz downloads and group them by version.
    """

    links = parse_download_links(html)

    releases = {}

    for url in links:
        version = extract_version(url)

        if not version:
            continue

        if version not in releases:
            releases[version] = {
                "version": version,
                "downloads": []
            }

        releases[version]["downloads"].append(url)

    return list(releases.values())


def version_key(version):
    """
    Convert a Ruffle version into something sortable.

    Example:
        0.5.0 -> (0, 5, 0)
    """

    match = re.match(
        r"^(\d+)\.(\d+)\.(\d+)",
        version
    )

    if not match:
        return (0, 0, 0)

    return tuple(
        int(x)
        for x in match.groups()
    )


def find_latest_release(releases):
    if not releases:
        raise RuntimeError(
            "Ruffle downloads page was fetched successfully, "
            "but no versioned .tar.gz downloads were found."
        )

    return max(
        releases,
        key=lambda release: version_key(
            release["version"]
        )
    )


def find_windows_x64(release):
    """
    Find the Windows x86_64 / amd64 Ruffle download.
    """

    downloads = release["downloads"]

    # Print candidates while debugging the package.
    print()
    print(
        f"Found {len(downloads)} downloads for "
        f"Ruffle {release['version']}:"
    )

    for url in downloads:
        print(f"  {url}")

    print()

    # Prefer explicit x86_64 naming.
    for url in downloads:
        lower = url.lower()

        if (
            "windows" in lower
            and (
                "x86_64" in lower
                or "amd64" in lower
                or "win64" in lower
            )
            and lower.endswith(".tar.gz")
        ):
            return url

    # Fallback: Windows + 64-bit.
    for url in downloads:
        lower = url.lower()

        if (
            "windows" in lower
            and "64" in lower
            and lower.endswith(".tar.gz")
        ):
            return url

    raise RuntimeError(
        f"Could not find a Windows 64-bit desktop "
        f".tar.gz download for Ruffle {release['version']}."
    )


def main():
    """
    SDPkg installation entry point.
    """

    print("SDPkg: Installing Ruffle")
    print()

    package_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    archive_path = os.path.join(
        package_dir,
        "ruffle.tar.gz"
    )

    install_dir = os.path.join(
        package_dir,
        "ruffle"
    )

    print("Fetching Ruffle downloads page...")

    html = fetch_download_page()

    print(
        f"Received {len(html):,} bytes."
    )

    releases = parse_releases(html)

    print(
        f"Parsed {len(releases)} Ruffle releases."
    )

    if not releases:
        raise RuntimeError(
            "The Ruffle downloads page was fetched successfully, "
            "but no releases could be detected."
        )

    release = find_latest_release(
        releases
    )

    version = release["version"]

    print(
        f"Latest Ruffle release: {version}"
    )

    download_url = find_windows_x64(
        release
    )

    print(
        "Selected Windows 64-bit build:"
    )
    print(
        f"  {download_url}"
    )
    print()

    if os.path.exists(archive_path):
        os.remove(archive_path)

    print("Downloading Ruffle...")

    download_file(
        download_url,
        archive_path
    )

    print("Extracting Ruffle...")

    os.makedirs(
        install_dir,
        exist_ok=True
    )

    extract_tar(
        archive_path,
        install_dir
    )

    if os.path.exists(archive_path):
        os.remove(archive_path)

    print()
    print(
        "Ruffle installation completed successfully."
    )
    print(
        f"Version: {version}"
    )
    print(
        f"Files:   {install_dir}"
    )


if __name__ == "__main__":
    main()
