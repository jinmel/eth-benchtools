// main.go

package main

import (
	"context"
	"crypto/ecdsa"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/big"
	"math/rand"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/accounts/abi/bind"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
)

// Command-line flags
var (
	faucetPK     = flag.String("faucet_pk", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", "Faucet private key")
	chainID      = flag.Int64("chain_id", 901, "Chain ID")
	host         = flag.String("host", "http://localhost:8545", "Host")
	fundAmount   = flag.String("fund_amount", "0.01", "Fund amount in ether")
	accountsFile = flag.String("accounts_file", "", "File containing accounts' private keys")
	outputDir    = flag.String("output_dir", "", "History output directory")
	txCount      = flag.Int("txcount", 100, "Number of transactions to send per account")
	numAccounts  = flag.Int("num_accounts", 100, "Number of accounts to create if accounts_file does not exist")
)

func main() {
	flag.Parse()

	// Check required flags
	if *accountsFile == "" || *outputDir == "" {
		log.Fatal("flags accounts_file and output_dir are required")
	}

	// Create output directory if it doesn't exist
	err := os.MkdirAll(*outputDir, os.ModePerm)
	if err != nil {
		log.Fatalf("Failed to create output directory: %v", err)
	}

	// Read or create accounts
	accounts, err := readOrCreateAccounts(*accountsFile, *numAccounts)
	if err != nil {
		log.Fatalf("Failed to read or create accounts: %v", err)
	}

	// Connect to Ethereum node
	client, err := ethclient.Dial(*host)
	if err != nil {
		log.Fatalf("Failed to connect to Ethereum client: %v", err)
	}

	// Load faucet account
	faucetPrivateKey, err := crypto.HexToECDSA(strings.TrimPrefix(*faucetPK, "0x"))
	if err != nil {
		log.Fatalf("Failed to load faucet private key: %v", err)
	}

	// Deploy ERC20 test contract
	log.Println("Deploying ERC20 test contract")
	contractAddress, contractABI, err := deployTestTokenContract(client, faucetPrivateKey, big.NewInt(*chainID))
	if err != nil {
		log.Fatalf("Failed to deploy test token contract: %v", err)
	}
	log.Printf("Deployed contract at %s\n", contractAddress.Hex())

	// Fund accounts
	log.Printf("Funding %d accounts\n", len(accounts))

	fundAmt, err := strconv.ParseFloat(*fundAmount, 64)
	if err != nil {
		log.Fatalf("Failed to parse fund amount: %v", err)
	}

	err = fundAccounts(client, accounts, etherToWei(fundAmt), contractAddress, contractABI, faucetPrivateKey)
	if err != nil {
		log.Fatalf("Failed to fund accounts: %v", err)
	}

	// Transfer ETH and ERC20 tokens
	log.Printf("Sending %d transactions from %d accounts\n", *txCount, len(accounts))
	err = transferTokens(client, accounts, big.NewInt(*chainID), contractAddress, contractABI, *txCount, *outputDir)
	if err != nil {
		log.Fatalf("Failed to transfer tokens: %v", err)
	}

	log.Println("Done")
}

// readOrCreateAccounts reads existing accounts from a file or creates new ones.
func readOrCreateAccounts(accountsFile string, numAccounts int) ([]*ecdsa.PrivateKey, error) {
	var accounts []*ecdsa.PrivateKey

	if _, err := os.Stat(accountsFile); err == nil {
		// File exists, read accounts
		log.Printf("Reading accounts from %s\n", accountsFile)
		data, err := os.ReadFile(accountsFile)
		if err != nil {
			return nil, fmt.Errorf("failed to read accounts file: %v", err)
		}
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			pkHex := strings.TrimSpace(line)
			if pkHex == "" {
				continue
			}
			pk, err := crypto.HexToECDSA(strings.TrimPrefix(pkHex, "0x"))
			if err != nil {
				return nil, fmt.Errorf("invalid private key %s: %v", pkHex, err)
			}
			accounts = append(accounts, pk)
		}
	} else {
		// File does not exist, create accounts
		log.Printf("Generating %d accounts\n", numAccounts)
		for i := 0; i < numAccounts; i++ {
			pk, err := crypto.GenerateKey()
			if err != nil {
				return nil, fmt.Errorf("failed to generate key: %v", err)
			}
			accounts = append(accounts, pk)
		}
		// Write accounts to file
		file, err := os.Create(accountsFile)
		if err != nil {
			return nil, fmt.Errorf("failed to create accounts file: %v", err)
		}
		defer file.Close()
		for _, pk := range accounts {
			pkBytes := crypto.FromECDSA(pk)
			pkHex := hex.EncodeToString(pkBytes)
			_, err := file.WriteString(pkHex + "\n")
			if err != nil {
				return nil, fmt.Errorf("failed to write to accounts file: %v", err)
			}
		}
		log.Printf("Done generating %d accounts to %s\n", numAccounts, accountsFile)
	}
	return accounts, nil
}

