# Web3 locust

## Introduction

Locust for load testing rpc node with spam transactions.

## How to run

```sh
cd contracts
forge build
poetry run locust --host <rpc-node-url> --processes 4 --users 100 --spawn-rate 10 --csv <output-prefix> --csv-full-history --faucet-pk <faucet-private-key> --chain-id <chain_id>
```

Go to `localhost:8089` to see the locust dashboard.

### Additional options

Specify the transaction types to run with tags. For example, to run only `eth_transfer` type transactions:

```sh
poetry run locust --host <rpc-node-url> --processes 4 --users 100 --spawn-rate 10 --csv <output-prefix> --csv-full-history --faucet-pk <faucet-private-key> --chain-id <chain_id> --tags eth
```

To run with both eth and erc20 transfers:

```sh
poetry run locust --host <rpc-node-url> --processes 4 --users 100 --spawn-rate 10 --csv <output-prefix> --csv-full-history --faucet-pk <faucet-private-key> --chain-id <chain_id> --tags eth erc20
```
