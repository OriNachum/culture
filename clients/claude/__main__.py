# clients/claude/__main__.py
"""Entry point: python -m clients.claude"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AgentIRC Claude daemon")
    p.add_argument("--server-name", help="IRC server name (e.g. spark)")
    p.add_argument("--irc-host", default="127.0.0.1")
    p.add_argument("--irc-port", type=int, default=6667)
    p.add_argument("--channel", action="append", dest="channels", metavar="CHANNEL")
    p.add_argument("--config", metavar="PATH", help="YAML config file")
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from clients.claude.config import DaemonConfig

    if args.config:
        config = DaemonConfig.from_yaml(args.config)
        # CLI flags override YAML
        if args.irc_host != "127.0.0.1":
            config.irc_host = args.irc_host
        if args.irc_port != 6667:
            config.irc_port = args.irc_port
        if args.channels:
            config.channels = args.channels
        if args.server_name:
            config.server_name = args.server_name
    else:
        if not args.server_name:
            print("ERROR: --server-name or --config is required", file=sys.stderr)
            sys.exit(1)
        config = DaemonConfig(
            server_name=args.server_name,
            irc_host=args.irc_host,
            irc_port=args.irc_port,
            channels=args.channels or ["#general"],
        )

    from clients.claude.daemon import ClaudeDaemon

    daemon = ClaudeDaemon(config)
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
