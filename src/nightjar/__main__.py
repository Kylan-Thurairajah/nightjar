"""Run Nightjar with `python -m nightjar` or `nightjar`."""


def main() -> None:
    from nightjar.tui.app import NightjarApp

    NightjarApp().run()


if __name__ == "__main__":
    main()
