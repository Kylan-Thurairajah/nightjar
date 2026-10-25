"""Run Nightjar with `python -m nightjar` or `nightjar`."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Nightjar simulation TUI.")
    parser.add_argument(
        "--mode",
        choices=("demo", "gridworld"),
        default="demo",
        help="simulation to display (default: demo)",
    )
    args = parser.parse_args()

    from nightjar.tui.app import NightjarApp

    NightjarApp(mode=args.mode).run()


if __name__ == "__main__":
    main()
