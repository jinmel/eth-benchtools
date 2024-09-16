# Web3 locust

## Introduction

Load test tools for ethereum execution clients

## How to run

### Build the contracts
```sh
cd contracts
forge build
```

### Run the benchmark

```sh
go build
./eth-benchtools  --accounts_file accounts.txt --output_dir ./out --host <rpc_endpoint> --fund_amount 0.01 --faucet_pk <your_faucet_private_key> --chain_id <chain_id> --num_accounts 1000
```

### Generate the benchmark report

```sh
python generate_figures.py --data_folder ./out --plots_dir ./plots
```