// deployTestTokenContract deploys the ERC20 test token contract.
func deployTestTokenContract(client *ethclient.Client, faucetPrivateKey *ecdsa.PrivateKey, chainID *big.Int) (common.Address, abi.ABI, error) {
	// Load contract JSON
	contractJSON, err := os.ReadFile("contracts/out/Token.sol/TestToken.json")
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to read contract JSON: %v", err)
	}

	var contractData struct {
		ABI      json.RawMessage `json:"abi"`
		Bytecode struct {
			Object string `json:"object"`
		} `json:"bytecode"`
	}

	err = json.Unmarshal(contractJSON, &contractData)
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to unmarshal contract JSON: %v", err)
	}

	parsedABI, err := abi.JSON(strings.NewReader(string(contractData.ABI)))
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to parse contract ABI: %v", err)
	}

	bytecode := common.FromHex(contractData.Bytecode.Object)

	// Create transactor
	auth, err := bind.NewKeyedTransactorWithChainID(faucetPrivateKey, chainID)
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to create transactor: %v", err)
	}

	// Deploy contract
	address, tx, _, err := bind.DeployContract(auth, parsedABI, bytecode, client, auth.From)
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to deploy contract: %v", err)
	}

	// Wait for the transaction to be mined
	ctx := context.Background()
	receipt, err := bind.WaitMined(ctx, client, tx)
	if err != nil {
		return common.Address{}, abi.ABI{}, fmt.Errorf("failed to wait for contract deployment: %v", err)
	}
	if receipt.Status != types.ReceiptStatusSuccessful {
		return common.Address{}, abi.ABI{}, fmt.Errorf("contract deployment failed")
	}

	return address, parsedABI, nil
}

type SafeNonce struct {
	nonce uint64
	mu    sync.Mutex
}

func (s *SafeNonce) GetAndIncrement() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	ret := s.nonce
	s.nonce++
	return ret
}

// fundAccounts funds accounts with Ether and ERC20 tokens.
func fundAccounts(client *ethclient.Client, accounts []*ecdsa.PrivateKey, fundAmount *big.Int, tokenAddress common.Address, tokenABI abi.ABI, faucetPrivateKey *ecdsa.PrivateKey) error {
	ctx := context.Background()
	chainID := big.NewInt(*chainID)

	// Create transactor for faucet account
	auth, err := bind.NewKeyedTransactorWithChainID(faucetPrivateKey, chainID)
	if err != nil {
		return fmt.Errorf("failed to create transactor: %v", err)
	}

	faucetAddress := auth.From

	// Create instance of token contract
	tokenContract := bind.NewBoundContract(tokenAddress, tokenABI, client, client, client)

	nonce, err := client.PendingNonceAt(ctx, faucetAddress)

	if err != nil {
		return fmt.Errorf("failed to get nonce: %v", err)
	}

	gasPrice, err := client.SuggestGasPrice(ctx)
	if err != nil {
		return fmt.Errorf("failed to suggest gas price: %v", err)
	}

	for _, account := range accounts {
		accountAddress := crypto.PubkeyToAddress(account.PublicKey)
		balance, err := client.BalanceAt(ctx, accountAddress, nil)
		if err != nil {
			log.Printf("failed to get balance for %s: %v", accountAddress.Hex(), err)
		}
		value := new(big.Int).Sub(fundAmount, balance)
		if value.Sign() > 0 {
			go func(nonce uint64) {
				// Transfer Ether
				log.Printf("Transferring %s ETH to %s\n", weiToEther(value), accountAddress.Hex())
				tx := types.NewTransaction(nonce, accountAddress, value, uint64(21000), gasPrice, nil)
				signedTx, err := auth.Signer(auth.From, tx)
				if err != nil {
					log.Printf("failed to sign transaction: %v", err)
				}

				err = client.SendTransaction(ctx, signedTx)
				if err != nil {
					log.Printf("failed to send transaction: %v", err)
				}
			}(nonce)
			nonce++
		} else {
			log.Printf("Account %s already funded with %s ETH\n", accountAddress.Hex(), weiToEther(balance))
		}

		// Transfer ERC20 tokens
		go func(nonce uint64) {
			clonedAuth := *auth
			log.Printf("Transferring %s ERC20 tokens to %s\n", weiToEther(big.NewInt(1e18)), accountAddress.Hex())
			clonedAuth.Nonce = big.NewInt(int64(nonce))
			nonce++
			_, err = tokenContract.Transact(&clonedAuth, "transfer", accountAddress, big.NewInt(1e18))
			if err != nil {
				log.Printf("failed to transfer ERC20 tokens: %v", err)
			}
		}(nonce)
		nonce++
		log.Printf("Transferring %s ERC20 tokens to %s\n", weiToEther(big.NewInt(1e18)), accountAddress.Hex())
	}

	return nil
}

