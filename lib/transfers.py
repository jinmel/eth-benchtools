from locust.exception import RescheduleTask
from web3 import Web3


def transfer_balance(w3:Web3, to, chain_id, amount, account, receipt=False):
    # Estimate gas price
    gas_price = w3.eth.gas_price
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = base_fee + max_priority_fee

    tx = {
        "to": to,
        "value": amount,
        "gas": 21000,
        "gas": gas_price,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
        "chainId": chain_id,
        "type": 2,
        "maxFeePerGas": max_fee_per_gas,
        "maxPriorityFeePerGas": max_priority_fee,
    }
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    if receipt:
        return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30, poll_latency=0.5)
    return None


def transfer_erc20(w3, to, chain_id, amount, test_token_address, test_token_abi, account, nonce=None):
    # Estimate gas price
    estimated_gas_price = w3.eth.gas_price

    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = base_fee + max_priority_fee

    erc20_contract = w3.eth.contract(address=test_token_address, abi=test_token_abi)

    # Prepare the transaction
    transfer_txn = erc20_contract.functions.transfer(
        to,
        amount,
    ).build_transaction({
        'chainId': chain_id,
        'gas': 100000,  # Adjust gas limit as needed
        'gas': estimated_gas_price,
        'nonce': nonce if nonce else w3.eth.get_transaction_count(account.address, "pending"),
        'type': 2,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': max_priority_fee,
    })

    # Sign and send the transaction
    signed_txn = w3.eth.account.sign_transaction(transfer_txn, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

    # Wait for the transaction to be mined
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30, poll_latency=0.5)
    return tx_receipt
