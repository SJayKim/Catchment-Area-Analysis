"""python -m app.engine 진입점."""

import asyncio

from marketscope_agent.engine.worker import main

if __name__ == "__main__":
    asyncio.run(main())
