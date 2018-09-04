# somechain
A (somewhat) complete implementation of the bitcoin core in python 3.7+

## Simplifications
- Storage using pickledb in flat files
- Communication between peers using http api calls
- Can only send tokens to a single public key
- Serialization completely done via json
- No scripting language
- All nodes assumed to be honest and non malicious
- Peer discovery through a central server
- Every node is a full node with a wallet, no light nodes (for now)

## Installing and running
Use conda to create an env using the environment.yml file and run src/fullnode.py
