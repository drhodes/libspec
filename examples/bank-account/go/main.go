package main

import (
	"errors"
	"fmt"
)

// --- API Specification ---

type BankAPI interface {
	Version() string
	CreateAccount(owner string) string
	Deposit(accountID string, amount float64) error
	Withdraw(accountID string, amount float64) error
	Balance(accountID string) (float64, error)
	Transactions(accountID string) ([]float64, error)
}

// --- Implementation ---

type Account struct {
	ID           string
	Owner        string
	Balance      float64
	Transactions []float64
}

type BankLibrary struct {
	accounts map[string]*Account
}

func NewBankLibrary() *BankLibrary {
	return &BankLibrary{accounts: make(map[string]*Account)}
}

func (b *BankLibrary) Version() string {
	return "1"
}

func (b *BankLibrary) CreateAccount(owner string) string {
	id := fmt.Sprintf("ACC-%d", len(b.accounts)+1)
	b.accounts[id] = &Account{ID: id, Owner: owner, Transactions: []float64{}}
	return id
}

func (b *BankLibrary) Deposit(accountID string, amount float64) error {
	acc, exists := b.accounts[accountID]
	if !exists {
		return errors.New("CONST-003: account_id does not exist")
	}
	if amount <= 0 {
		return errors.New("CONST-001: transactions must be positive numbers")
	}
	acc.Balance += amount
	acc.Transactions = append(acc.Transactions, amount)
	return nil
}

func (b *BankLibrary) Withdraw(accountID string, amount float64) error {
	acc, exists := b.accounts[accountID]
	if !exists {
		return errors.New("CONST-003: account_id does not exist")
	}
	if amount <= 0 {
		return errors.New("CONST-001: transactions must be positive numbers")
	}
	if amount > acc.Balance {
		return errors.New("CONST-002: cannot withdraw more than current balance")
	}
	acc.Balance -= amount
	acc.Transactions = append(acc.Transactions, -amount)
	return nil
}

func (b *BankLibrary) Balance(accountID string) (float64, error) {
	acc, exists := b.accounts[accountID]
	if !exists {
		return 0, errors.New("CONST-003: account_id does not exist")
	}
	return acc.Balance, nil
}

func (b *BankLibrary) Transactions(accountID string) ([]float64, error) {
	acc, exists := b.accounts[accountID]
	if !exists {
		return nil, errors.New("CONST-003: account_id does not exist")
	}
	return acc.Transactions, nil
}

func main() {
	fmt.Println("BankAPI Library loaded. Version:", NewBankLibrary().Version())
}
