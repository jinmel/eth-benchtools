import json

from web3 import Web3
from eth_account import Account

def deploy_test_token_contract(w3: Web3, faucet: Account, chain_id):

    # Deploy contracts
    # Load TestToken ABI and bytecode
    with open('contracts/out/Token.sol/TestToken.json', 'r') as file:
        contract_json = json.loads(file.read())
        abi = contract_json['abi']
        bytecode = contract_json['bytecode']['object']

    # Create contract instance
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Estimate gas for deployment
    gas_estimate = contract.constructor(faucet.address).estimate_gas()

    # Prepare transaction for contract deployment
    deploy_txn = contract.constructor(faucet.address).build_transaction({
        'from': faucet.address,
        'gas': int(gas_estimate * 1.2),  # Add 20% buffer to gas estimate
        'gas': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(faucet.address),
        'chainId': chain_id,
    })

    # Sign and send the transaction
    signed_txn = faucet.sign_transaction(deploy_txn)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

    # Wait for the transaction to be mined
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if tx_receipt['status'] == 1:
        contract_address = tx_receipt['contractAddress']
        print(f"TestToken deployed successfully at address: {contract_address}")
        # Store the contract address for later use
    else:
        raise Exception("Failed to deploy TestToken contract")

    return abi, contract_address
