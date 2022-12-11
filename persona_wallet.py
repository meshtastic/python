from black_lager import persona_pb2
from nacl.signing import SigningKey
import pickle
import sys


class PersonaWallet:
    """A wrapper around the protobuf Wallet message. Read and write wallet from disk. Create new personas."""

    def __init__(self):
        """Initialize a Wallet object. Check if a command line argument is provided for the wallet file.
        If there is one provided, then set it as the wallet path. Else set the default wallet path
        """
        self.wallet_message = persona_pb2.Wallet()

        if len(sys.argv) == 1:
            self.wallet_path = "./wallet"
        elif len(sys.argv) == 2:
            self.wallet_path = sys.argv[1]
        else:
            print("Usage:", sys.argv[0], "WALLET_FILE")
            sys.exit(-1)

        self.read_wallet_from_file()

        # TODO: make persona selection CLI more robust, maybe use Python Click library
        if self.wallet_message.my_personas:
            print("Your personas:")
            for index, persona in enumerate(self.wallet_message.my_personas):
                print(index, persona.local_name)
            create_new_input = input("Would you like to use an existing persona? [y/n]: ")
            create_new = create_new_input.lower() == "n"
        else:
            print("No existing personas found. Creating new persona.")
            create_new = True

        if create_new:
            self.current_persona = self.create_new_persona()
        else:
            persona_selection = -1
            while not persona_selection > -1 and persona_selection < len(self.wallet_message.my_personas):
                persona_selection = int(input("Select a persona to use: "))

            self.current_persona = self.wallet_message.my_personas[persona_selection]

    def read_wallet_from_file(self):
        """Read wallet data from the wallet_path file and parse it into the wallet_message protobuf object"""
        try:
            f = open(self.wallet_path, "rb")
            self.wallet_message.ParseFromString(f.read())
            f.close()
        except IOError:
            print("Creating new wallet file.")

    def create_new_persona(self):
        """Prompt user for a name and add a new owned persona to the wallet."""
        new_persona = self.wallet_message.my_personas.add()
        new_persona.owned = True
        new_persona.local_name = input("Enter name: ")
        signing_key = SigningKey.generate()
        new_persona.private_key = pickle.dumps(signing_key)
        new_persona.public_key = pickle.dumps(signing_key.verify_key)
        return new_persona

    def save_peer_persona(self, name, public_key):
        """Save a peer persona to wallet"""
        peer_persona = self.wallet_message.peer_personas.add()
        peer_persona.owned = False
        peer_persona.local_name = name
        peer_persona.public_key = public_key

    def write_wallet_to_file(self):
        """Writes wallet data out to a file on disk"""
        # Note that the bytes are binary, not text; we only use the str type as a convenient container.
        f = open(self.wallet_path, "wb")
        f.write(self.wallet_message.SerializeToString())
        f.close()


# wallet = PersonaWallet()
# print("Current persona:", wallet.current_persona.local_name)
# print("Saving the following wallet to disk:")
# print(wallet.wallet_message)
# wallet.write_wallet_to_file()
