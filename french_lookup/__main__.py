import argparse
import sys

from . import claude, config


def main() -> int:
    parser = argparse.ArgumentParser(prog="french-lookup")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("daemon", help="run the background app (tray icon + popup)")
    sub.add_parser("trigger", help="look up the current selection (bound to Super+F)")
    sub.add_parser("stop", help="stop the background app")
    ask = sub.add_parser("ask", help="look up TEXT and print the answer")
    ask.add_argument("text")
    sub.add_parser("register-shortcut", help="bind Super+F in GNOME")
    sub.add_parser("unregister-shortcut", help="remove the Super+F binding")
    args = parser.parse_args()

    if args.command == "ask":
        try:
            print(claude.ask(config.load(), claude.clean_selection(args.text)))
        except claude.LookupError_ as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    if args.command == "daemon":
        from . import daemon
        return daemon.run()
    if args.command in ("trigger", "stop"):
        from . import client
        return client.trigger() if args.command == "trigger" else client.stop()
    from . import shortcut
    if args.command == "register-shortcut":
        shortcut.register()
    else:
        shortcut.unregister()
    return 0


if __name__ == "__main__":
    sys.exit(main())