func transferEthLegacyTx(ctx context.Context, client *ethclient.Client, account *ecdsa.PrivateKey, to *common.Address, chainID *big.Int, nonce *big.Int) (*types.Receipt, error) {
	// Create transactor
	auth, err := bind.NewKeyedTransactorWithChainID(account, chainID)
	if err != nil {
		return nil, fmt.Errorf("failed to create transactor: %v", err)
	}

	gasPrice, err := client.SuggestGasPrice(ctx)
	if err != nil {
		return nil, fmt.Errorf("Failed to suggest gas price: %v", err)
	}

	value := big.NewInt(1) // Transfer 1 wei

	// Update auth object
	auth.Nonce = nonce
	auth.Value = value            // in wei
	auth.GasLimit = uint64(21000) // standard gas limit for ETH transfer
	auth.GasPrice = gasPrice

	log.Printf("Transferring %s ETH from %s to %s\n", weiToEther(value), auth.From.Hex(), to.Hex())

	tx := types.NewTransaction(auth.Nonce.Uint64(), *to, value, auth.GasLimit, auth.GasPrice, nil)

	signedTx, err := auth.Signer(auth.From, tx)

	err = client.SendTransaction(ctx, signedTx)
	if err != nil {
		return nil, fmt.Errorf("Failed to send transaction: %v", err)
	}

	receipt, err := bind.WaitMined(ctx, client, signedTx)
	if err != nil {
		return nil, fmt.Errorf("Failed to wait for transaction: %v", err)
	}

	return receipt, nil
}

func transferEthEIP1559(ctx context.Context, client *ethclient.Client, account *ecdsa.PrivateKey, to *common.Address, chainID *big.Int, nonce *big.Int) (*types.Receipt, error) {
	// Create transactor
	auth, err := bind.NewKeyedTransactorWithChainID(account, chainID)
	if err != nil {
		return nil, fmt.Errorf("failed to create transactor: %v", err)
	}

	// Suggest the max fee per gas and max priority fee per gas
	tipCap, err := client.SuggestGasTipCap(ctx)
	if err != nil {
		return nil, fmt.Errorf("Failed to suggest gas tip cap: %v", err)
	}

	gasFeeCap, err := client.SuggestGasPrice(ctx)
	if err != nil {
		return nil, fmt.Errorf("Failed to suggest gas fee cap: %v", err)
	}

	value := big.NewInt(1) // Transfer 1 wei

	// Update auth object
	auth.Nonce = nonce
	auth.Value = value            // in wei
	auth.GasLimit = uint64(21000) // standard gas limit for ETH transfer
	auth.GasFeeCap = gasFeeCap    // max fee per gas (base fee + priority fee)
	auth.GasTipCap = tipCap       // max priority fee per gas
	auth.GasPrice = nil           // no gas price

	log.Printf("Transferring %s ETH from %s to %s\n", weiToEther(value), auth.From.Hex(), to.Hex())

	// Create the EIP-1559 transaction
	tx := types.NewTx(&types.DynamicFeeTx{
		ChainID:   chainID,
		Nonce:     auth.Nonce.Uint64(),
		GasFeeCap: auth.GasFeeCap,
		GasTipCap: auth.GasTipCap,
		Gas:       auth.GasLimit,
		To:        to,
		Value:     auth.Value,
		Data:      nil, // No data for simple ETH transfer
	})

	signedTx, err := auth.Signer(auth.From, tx)
	if err != nil {
		return nil, fmt.Errorf("Failed to sign transaction: %v", err)
	}

	err = client.SendTransaction(ctx, signedTx)
	if err != nil {
		return nil, fmt.Errorf("Failed to send transaction: %v", err)
	}

	receipt, err := bind.WaitMined(ctx, client, signedTx)
	if err != nil {
		return nil, fmt.Errorf("Failed to wait for transaction: %v", err)
	}

	return receipt, nil
}

