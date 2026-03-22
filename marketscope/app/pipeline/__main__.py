"""python -m app.pipeline 진입점."""

import asyncio

from app.pipeline.main import main

if __name__ == "__main__":
    asyncio.run(main())
