from __future__ import annotations

import argparse

import uvicorn

from quantnse.config import get_settings


def cmd_demo() -> None:
    from quantnse.api.main import get_engine
    from quantnse.live import demo_loop

    engine = get_engine()
    demo_loop(engine)
    print(f"Watchlist: {len(engine.watchlist)}  Setups: {len(engine.setups)}")
    triggered = [s.symbol for s in engine.setups.values() if s.status == "triggered"]
    print("Triggered:", ", ".join(triggered) or "(none)")


def cmd_api() -> None:
    settings = get_settings()
    uvicorn.run("quantnse.api.main:app", host=settings.api_host, port=settings.api_port, reload=False)


def cmd_login() -> None:
    from quantnse.ingestion.auth import login_url

    print(login_url())


def main() -> None:
    parser = argparse.ArgumentParser(prog="quantnse")
    parser.add_argument("command", choices=["demo", "api", "login", "live"])
    args = parser.parse_args()
    if args.command == "demo":
        cmd_demo()
    elif args.command == "api":
        cmd_api()
    elif args.command == "login":
        cmd_login()
    else:
        from quantnse.live import main_live

        main_live()


if __name__ == "__main__":
    main()
