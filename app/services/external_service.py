from typing import Any, Dict

from app.core.logger import logger
from app.core.utils.http_client import HTTP_CLIENT


class EXTERNAL_SERVICE:

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def fetch_remote_resource(self, resource_id: str) -> Dict[str, Any]:
        target_url = f"{self.base_url}/resources/{resource_id}"
        logger.info(f"Fetching remote integration resource from: {target_url}")
        return await HTTP_CLIENT.get(url=target_url)

