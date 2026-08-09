import os
import re
import sys
from html.parser import HTMLParser

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
    extract_zip,
    copy_directory_contents,
    remove_directory,
)


DOWNLOADS_URL = "https://ruffle.rs/downloads"


class RuffleDownloadsParser(HTMLParser):
    """
    Parses Ruffle's downloads page without depending on
    a specific table/class structure.

    Collects every link on the page together with its
    surrounding visible text.
    """

    def __init__(self):
        super().__init__()

        self.in_link = False
        self.current_href = None
        self.current_text = []

        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a":
            self.in_link = True
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.in_link:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            text = " ".join(
                "".join(self.current_text).split()
            )

            self.links.append({
                "text": text,
                "href": self.current_href,
            })

            self.in_link = False
            self.current_href = None
            self.current_text = []


def fetch_download_page():
    """
    Download the Ruffle downloads page.
    """

    return fetch_contents(DOWNLOADS_URL)


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


def normalize_url(url):
    """
    Convert relative Ruffle URLs into absolute URLs.
    """

    if not url:
        return None

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return "https://ruffle.rs" + url

    if url.startswith("http://"):
        return url

    if url.startswith("https://"):
        return url

    return "https://ruffle.rs/" + url.lstrip("/")


def parse_releases(html):
    """
    Parse Ruffle releases from download links.

    This parser intentionally does not depend on the
    current HTML table/class layout.
    """

    parser = RuffleDownloadsParser()
    parser.feed(html)

    releases = {}

    for link in parser.links:
        text = link["text"]
        href = normalize_url(link["href"])

        if not href:
            continue

        # Look for a Ruffle version in either the visible
        # link text or the download URL.
        combined = f"{text} {href}"

        matches = re.findall(
            r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b",
            combined
        )

        if not matches:
            continue

        version = matches[0]

        # Only consider actual Ruffle-looking downloads.
        lower = combined.lower()

        if "ruffle" not in lower:
            continue

        # Ignore unrelated links.
        if not (
            href.lower().endswith(".zip")
            or ".zip?" in href.lower()
        ):
            continue

        if version not in releases:
            releases[version] = {
                "version": version,
                "downloads": []
            }

        releases[version]["downloads"].append({
            "text": text,
            "href": href,
        })

    return list(releases.values())


def find_latest_release(releases):
    if not releases:
        raise RuntimeError(
            "Ruffle downloads page was fetched successfully, "
            "but no Ruffle ZIP releases could be detected. "
            "The download URL format may have changed."
        )

    return max(
        releases,
        key=lambda release: version_key(
            release["version"]
        )
    )


def find_windows_x64(release):
    """
    Find the Windows 64-bit desktop ZIP.

    Uses several indicators because the visible
    label/filename may change.
    """

    candidates = release["downloads"]

    # First try the visible text.
    for item in candidates:
        text = item["text"].lower()
        href = item["href"].lower()

        if (
            "windows" in text
            and (
                "64-bit" in text
                or "64 bit" in text
                or "x64" in text
            )
        ):
            return item["href"]

    # Then inspect the filename.
    for item in candidates:
        text = item["text"].lower()
        href = item["href"].lower()

        combined = text + " " + href

        if "windows" not in combined:
            continue

        if not (
            "x64" in combined
            or "win64" in combined
            or "64-bit" in combined
            or "64bit" in combined
        ):
            continue

        if href.endswith(".zip"):
            return item["href"]

    raise RuntimeError(
        f"Could not find a Windows 64-bit desktop "
        f"download for Ruffle {release['version']}."
    )


def main():
    """
    SDPkg installation entry point.
    """

    print("SDPkg: Installing Ruffle")
    print()

    # --------------------------------------------------------
    # Determine package directory
    # --------------------------------------------------------

    package_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    archive_path = os.path.join(
        package_dir,
        "ruffle.zip"
    )

    install_dir = os.path.join(
        package_dir,
        "ruffle"
    )

    # --------------------------------------------------------
    # Fetch Ruffle downloads page
    # --------------------------------------------------------

    print("Fetching Ruffle downloads page...")

    html = fetch_download_page()

    print(
        f"Received {len(html):,} bytes."
    )

    # --------------------------------------------------------
    # Parse releases
    # --------------------------------------------------------

    releases = parse_releases(html)

    print(
        f"Parsed {len(releases)} Ruffle releases."
    )

    if not releases:
        raise RuntimeError(
            "The Ruffle downloads page was fetched successfully, "
            "but no releases could be detected. "
            "The page's download-link structure may have changed."
        )

    # --------------------------------------------------------
    # Select latest release
    # --------------------------------------------------------

    release = find_latest_release(
        releases
    )

    version = release["version"]

    print(
        f"Latest Ruffle release: {version}"
    )

    # --------------------------------------------------------
    # Select Windows x64 desktop build
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    if os.path.exists(archive_path):
        os.remove(archive_path)

    print("Downloading Ruffle...")

    download_file(
        download_url,
        archive_path
    )

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    print("Extracting Ruffle...")

    os.makedirs(
        install_dir,
        exist_ok=True
    )

    extract_zip(
        archive_path,
        install_dir
    )

    # --------------------------------------------------------
    # Remove temporary archive
    # --------------------------------------------------------

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
