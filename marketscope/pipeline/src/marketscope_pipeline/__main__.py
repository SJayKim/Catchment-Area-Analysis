"""python -m marketscope_pipeline 진입점."""

import asyncio

from marketscope_pipeline.main import main

if __name__ == "__main__":
    asyncio.run(main())
