"""FFAStrans Linux Mimo - main entry point."""
import os
import sys
import logging
import argparse
import uvicorn
from .core.config import API_HOST, API_PORT, NODE_ROLE, load_config, save_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("data", "ffastrans.log"), mode="a"),
    ],
)
logger = logging.getLogger("ffastrans")


def main():
    parser = argparse.ArgumentParser(description="FFAStrans Linux Mimo")
    parser.add_argument("--host", default=API_HOST, help="API host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=API_PORT, help="API port (default: 8080)")
    parser.add_argument("--role", default=NODE_ROLE, choices=["master", "node"], help="Node role")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    args = parser.parse_args()

    os.environ["FFASTRANS_NODE_ROLE"] = args.role
    cfg = load_config()
    cfg["role"] = args.role
    save_config(cfg)

    logger.info(f"Starting FFAStrans Linux Mimo (role={args.role})")
    logger.info(f"API: http://{args.host}:{args.port}")

    from .api.routes import app
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload, workers=args.workers)


if __name__ == "__main__":
    main()