func transferERC20(ctx context.Context, client *ethclient.Client, account *ecdsa.PrivateKey, to *common.Address, chainID *big.Int, nonce *big.Int, tokenContractAddress common.Address, tokenABI abi.ABI) (*types.Receipt, error) {
	tokenContract := bind.NewBoundContract(tokenContractAddress, tokenABI, client, client, client)
	tokenValue := big.NewInt(1) // Adjust token amount as needed

	auth, err := bind.NewKeyedTransactorWithChainID(account, chainID)
	if err != nil {
		return nil, fmt.Errorf("Failed to create transactor: %v", err)
	}

	// Update auth object for token transfer
	auth.Nonce = nonce
	auth.Value = big.NewInt(0) // No ETH is being sent

	// Remove hardcoded gas limit
	// auth.GasLimit = uint64(70000)

	// Get suggested gas tip cap
	gasTipCap, err := client.SuggestGasTipCap(ctx)
	if err != nil {
		return nil, fmt.Errorf("Failed to suggest gas tip cap: %v", err)
	}

	// Get base fee from the latest block header
	header, err := client.HeaderByNumber(ctx, nil) // nil gets the latest block
	if err != nil {
		return nil, fmt.Errorf("Failed to get latest block header: %v", err)
	}
	baseFee := header.BaseFee
	if baseFee == nil {
		return nil, fmt.Errorf("Base fee is nil. Ensure that EIP-1559 is activated on this network.")
	}

	// Compute gas fee cap (maxFeePerGas)
	gasFeeCap := new(big.Int).Add(
		new(big.Int).Mul(baseFee, big.NewInt(2)), // baseFee * 2
		gasTipCap,                                // + gasTipCap
	)

	// Set the auth.GasFeeCap and auth.GasTipCap
	auth.GasFeeCap = gasFeeCap
	auth.GasTipCap = gasTipCap
	auth.GasPrice = nil

	// Prepare the transaction data
	data, err := tokenABI.Pack("transfer", to, tokenValue)
	if err != nil {
		return nil, fmt.Errorf("Failed to pack transfer data: %v", err)
	}

	// Create a call message for estimating gas
	callMsg := ethereum.CallMsg{
		From:      auth.From,
		To:        &tokenContractAddress,
		Gas:       0, // gas is set to 0, which means gas estimation is needed
		Value:     big.NewInt(0),
		Data:      data,
		GasFeeCap: gasFeeCap,
		GasTipCap: gasTipCap,
	}

	// Estimate gas limit
	gasLimit, err := client.EstimateGas(ctx, callMsg)
	if err != nil {
		return nil, fmt.Errorf("Failed to estimate gas: %v", err)
	}

	// Optionally add a buffer to the estimated gas limit
	gasLimit = gasLimit + gasLimit/10 // Increase gas limit by 10%

	// Set the gas limit in the auth
	auth.GasLimit = gasLimit

	log.Printf("Transferring %s tokens from %s to %s\n", tokenValue.String(), auth.From.Hex(), to.Hex())
	tx, err := tokenContract.Transact(auth, "transfer", to, tokenValue)
	if err != nil {
		return nil, fmt.Errorf("Failed to create token transfer transaction: %v", err)
	}

	// Wait for transaction to be mined
	receipt, err := bind.WaitMined(ctx, client, tx)
	if err != nil {
		return nil, fmt.Errorf("Failed to wait for token transfer transaction: %v", err)
	}
	return receipt, nil
}

