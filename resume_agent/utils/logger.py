import sys
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    logger.remove()

    # Console — coloured, human-readable
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File — full details for debugging
    logger.add(
        "output/agent.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )


setup_logger()