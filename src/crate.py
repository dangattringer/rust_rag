import re
from pathlib import Path
import tempfile
import requests
from typing import Optional, Self
import zipfile
from rich.progress import (
    Progress,
    BarColumn,
    TimeElapsedColumn,
    DownloadColumn,
    TextColumn,
    TaskID,
)
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from bs4 import BeautifulSoup as bs

from .client import Client
from .logger import Logger


class CrateBase(Logger):
    """Base model for Rust crate metadata."""

    def __init__(self, name: str, version: str | None = None):
        super().__init__()
        self.name = name
        self.version = version
        self.latest_version = None
        self.url_templates = {
            "download": "https://docs.rs/crate/{name}/{version}/download",
            "download_latest": "https://docs.rs/crate/{name}/latest/download/",
            "latest": "https://docs.rs/crate/{name}/latest",
        }


class Crate(CrateBase):
    """Rust crate documentation downloader."""

    def __init__(self, name: str, version: Optional[str] = None):
        super().__init__(name=name, version=version)
        self.client = Client()
        self.output_path = None

    def fetch_metadata(self) -> None:
        """Fetch the latest version of the crate."""
        try:
            response = self.client.session.get(
                self.url_templates["latest"].format(name=self.name)
            )
            response.raise_for_status()

            soup = bs(response.text, "html.parser")
            crate_title = soup.find("h1", {"id": "crate-title"})

            if crate_title:
                version_match = re.search(r"\d+\.\d+\.\d+", crate_title.text)
                self.latest_version = version_match.group() if version_match else None
        except requests.HTTPError as e:
            self.logger.error(
                f"Failed to fetch metadata for {self.name}: HTTPError {e.response.status_code} {e}"
            )
            raise
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch metadata for {self.name}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch metadata for {self.name}: {e}")
            raise

    @classmethod
    def from_latest_version(cls, name: str) -> Self:
        """Create a Crate instance with the latest version."""
        crate = cls(name=name)
        crate.fetch_metadata()
        crate.version = crate.latest_version
        return crate

    @classmethod
    def from_version(cls, name: str, version: str) -> Self:
        """Create a Crate instance with a specific version."""
        crate = cls(name=name, version=version)
        crate.fetch_metadata()
        return crate

    def download_docs(self, output_path: Path) -> None:
        """Download and extract crate documentation."""
        output_path = Path(output_path) / self.name / self.version
        output_path.mkdir(exist_ok=True, parents=True)
        self.output_path = output_path
        download_url = self.url_templates["download"].format(
            name=self.name, version=self.version
        )
        try:
            self.logger.info(f"Downloading docs from: {download_url}")
            response = self.client.session.get(download_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            if response.status_code == 404:
                raise ValueError(f"Documentation not found: {download_url}")

            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                with Progress(
                    TextColumn("[bold blue]{task.description}:", justify="right"),
                    BarColumn(bar_width=30),
                    TextColumn("[magenta]{task.percentage:>3.1f}%"),
                    "•",
                    DownloadColumn(),
                    "•",
                    TimeElapsedColumn(),
                    transient=False,
                    console=Console(),
                ) as progress:
                    download_task: TaskID = progress.add_task(
                        f"Downloading {self.name}-{self.version}.zip", total=total_size
                    )

                    for chunk in response.iter_content(chunk_size=8192):
                        tmp_file.write(chunk)
                        progress.update(download_task, advance=len(chunk))

                self._extract_zip(Path(tmp_file.name), output_path)

            self.logger.info(f"Successfully extracted docs to: {output_path}")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.error(
                    f"Error downloading docs: Documentation not found for {download_url}"
                )
                raise ValueError(f"Documentation not found: {download_url}") from e
            self.logger.error(
                f"Error downloading docs: {e} - Response {e.response.status_code}"
            )
            raise
        except zipfile.BadZipFile as e:
            self.logger.error(f"Error extracting the zip file {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error downloading docs: {e}")
            raise
        finally:
            self._cleanup_download(output_path)

    def _extract_zip(self, zip_path: Path, output_path: Path):
        """Extract documentation with progress tracking."""
        with (
            zipfile.ZipFile(zip_path, "r") as zip_ref,
            Progress(
                TextColumn("[bold blue]{task.description}:", justify="right"),
                BarColumn(bar_width=30),
                TextColumn("[magenta]{task.percentage:>3.1f}%"),
                "•",
                TextColumn("[green]{task.completed}/{task.total} files"),
                "•",
                TimeElapsedColumn(),
                transient=False,
                console=Console(),
            ) as progress,
        ):
            extract_task = progress.add_task(
                f"Extracting {self.name}-{self.version}.zip",
                total=len(zip_ref.namelist()),
            )

            for file in zip_ref.namelist():
                zip_ref.extract(member=file, path=output_path)
                progress.update(extract_task, advance=1)

    def _cleanup_download(self, output_path: Path):
        """Clean up temporary files and empty directories."""
        zip_path = Path(tempfile.gettempdir()) / f"{self.name}-{self.version}.zip"
        if zip_path.exists():
            try:
                zip_path.unlink()
            except OSError as e:
                self.logger.warning(f"Failed to delete temp file: {zip_path} - {e}")

        if not list(output_path.glob("*")):
            try:
                output_path.rmdir()
                self.logger.info(f"Removed empty output path: {output_path}")
            except OSError as e:
                self.logger.warning(
                    f"Failed to remove output path: {output_path} - {e}"
                )

    def _process_html_files(self):
        """Process downloaded HTML files."""
        src_path = self.output_path / self.name / "src"
        html_files = list(src_path.glob("**/*.html"))
        console = Console()
        console.print(
            Panel(Text(f"Found {len(html_files)} HTML files.", style="bold green"))
        )

    def process_files(self):
        self._process_html_files()

    def __str__(self):
        console = Console(force_terminal=True)

        table = Table(
            show_header=False, show_edge=False, border_style="blue", style="bold"
        )
        table.add_column("Attribute", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Crate", self.name)
        table.add_row("Version", self.version)
        table.add_row("Version (latest)", self.latest_version)
        table.add_row("Output Path", str(self.output_path))
        panel = Panel(
            table,
            expand=False,
            border_style="blue",
            title="Crate Info",
            style="bold",
            padding=(1, 1),
        )
        with console.capture() as capture:
            console.print(panel)
        return capture.get()

    def save(self, output_path: Path = Path("tmp")):
        """Serialize Crate instance to pickle."""
        import pickle

        output_path = Path(output_path)
        output_path.mkdir(exist_ok=True, parents=True)
        try:
            with open(output_path / f"{self.name}.pickle", "wb") as file:
                pickle.dump(self, file)
            self.logger.info(f"Saved {self.name} to {output_path}")
        except pickle.PickleError as e:
            self.logger.error(f"Failed to save Crate to {output_path} - {e}")
            raise

    @classmethod
    def load(cls, file_path: Path):
        """Deserialize Crate instance from pickle."""
        import pickle

        try:
            with open(file_path, "rb") as file:
                return pickle.load(file)
        except pickle.PickleError as e:
            raise Exception(f"Error loading pickle file {file_path} - {e}")
