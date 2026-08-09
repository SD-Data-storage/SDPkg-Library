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
)

DOWNLOADS_URL = "https://ruffle.rs/downloads"

GITHUB_RELEASE_BASE = (
    "https://github.com/ruffle-rs/ruffle/releases/download/"
)


class RuffleDownloadsParser(HTMLParser):
    """
    Parses the Ruffle downloads page.

    Collects every download link from the releases table.

    A release is represented as:

        {
            "version": "0.5.0",
            "downloads": {
                "Windows (64-bit)": "...",
                "Linux (x86_64)": "...",
                ...
            }
        }
    """

    def __init__(self):
        super().__init__()

        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_link = False

        self.current_cell = []
        self.current_href = None
        self.current_row = []

        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "table":
            classes = attrs.get("class", "")

            if "releases-module" in classes:
                self.in_table = True

        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []

        elif self.in_row and tag in ("td", "th"):
            self.in_cell = True
            self.current_cell = []

        elif self.in_cell and tag == "a":
            self.in_link = True
            self.current_href = attrs.get("href")

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            self.in_link = False

        elif tag in ("td", "th") and self.in_cell:
            text = " ".join(
                "".join(self.current_cell).split()
            )

            self.current_row.append(
                {
                    "text": text,
                    "href": self.current_href,
                }
            )

            self.current_cell = []
            self.current_href = None
            self.in_cell = False

        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)

            self.current_row = []
            self.in_row = False

        elif tag == "table" and self.in_table:
            self.in_table = False


def fetch_download_page():
    """
    Fetch the Ruffle downloads page.
    """

    return fetch_contents(DOWNLOADS_URL)


def normalize_url(url):
    """
    Convert a Ruffle download URL into an absolute URL.
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


def looks_like_version(value):
    """
    Check whether a string looks like a Ruffle version.

    Examples:

        0.5.0
        0.5.0-beta
        1.2.3-rc1
    """

    return bool(
        re.fullmatch(
            r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?",
            value.strip()
        )
    )


def parse_releases(html):
    """
    Parse releases from the Ruffle downloads page.

    Every href is preserved. We do NOT restrict this to .tar.gz
    because Windows uses .zip.
    """

    parser = RuffleDownloadsParser()
    parser.feed(html)

    releases = []

    for row in parser.rows:
        if not row:
            continue

        version = row[0]["text"].strip()

        # Skip header rows.
        if version.lower() == "version":
            continue

        # Ignore rows that aren't release versions.
        if not looks_like_version(version):
            continue

        downloads = {}

        for cell in row[1:]:
            name = cell["text"].strip()
            href = cell["href"]

            if not href:
                continue

            href = normalize_url(href)

            if not href:
                continue

            # Keep the visible label when available.
            if name:
                downloads[name] = href

            # Also keep the URL itself so that assets whose
            # visible text changes are still discoverable.
            downloads.setdefault(
                href,
                href
            )

        releases.append(
            {
                "version": version,
                "downloads": downloads,
            }
        )

    return releases


def version_key(version):
    """
    Convert a Ruffle version into a sortable tuple.

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
    """
    Find the newest Ruffle release.
    """

    if not releases:
        raise RuntimeError(
            "Ruffle downloads page was parsed successfully, "
            "but no releases were found."
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

    Ruffle Windows desktop builds are ZIP archives,
    not .tar.gz archives.
    """

    downloads = release["downloads"]

    # --------------------------------------------------------
    # Exact visible-label match
    # --------------------------------------------------------

    preferred_labels = (
        "Windows (64-bit)",
        "Windows 64-bit",
        "Windows (x86_64)",
        "Windows x86_64",
        "Windows (x64)",
        "Windows x64",
    )

    for label in preferred_labels:
        url = downloads.get(label)

        if not url:
            continue

        if url.lower().endswith(".zip"):
            return url

    # --------------------------------------------------------
    # Search every discovered href
    # --------------------------------------------------------

    candidates = []

    seen = set()

    for name, url in downloads.items():
        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        lower_name = name.lower()
        lower_url = url.lower()

        # Windows only.
        if "windows" not in lower_name and "windows" not in lower_url:
            continue

        # Desktop Windows build should be ZIP.
        if not lower_url.endswith(".zip"):
            continue

        # Reject web/self-hosted builds.
        if "web" in lower_url:
            continue

        if "selfhosted" in lower_url:
            continue

        if "self-hosted" in lower_url:
            continue

        # Reject obvious ARM builds.
        if "arm64" in lower_url:
            continue

        if "aarch64" in lower_url:
            continue

        if "arm" in lower_url:
            continue

        # Accept common x64 naming schemes.
        if any(
            architecture in lower_url
            for architecture in (
                "x86_64",
                "x64",
                "win64",
                "windows-x64",
                "windows_x64",
                "windows64",
            )
        ):
            candidates.append(url)

    if candidates:
        return candidates[0]

    # --------------------------------------------------------
    # Last-resort Windows ZIP search
    # --------------------------------------------------------

    for name, url in downloads.items():
        if not url:
            continue

        lower_name = name.lower()
        lower_url = url.lower()

        if "windows" not in lower_name and "windows" not in lower_url:
            continue

        if not lower_url.endswith(".zip"):
            continue

        if "web" in lower_url:
            continue

        if "selfhosted" in lower_url:
            continue

        if "self-hosted" in lower_url:
            continue

        return url

    raise RuntimeError(
        f"Could not find a Windows 64-bit desktop "
        f".zip download for Ruffle {release['version']}."
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
    # Fetch downloads page
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
            "The Ruffle releases table could not be parsed. "
            "The page structure may have changed."
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
    # Debug: show every discovered download
    # --------------------------------------------------------

    unique_downloads = []

    seen = set()

    for url in release["downloads"].values():
        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)
        unique_downloads.append(url)

    print(
        f"Found {len(unique_downloads)} downloads "
        f"for Ruffle {version}:"
    )

    for url in unique_downloads:
        print(url)

    print()

    # --------------------------------------------------------
    # Select Windows x64 build
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
