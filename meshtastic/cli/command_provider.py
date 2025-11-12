"""Command provider infrastructure for the Meshtastic CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

import argparse


class ArgumentContainer(Protocol):
    """A minimal protocol for argparse containers (ArgumentParser or _ArgumentGroup)."""

    def add_argument(self, *args, **kwargs) -> argparse.Action:  # pragma: no cover - interface stub
        ...

    def add_argument_group(self, *args, **kwargs) -> argparse._ArgumentGroup:  # pragma: no cover - interface stub
        ...


class CommandProvider(Protocol):
    """Protocol for CLI command providers."""

    def register_arguments(self, container: ArgumentContainer) -> None:  # pragma: no cover - interface stub
        """Add argparse arguments to the provided container."""

    def register_subcommands(self, subparsers: argparse._SubParsersAction) -> None:  # pragma: no cover - interface stub
        """Add argparse subcommands."""

    def handle(self, context: "CommandContext") -> None:  # pragma: no cover - interface stub
        """Handle CLI invocation with access to the mutable command context."""


@dataclass
class CommandContext:
    """Mutable command invocation context shared with providers."""

    args: argparse.Namespace
    interface: object
    command: Optional[str] = None
    close_now: bool = False
    wait_for_ack: bool = False
    errors: List[str] = field(default_factory=list)

    def request_close(self, wait_for_ack: bool = False) -> None:
        """Signal that CLI should close once processing completes."""

        self.close_now = True
        if wait_for_ack:
            self.wait_for_ack = True

    def add_error(self, message: str) -> None:
        """Record an error message for later reporting."""

        self.errors.append(message)


class CommandRegistry:
    """Registry for CLI command providers."""

    def __init__(self) -> None:
        self._providers: List[CommandProvider] = []

    def register(self, provider: CommandProvider) -> None:
        """Register a provider instance."""

        self._providers.append(provider)

    def register_arguments(self, container: ArgumentContainer) -> None:
        """Ask providers to contribute argparse arguments."""

        for provider in self._providers:
            provider.register_arguments(container)

    def register_subcommands(self, subparsers: argparse._SubParsersAction) -> None:
        """Ask providers to contribute subcommands."""

        for provider in self._providers:
            hook = getattr(provider, "register_subcommands", None)
            if callable(hook):
                hook(subparsers)

    def handle(self, context: CommandContext) -> None:
        """Invoke providers so they can respond to the CLI invocation."""

        for provider in self._providers:
            provider.handle(context)


_registry: CommandRegistry | None = None


def get_registry() -> CommandRegistry:
    """Return the singleton command provider registry."""

    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry

