import logging
from pathlib import Path
from pydantic import Field, validate_call

from .crate import Crate

logging.basicConfig(level=logging.INFO)


@validate_call
def download(
    crate_name: str, version: str | None = None, output_path: Path = Path.cwd()
):

    logging.info("Starting crate download...")
    if version:
        crate = Crate.from_version(crate_name, version)
        if crate.version != version:
            logging.warning(
                f"Version {version} was not the latest, using: {crate.version}"
            )
    else:
        crate = Crate.from_latest_version(crate_name)

    crate.download_docs(output_path=output_path)
    return crate