func transferTokens(client *ethclient.Client, accounts []*ecdsa.PrivateKey, chainID *big.Int, tokenAddress common.Address, tokenABI abi.ABI, txCount int, outputDir string) error {
	var wg sync.WaitGroup

	for _, account := range accounts {
		wg.Add(1)

		go func(acc *ecdsa.PrivateKey) {
			defer wg.Done()

			ctx := context.Background()

			data := []map[string]interface{}{}

			nonce, err := client.PendingNonceAt(ctx, crypto.PubkeyToAddress(acc.PublicKey))
			if err != nil {
				log.Printf("Failed to get nonce: %v", err)
				return
			}

			for i := 0; i < txCount; i++ {
				toAccount := accounts[rand.Intn(len(accounts))]
				toAddress := crypto.PubkeyToAddress(toAccount.PublicKey)
				startTime := time.Now()

				var kind string
				var receipt *types.Receipt
				switch rand.Intn(2) {
				case 0:
					kind = "erc20-transfer"
					receipt, err = transferERC20(ctx, client, acc, &toAddress, chainID, big.NewInt(int64(nonce)), tokenAddress, tokenABI)
				// case 0:
				// 	kind = "eth-transfer-legacy"
				// 	receipt, err = transferEthLegacyTx(ctx, client, acc, &toAddress, chainID, big.NewInt(int64(nonce)))
				case 1:
					kind = "eth-transfer-eip1559"
					receipt, err = transferEthEIP1559(ctx, client, acc, &toAddress, chainID, big.NewInt(int64(nonce)))
				}

				if err != nil {
					log.Printf("Failed to transfer tokens: %v", err)
					continue
				}

				// update nonce
				nonce++
				endTime := time.Now()
				receiptMap := map[string]interface{}{
					"kind":            kind,
					"tx_hash":         receipt.TxHash.Hex(),
					"block_number":    receipt.BlockNumber.Uint64(),
					"gas_used":        receipt.GasUsed,
					"status":          receipt.Status,
					"start_time":      startTime.UnixMilli(),
					"end_time":        endTime.UnixMilli(),
					"time_to_include": endTime.Sub(startTime).Microseconds(),
				}
				data = append(data, receiptMap)
			}

			// Write data to CSV
			writeToRandomFile(data, outputDir)
		}(account)
	}
	wg.Wait()
	return nil
}

// writeToRandomFile writes data to a CSV file with a random name.
func writeToRandomFile(data []map[string]interface{}, outputDir string) {
	if len(data) == 0 {
		log.Println("No data to write")
		return
	}
	randomName := getRandomName()
	filename := filepath.Join(outputDir, fmt.Sprintf("%s.csv", randomName))

	file, err := os.Create(filename)
	if err != nil {
		log.Printf("Failed to create file %s: %v", filename, err)
		return
	}
	defer file.Close()

	// Write CSV header
	var headers []string
	for key := range data[0] {
		headers = append(headers, key)
	}
	writer := csv.NewWriter(file)
	err = writer.Write(headers)
	if err != nil {
		log.Printf("Failed to write headers to CSV: %v", err)
		return
	}

	// Write data rows
	for _, row := range data {
		var values []string
		for _, header := range headers {
			value := fmt.Sprintf("%v", row[header])
			values = append(values, value)
		}
		err = writer.Write(values)
		if err != nil {
			log.Printf("Failed to write row to CSV: %v", err)
			return
		}
	}
	writer.Flush()

	log.Printf("Done writing to %s\n", filename)
}

// getRandomName generates a random string of 8 characters.
func getRandomName() string {
	letters := []rune("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
	b := make([]rune, 8)
	for i := range b {
		b[i] = letters[rand.Intn(len(letters))]
	}
	return string(b)
}

// weiToEther converts Wei to Ether as a string.
func weiToEther(wei *big.Int) string {
	ether := new(big.Float).Quo(new(big.Float).SetInt(wei), big.NewFloat(1e18))
	return ether.Text('f', 18)
}

func etherToWei(ether float64) *big.Int {
	wei := new(big.Float).Mul(big.NewFloat(ether), big.NewFloat(1e18))
	intWei, _ := wei.Int(nil)
	return intWei
}
