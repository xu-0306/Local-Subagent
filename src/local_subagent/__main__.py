from local_subagent.server import create_server


def main() -> int:
    create_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
