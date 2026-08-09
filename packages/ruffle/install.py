import os
import re
import sys
from html.parser import HTMLParser
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from sdpkg import download_file, fetch_contents, extract_zip, copy_directory_contents, remove_directory

DOWNLOADS_URL = "https://ruffle.rs/downloads"


class RuffleDownloadsParser(HTMLParser):
    """
    Parses the releases table from ruffle.rs/downloads.

    Extracts rows in the form:

        {
            "version": "0.5.0",
            "downloads": {
                "Windows (64-bit)": "...",
                "Windows (32-bit)": "...",
                "macOS": "...",
                "Linux (x86_64)": "...",
                "Linux (ARM64)": "...",
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

            # The releases table contains "releases-module" in its classes.
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

            self.current_row.append({
                "text": text,
                "href": self.current_href
            })

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
    Download the Ruffle downloads page.
    """

    return fetch_contents(DOWNLOADS_URL)


def parse_releases(html):
    """
    Parse the releases table and return normalized release dictionaries.
    """

    parser = RuffleDownloadsParser()
    parser.feed(html)

    releases = []

    for row in parser.rows:
        if not row:
            continue

        version = row[0]["text"]

        # Skip the header row.
        if version.lower() == "version":
            continue

        # Only accept version-looking rows.
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
            continue

        downloads = {}

        for cell in row[1:]:
            name = cell["text"]
            href = cell["href"]

            if name and href:
                downloads[name] = href

        releases.append({
            "version": version,
            "downloads": downloads
        })

    return releases


def version_key(version):
    """
    Convert a Ruffle version into something sortable.

    Example:
        0.5.0 -> (0, 5, 0)
    """

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)

    if not match:
        return (0, 0, 0)

    return tuple(int(x) for x in match.groups())


def find_latest_release(releases):
    if not releases:
        raise RuntimeError(
            "Ruffle downloads page was parsed successfully, "
            "but no releases were found."
        )

    return max(
        releases,
        key=lambda release: version_key(release["version"])
    )


def find_windows_x64(release):
    """
    Find the Windows 64-bit desktop download.
    """

    downloads = release["downloads"]

    # Prefer the exact label used by the Ruffle downloads page.
    if "Windows (64-bit)" in downloads:
        return downloads["Windows (64-bit)"]

    # Fallback in case Ruffle changes the visible label.
    for name, url in downloads.items():
        normalized = name.lower()

        if (
            "windows" in normalized
            and "64" in normalized
            and url.lower().endswith(".zip")
        ):
            return url

    raise RuntimeError(
        f"Could not find a Windows 64-bit desktop download "
        f"for Ruffle {release['version']}."
    )


def main():
    """
    SDPkg installation entry point.
    """

    print("SDPkg: Installing Ruffle")
    print()

    # ------------------------------------------------------------
    # Determine package directory
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Fetch Ruffle downloads page
    # ------------------------------------------------------------

    print("Fetching Ruffle downloads page...")

    html = fetch_download_page()

    print(
        f"Received {len(html):,} bytes."
    )

    # ------------------------------------------------------------
    # Parse releases
    # ------------------------------------------------------------

    releases = parse_releases(html)

    print(
        f"Parsed {len(releases)} Ruffle releases."
    )

    if not releases:
        raise RuntimeError(
            "The Ruffle releases table could not be parsed. "
            "The page structure may have changed."
        )

    # ------------------------------------------------------------
    # Select latest release
    # ------------------------------------------------------------

    release = find_latest_release(releases)

    version = release["version"]

    print(
        f"Latest Ruffle release: {version}"
    )

    # ------------------------------------------------------------
    # Select Windows x64 desktop build
    # ------------------------------------------------------------

    download_url = find_windows_x64(release)

    print(
        f"Selected Windows 64-bit build:"
    )
    print(
        f"  {download_url}"
    )
    print()

    # ------------------------------------------------------------
    # Download
    # ------------------------------------------------------------

    if os.path.exists(archive_path):
        os.remove(archive_path)

    download_file(
        download_url,
        archive_path
    )

    # ------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------

    os.makedirs(
        install_dir,
        exist_ok=True
    )

    extract_zip(
        archive_path,
        install_dir
    )

    # ------------------------------------------------------------
    # Remove temporary archive
    # ------------------------------------------------------------

    os.remove(archive_path)

    print()
    print("Ruffle installation completed successfully.")
    print(f"Version: {version}")
    print(f"Files:   {install_dir}")


if __name__ == "__main__":
    main()
