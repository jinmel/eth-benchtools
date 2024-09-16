import time
import logging

import locust.stats
from locust import User, task, tag, constant_throughput
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.exceptions import Web3RPCError
from eth_account import Account
from locust import events
from lib.transfers import transfer_balance, transfer_erc20
from lib.deployer import deploy_test_token_contract


locust.stats.CSV_STATS_INTERVAL_SEC = 5 # default is 1 second


class Web3User(User):
    account: Account
    wait_time = constant_throughput(1)

    def __init__(self, environment):
        super().__init__(environment)
        self.w3 = Web3(Web3.HTTPProvider(self.host))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.create()

    @task
    @tag("eth")
    def transfer_balance(self):
        chain_id = self.environment.parsed_options.chain_id
        random_account = Account.create()
        start_perf_counter = time.perf_counter()
        start_time = time.time()
        receipt = transfer_balance(self.w3, random_account.address, chain_id, 1, self.account)
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
        chain_id = self.environment.parsed_options.chain_id
        random_account = Account.create()
        start_perf_counter = time.perf_counter()
        start_time = time.time()
        receipt = transfer_erc20(self.w3, random_account.address, chain_id, 1, self.environment.test_token_address,
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
        faucet = Account.from_key(self.environment.parsed_options.faucet_pk)
        chain_id = self.environment.parsed_options.chain_id

        result = None
        while result is None:
            try:
                result = transfer_balance(self.w3, self.account.address, chain_id,
                                          self.environment.parsed_options.fund_amount, faucet)
            except Web3RPCError:
                pass

        result = None
        while result is None:
            try:
                result = transfer_erc20(
                    self.w3, self.account.address, chain_id, self.environment.parsed_options.fund_amount,
                    self.environment.test_token_address, self.environment.test_token_abi, faucet)
            except Web3RPCError:
                pass


@events.test_start.add_listener
def on_locust_init(environment, **kwargs):
    logger = logging.getLogger("web3.manager.RequestManager")
    logger.setLevel(logging.CRITICAL)

    faucet = Account.from_key(environment.parsed_options.faucet_pk)
    chain_id = environment.parsed_options.chain_id
    w3 = Web3(Web3.HTTPProvider(environment.host))

    result = None
    while result is None:
        try:
            abi, contract_address = deploy_test_token_contract(w3, faucet, chain_id)
            result = True
        except Web3RPCError:
            pass
    environment.test_token_abi = abi
    environment.test_token_address = contract_address


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--faucet-pk", type=str, env_var="LOCUST_FAUCET_PK", default="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", help="Private key of the faucet account")
    parser.add_argument("--chain-id", type=int, env_var="LOCUST_CHAIN_ID", default=901, help="Chain ID of the network")
    parser.add_argument('--fund_amount', type=int, env_var="LOCUST_FUND_AMOUNT", default=10 ** 18, help="Funded balance per account")
