import logging
from rich.logging import RichHandler

FORMAT = "%(asctime)s [%(levelname)-8s] (%(name)s) %(message)s"


class Logger:

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(
            RichHandler(level=logging.INFO, rich_tracebacks=True, markup=True)
        )
