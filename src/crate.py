import logging
import re
from pathlib import Path
import tempfile
import requests
from typing import Self
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
from bs4 import BeautifulSoup as bs
from pydantic import BaseModel, Field

from .client import Client

logging.basicConfig(level=logging.INFO)


class CrateBase(BaseModel):
    """Base model for Rust crate metadata."""

    name: str = Field(..., description="The name of the crate")
    version: str | None = Field(None, description="The version of the crate")
    latest_version: str | None = Field(
        None, description="The latest version of the crate"
    )

    url_templates: dict[str, str] = Field(
        {
            "download": "https://docs.rs/crate/{name}/{version}/download",
            "download_latest": "https://docs.rs/crate/{name}/latest/download/",
            "latest": "https://docs.rs/crate/{name}/latest",
        },
        description="URL templates for fetching crate metadata and documentation",
    )


class Crate(CrateBase):
    """Rust crate documentation downloader."""

    client: Client = Field(Client(), description="The client to use for the requests")
    output_path: Path | None = Field(
        None, description="The path to save the downloaded documentation"
    )

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
        except (requests.RequestException, AttributeError) as e:
            logging.error(f"Failed to fetch metadata for {self.name}: {e}")
            raise

    @classmethod
    def from_latest_version(cls, name: str) -> Self:
        """Create a Crate instance with the latest version."""
        crate = cls(name=name)
        crate.fetch_metadata()

        return cls.model_validate(
            {
                "name": name,
                "version": crate.latest_version,
                "latest_version": crate.latest_version,
            }
        )

    @classmethod
    def from_version(cls, name: str, version: str) -> Self:
        """Create a Crate instance with a specific version."""
        latest_version = cls.from_latest_version(name).latest_version
        return cls.model_validate(
            {"name": name, "version": version, "latest_version": latest_version}
        )

    def download_docs(self, output_path: Path) -> None:
        """Download and extract crate documentation."""
        output_path = Path(output_path) / self.name / self.version
        output_path.mkdir(exist_ok=True, parents=True)
        self.output_path = output_path
        download_url = self.url_templates["download"].format(
            name=self.name, version=self.version
        )
        try:
            logging.info(f"Downloading docs from: {download_url}")
            response = self.client.session.get(download_url, stream=True)
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

            logging.info(f"Successfully extracted docs to: {output_path}")
        except Exception as e:
            logging.error(f"Error downloading docs: {e}")
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
            zip_path.unlink()

        if not list(output_path.glob("*")):
            output_path.rmdir()
            logging.info(f"Removed empty output path: {output_path}")

    def _process_html_files(self):
        """Process downloaded HTML files."""
        src_path = self.output_path / self.name
        html_files = list(src_path.glob("**/*.html"))
        console = Console()
        console.print(
            Panel(Text(f"Found {len(html_files)} HTML files.", style="bold green"))
        )

    def process_files(self):
        self._process_html_files()

    def __str__(self):
        return f"""{self.__class__.__name__}:
    name: {self.name}
    version: {self.version}
    latest_version: {self.latest_version}"""

    def save(self, output_path: Path = Path("tmp")):
        """Serialize Crate instance to pickle."""
        import pickle

        output_path = Path(output_path)
        output_path.mkdir(exist_ok=True, parents=True)
        with open(output_path / f"{self.name}.pickle", "wb") as file:
            pickle.dump(self, file)
        logging.info(f"Saved {self} to {output_path}")

    @classmethod
    def load(cls, file_path: Path):
        """Deserialize Crate instance from pickle."""
        import pickle

        with open(file_path, "rb") as file:
            return pickle.load(file)
