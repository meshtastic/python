# Contributing Example Scripts

Use this guide when adding or updating scripts in `examples/`.

## Must-have checklist before opening a PR

1. Script teaches one clear thing (its primary learning goal).
2. File name matches that goal.
3. Top docstring states purpose, transport scope, behavior, and expected output.
4. Script has safe shutdown (`with ...` or `finally`) and graceful `KeyboardInterrupt` handling.
5. Argument handling is clear (`argparse` preferred).
6. Errors are explicit (no bare `except:`).
7. The script is not a near-duplicate of an existing example.

## Choose the right teaching goal

Each example should have one primary lesson. Keep it focused.

- Good: "Send one text message over serial."
- Good: "Print inbound text messages."
- Avoid: discovery + chat + config mutation all in one script unless that combined flow is the lesson.

## Transport scope must be explicit

State exactly what transports are supported and why.

- Serial-only when that keeps the example simplest.
- Multi-transport (Serial/TCP/BLE) only when transport selection is part of the lesson.
- If TCP/BLE are supported, expose explicit flags (`--host`, `--ble`) and document defaults.

## Behavior and output should be predictable

Readers should know if the script sends, receives, mutates config, or combines those.

- Receive examples: subscribe to the narrowest pubsub topic that matches the lesson.
- Send examples: clarify destination behavior (broadcast default vs explicit destination).
- Mutation examples: clearly document side effects.

Output should make success easy to confirm:

- Print concise, stable status/event lines.
- Avoid noisy debug output unless the script is specifically diagnostic-focused.

## Cleanup and error handling

- Use context managers where practical; otherwise close interfaces in `finally`.
- Handle `KeyboardInterrupt` cleanly.
- Exit non-zero for invalid args, connection/setup failures, or command failures.

## Naming guidance

Use descriptive names tied to the teaching goal.

- Prefer names like `tcp_connection_info_once.py` over `pub_sub_example.py`.
- Prefer names like `tcp_pubsub_send_and_receive.py` over `pub_sub_example2.py`.
- Avoid generic names such as `example2.py`.

Keep existing filenames only when compatibility or discoverability outweighs clarity.

## New script vs extending an existing one

Create a new script when:

- The learning goal is genuinely distinct.
- Combining behaviors would make either example harder to understand.

Extend an existing script when:

- The change deepens the same lesson.
- The resulting script remains focused and readable.
