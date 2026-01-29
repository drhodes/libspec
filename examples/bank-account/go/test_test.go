package main

import (
	// "errors"
	// "fmt"
	"testing"
)


// --- Unit Tests (REQ-005) ---

func TestBankAPI(t *testing.T) {
	lib := NewBankLibrary()
	id := lib.CreateAccount("Alice")

	t.Run("Deposit Positive", func(t *testing.T) {
		if err := lib.Deposit(id, 100); err != nil {
			t.Errorf("Expected success, got %v", err)
		}
	})

	t.Run("CONST-001: Negative Deposit", func(t *testing.T) {
		if err := lib.Deposit(id, -50); err == nil {
			t.Error("Expected error for negative deposit")
		}
	})

	t.Run("CONST-002: Overdraft", func(t *testing.T) {
		if err := lib.Withdraw(id, 200); err == nil {
			t.Error("Expected error for withdrawing more than balance")
		}
	})

	t.Run("CONST-003: Invalid ID", func(t *testing.T) {
		if _, err := lib.Balance("INVALID"); err == nil {
			t.Error("Expected error for non-existent account ID")
		}
	})
}
