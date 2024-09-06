import os
import time
import logging

from locust import User, task, tag
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.exceptions import Web3RPCError
from eth_account import Account
from locust import events
from locust.runners import WorkerRunner
from lib.transfers import transfer_balance, transfer_erc20
from lib.deployer import deploy_test_token_contract


PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80") ## PRIVATE KEY OF THE ACCOUNT TO FUND THE USERS
FAUCET = Account.from_key(PRIVATE_KEY)
CHAIN_ID = os.getenv("CHAIN_ID", 901)
HOST = os.getenv("HOST", "http://localhost:9545")
FAUCET_NONCE = Web3(Web3.HTTPProvider(HOST)).eth.get_transaction_count(FAUCET.address)

class Web3User(User):
    account: Account

    def __init__(self, environment):
        super().__init__(environment)
        self.w3 = Web3(Web3.HTTPProvider(self.host))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.create()

    @task
    @tag("eth")
    def transfer_balance(self):
        random_account = Account.create()
        start_perf_counter = time.perf_counter()
        start_time = time.time()
        receipt = transfer_balance(self.w3, random_account.address, CHAIN_ID, 1, self.account)
        response_time = (time.perf_counter() - start_perf_counter) * 1000
        request_meta = {
            "request_type": "POST",
            "response_time": response_time,
            "name": "Transfer Balance",
            "response": receipt,
            "exception": None,
            "start_time": start_time,
            "url": f"{self.host}",
            "response_length": receipt['gasUsed'],
        }
        self.environment.events.request.fire(**request_meta)

    @task
    @tag("erc20")
    def transfer_erc20(self):
        random_account = Account.create()
        start_perf_counter = time.perf_counter()
        start_time = time.time()
        receipt = transfer_erc20(self.w3, random_account.address, CHAIN_ID, 1, self.environment.test_token_address,
                                 self.environment.test_token_abi, self.account)
        response_time = (time.perf_counter() - start_perf_counter) * 1000
        request_meta = {
            "request_type": "POST",
            "response_time": response_time,
            "name": "Transfer ERC20 Token",
            "response": receipt,
            "exception": None,
            "start_time": start_time,
            "url": f"{self.host}",
            "response_length": receipt['gasUsed'],
        }
        self.environment.events.request.fire(**request_meta)

    def on_start(self):
        # Generate a new private key for this Web3User instance
        faucet = Account.from_key(PRIVATE_KEY)

        result = None
        while result is None:
            try:
                result = transfer_balance(self.w3, self.account.address, CHAIN_ID, 10 ** 18, faucet)
            except Web3RPCError:
                pass

        result = None
        while result is None:
            try:
               result =  transfer_erc20(self.w3, self.account.address, CHAIN_ID, 10 ** 18, self.environment.test_token_address,
                       self.environment.test_token_abi, faucet)
            except Web3RPCError:
                pass


@events.test_start.add_listener
def on_locust_init(environment, **kwargs):
    logger = logging.getLogger("web3.manager.RequestManager")
    logger.setLevel(logging.CRITICAL)

    print("Deploying TestToken contract")

    faucet = Account.from_key(PRIVATE_KEY)
    w3 = Web3(Web3.HTTPProvider(HOST))

    result = None
    while result is None:
        try:
            abi, contract_address = deploy_test_token_contract(w3, faucet, CHAIN_ID)
            result = True
        except Web3RPCError:
            pass
    print(f"TestToken contract deployed at address: {contract_address}")
    environment.test_token_abi = abi
    environment.test_token_address = contract_address
