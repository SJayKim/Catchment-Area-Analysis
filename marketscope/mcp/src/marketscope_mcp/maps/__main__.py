"""Maps MCP Server 단독 실행."""

import logging

import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

from marketscope_mcp.maps.server import app  # noqa: E402

uvicorn.run(app, host="0.0.0.0", port=5101)
