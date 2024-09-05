import os
import json
from locust import task, between, TaskSet, User
from locust.exception import RescheduleTask
from web3 import Web3
from eth_account import Account
from locust import events
from locust.runners import MasterRunner


PRIVATE_KEY = os.getenv("PRIVATE_KEY", None) ## PRIVATE KEY OF THE ACCOUNT TO FUND THE USERS
ACCOUNT = Account.from_key(PRIVATE_KEY)
CHAIN_ID = os.getenv("CHAIN_ID", 1337)
HOST = os.getenv("HOST", "http://localhost:8545")
w3 = Web3(Web3.HTTPProvider(HOST))

def transfer_balance(w3, target_address, private_key):
    # Estimate gas price
    estimated_gas_price = w3.eth.gas_price
    
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = base_fee + max_priority_fee

    # Get the address associated with the private key
    account = Account.from_key(private_key)

    tx = {
        "to": target_address,
        "value": 1,
        "gas": 21000,
        "gasPrice": estimated_gas_price,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": CHAIN_ID,
        "type": 2,
        "maxFeePerGas": max_fee_per_gas,
        "maxPriorityFeePerGas": max_priority_fee,
    }
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    # Wait for the transaction to be mined
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if tx_receipt['status'] != 1:
        raise RescheduleTask()
    else:
        print(f"Transferred 1 wei to {target_address}")

def transfer_erc20(w3, test_token_address, test_token_abi, target_address, private_key):
    # Estimate gas price
    estimated_gas_price = w3.eth.gas_price
    
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = base_fee + max_priority_fee

    erc20_contract = w3.eth.contract(address=test_token_address, abi=test_token_abi)
    
    # Get the address associated with the private key
    account = Account.from_key(private_key)
    
    # Prepare the transaction
    transfer_txn = erc20_contract.functions.transfer(
        target_address,
        1  # Transfer 1 token (adjust based on token decimals)
    ).build_transaction({
        'chainId': CHAIN_ID,
        'gas': 100000,  # Adjust gas limit as needed
        'gasPrice': estimated_gas_price,
        'nonce': w3.eth.get_transaction_count(account.address),
        'type': 2,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': max_priority_fee,
    })

    # Sign and send the transaction
    signed_txn = w3.eth.account.sign_transaction(transfer_txn, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    # Wait for the transaction to be mined
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if tx_receipt['status'] != 1:
        raise RescheduleTask()
    else:
        print(f"Transferred 1 ERC20 token to {target_address}")

class EthereumTasks(TaskSet):
    def make_random_account(self):
        return Account.create()

    @task
    def transfer_balance(self):
        target_address = self.make_random_account().address
        transfer_balance(self.user.w3, target_address, self.user.user_private_key)

    @task
    def transfer_erc20(self):
        target_address = self.make_random_account().address
        transfer_erc20(self.user.w3, self.user.test_token_address, self.user.test_token_abi, target_address, self.user.user_private_key)

        
class Web3User(User):
    tasks = [EthereumTasks]
    wait_time = between(1, 5)
    w3 = Web3(Web3.HTTPProvider(HOST))

    def on_start(self):
        # Generate a new private key for this Web3User instance
        self.user_private_key = Account.create().privateKey
        self.user_account = Account.from_key(self.user_private_key)
        self.user_address = self.user_account.address

        # Fund the user account from the faucet using transfer_balance function
        transfer_balance(self.w3, self.user_address, PRIVATE_KEY)
        print(f"User account funded successfully. Address: {self.user_address}")

        # Fund the user with ERC20 tokens
        transfer_erc20(self.w3, self.environment.test_token_address, self.environment.test_token_abi, self.user_address, PRIVATE_KEY)



@events.init.add_listener
def on_locust_init(environment):
    if isinstance(environment.runner, MasterRunner):
        pass

@events.init.add_listener
def deploy_contracts(environment):
    # only the master node should deploy the contracts
    if not isinstance(environment.runner, MasterRunner):
        return
    
    account = Account.from_key(PRIVATE_KEY)
    w3 = Web3(Web3.HTTPProvider(HOST))

    # Deploy contracts
    # Load TestToken ABI and bytecode
    with open('contracts/out/Token.sol/TestToken.json', 'r') as file:
        contract_json = json.loads(file.read())
        abi = contract_json['abi']
        environment.test_token_abi = abi
        bytecode = contract_json['bytecode']['object']

    # Create contract instance
    TestToken = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Estimate gas for deployment
    gas_estimate = TestToken.constructor(account.address).estimate_gas()

    # Prepare transaction for contract deployment
    deploy_txn = TestToken.constructor(account.address).build_transaction({
        'from': account.address,
        'gas': int(gas_estimate * 1.2),  # Add 20% buffer to gas estimate
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address),
        'chainId': CHAIN_ID,
    })

    # Sign and send the transaction
    signed_txn = account.sign_transaction(deploy_txn)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    # Wait for the transaction to be mined
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if tx_receipt['status'] == 1:
        contract_address = tx_receipt['contractAddress']
        print(f"TestToken deployed successfully at address: {contract_address}")
        # Store the contract address for later use
        environment.test_token_address = contract_address
    else:
        print("Failed to deploy TestToken contract")