import requests
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, validate_call
import logging

logging.basicConfig(level=logging.INFO)


class Client(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    headers: dict = Field(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        },
        description="The headers to use for the HTTP requests",
    )
    session: requests.Session = Field(
        default_factory=requests.Session,
        description="The session to use for the requests",
    )

    @validate_call
    def get(
        self, url: str = Field(..., description="The URL to make the GET request")
    ) -> Optional[Any]:
        try:
            logging.info(f"GET: {url}")
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            if response.headers.get("Content-Type") == "application/json":
                return response.json()
            else:
                return response.text

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            return None
