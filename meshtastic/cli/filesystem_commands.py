"""Filesystem command provider for the Meshtastic CLI."""

from __future__ import annotations

from meshtastic import BROADCAST_ADDR
from meshtastic.cli import CommandContext, CommandProvider
from meshtastic.mesh.interfaces import FsOperationError
from meshtastic.mesh_interface import MeshInterface


class FilesystemCommandProvider(CommandProvider):
    """Handles filesystem-related CLI commands."""

    def register_arguments(self, container) -> None:
        """No global arguments to register."""
        return

    def register_subcommands(self, subparsers) -> None:
        ls_parser = subparsers.add_parser(
            "ls",
            help="List local node filesystem contents",
            description="List filesystem entries reported by the connected local node.",
        )
        ls_parser.set_defaults(command="ls", command_handler=self.handle)

        download_parser = subparsers.add_parser(
            "download",
            help="Download a file from the node filesystem",
            description="Download a file from the connected node filesystem to the host.",
        )
        download_parser.add_argument(
            "node_src",
            metavar="NODE_SRC",
            help="Source path on the node.",
        )
        download_parser.add_argument(
            "host_dst",
            metavar="HOST_DST",
            nargs="?",
            default=".",
            help="Destination path on the host (defaults to current directory).",
        )
        download_parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite destination file if it already exists.",
        )
        download_parser.set_defaults(command="download", command_handler=self.handle)

        upload_parser = subparsers.add_parser(
            "upload",
            help="Upload a file to the node filesystem",
            description="Upload a host file to the connected node filesystem.",
        )
        upload_parser.add_argument(
            "host_src",
            metavar="HOST_SRC",
            help="Source path on the host.",
        )
        upload_parser.add_argument(
            "device_dst",
            metavar="DEVICE_DST",
            nargs="?",
            default="/",
            help="Destination path on the node (defaults to '/').",
        )
        upload_parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite destination file if it already exists.",
        )
        upload_parser.set_defaults(command="upload", command_handler=self.handle)

        delete_parser = subparsers.add_parser(
            "rm",
            help="Delete a file from the node filesystem",
            description="Remove a file from the connected node filesystem.",
        )
        delete_parser.add_argument(
            "remote_path",
            metavar="REMOTE_PATH",
            help="Path to remove from the node filesystem.",
        )
        delete_parser.set_defaults(command="rm", command_handler=self.handle)

    def handle(self, context: CommandContext) -> None:
        args = context.args
        interface: "MeshInterface" = context.interface  # type: ignore[assignment]

        if context.command == "ls":
            if args.dest != BROADCAST_ADDR:
                message = "Listing filesystem of a remote node is not supported."
                print(message)
                context.add_error(message)
            else:
                context.request_close()
                interface.fs.show()

        if context.command == "download":
            if args.dest != BROADCAST_ADDR:
                message = "Downloading from a remote node is not supported."
                print(message)
                context.add_error(message)
                return

            node_src = args.node_src
            host_dst = args.host_dst

            try:
                destination_path = interface.fs.download(
                    node_src, host_dst, overwrite=getattr(args, "force", False)
                )
            except FsOperationError as ex:
                context.request_close()
                error_message = f"ERROR: {ex}"
                print(error_message)
                context.add_error(error_message)
                return

            context.request_close()
            print(f"Downloaded '{node_src}' to '{destination_path}'.")

        if context.command == "upload":
            if args.dest != BROADCAST_ADDR:
                message = "Uploading to a remote node is not supported."
                print(message)
                context.add_error(message)
                return

            host_src = args.host_src
            device_dst = args.device_dst

            try:
                remote_path = interface.fs.upload(
                    host_src, device_dst, overwrite=getattr(args, "force", False)
                )
            except FsOperationError as ex:
                context.request_close()
                error_message = f"ERROR: {ex}"
                print(error_message)
                context.add_error(error_message)
                interface.close()
                return

            context.request_close()
            print(f"Uploaded '{host_src}' to '{remote_path}'.")

        if context.command == "rm":
            if args.dest != BROADCAST_ADDR:
                message = "Deleting files on a remote node is not supported."
                print(message)
                context.add_error(message)
                return

            remote_path = args.remote_path
            try:
                interface.fs.delete(remote_path)
            except FsOperationError as ex:
                context.request_close()
                error_message = f"ERROR: {ex}"
                print(error_message)
                context.add_error(error_message)
                return

            context.request_close()
            print(f"Deleted '{remote_path}' from node filesystem.")


def register_filesystem_provider(registry) -> None:
    """Convenience helper to register the filesystem command provider."""

    registry.register(FilesystemCommandProvider())

