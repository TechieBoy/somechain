# somechain
A complete implementation of a proof of work blockchain in python 3.7+

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

#### Installing Dependencies
```
sudo apt-get install python-dev libgmp3-dev wget #for fastecdsa
```

#### Installing Miniconda
```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh # Follow the instructions and ensure that conda is added to shell path.
```

#### Creating conda environment
```
# Inside the Repo directory
cd somechain/
conda env create -f=./environment.yml
```

#### Running
```
cd src/
source activate pychain
python fullnode.py
```
