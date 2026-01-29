import pytest
from typing import List, Dict, Any, Optional

# ==========================================
# Implementation
# ==========================================

class BankError(Exception):
    """Base class for bank API exceptions."""
    pass

class BankAPI:
    """
    Bank Account API implementation.
    Library API Version: 1 [cite: 12]
    """
    
    def __init__(self):
        self._accounts: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self._version = "1"

    def version(self) -> str:
        """
        Return the version of this API. [cite: 13]
        """
        return self._version

    def create_account(self, owner: str) -> int:
        """
        Create a new account for the given owner. [cite: 14]
        Returns the new account_id.
        """
        account_id = self._next_id
        self._next_id += 1
        self._accounts[account_id] = {
            "owner": owner,
            "balance": 0.0,
            "transactions": []
        }
        return account_id

    def _get_account(self, account_id: int) -> Dict[str, Any]:
        """Helper to retrieve account or raise error if invalid."""
        if account_id not in self._accounts:
            # CONSTRAINT-003: All operations require a valid account ID.
            # ENFORCEMENT: Raise an error if account_id does not exist [cite: 11]
            raise BankError(f"Account {account_id} not found.")
        return self._accounts[account_id]

    def deposit(self, account_id: int, amount: float) -> None:
        """
        Deposit money into the specified account. [cite: 15]
        """
        # CONSTRAINT-001: Transactions must be positive numbers.
        # ENFORCEMENT: Raise an error if transaction amount <= 0 [cite: 9]
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")

        account = self._get_account(account_id)
        account["balance"] += amount
        account["transactions"].append({"type": "deposit", "amount": amount})

    def withdraw(self, account_id: int, amount: float) -> None:
        """
        Withdraw money if balance allows. [cite: 16]
        """
        # CONSTRAINT-001: Transactions must be positive numbers. [cite: 9]
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")

        account = self._get_account(account_id)
        
        # CONSTRAINT-002: Cannot withdraw more than current balance.
        # ENFORCEMENT: Raise an error if withdraw amount > account.balance [cite: 10]
        if amount > account["balance"]:
            raise BankError("Insufficient funds.")

        account["balance"] -= amount
        account["transactions"].append({"type": "withdraw", "amount": -amount})

    def balance(self, account_id: int) -> float:
        """
        Return current account balance. [cite: 17]
        """
        account = self._get_account(account_id)
        return account["balance"]

    def transactions(self, account_id: int) -> List[Dict[str, Any]]:
        """
        Return the transaction history. [cite: 17]
        """
        account = self._get_account(account_id)
        return account["transactions"]

# ==========================================
# Test Suite (pytest) [cite: 5]
# ==========================================

@pytest.fixture
def bank():
    return BankAPI()

def test_version(bank):
    assert bank.version() == "1"

def test_create_account(bank):
    acct_id = bank.create_account("Alice")
    assert acct_id is not None
    assert bank.balance(acct_id) == 0.0

def test_deposit(bank):
    acct_id = bank.create_account("Bob")
    bank.deposit(acct_id, 100.0)
    assert bank.balance(acct_id) == 100.0
    
    # Check transaction log
    txs = bank.transactions(acct_id)
    assert len(txs) == 1
    assert txs[0]["type"] == "deposit"
    assert txs[0]["amount"] == 100.0

def test_withdraw(bank):
    acct_id = bank.create_account("Charlie")
    bank.deposit(acct_id, 100.0)
    bank.withdraw(acct_id, 40.0)
    assert bank.balance(acct_id) == 60.0
    
    # Check transaction log for negative amount representation
    txs = bank.transactions(acct_id)
    assert len(txs) == 2
    assert txs[1]["type"] == "withdraw"
    assert txs[1]["amount"] == -40.0

def test_constraint_transactions_must_be_positive(bank):
    """Test CONST-001: Raise error if amount <= 0 [cite: 9]"""
    acct_id = bank.create_account("Dave")
    
    with pytest.raises(ValueError):
        bank.deposit(acct_id, -50)
        
    with pytest.raises(ValueError):
        bank.deposit(acct_id, 0)

    # Deposit some money first to test withdrawal constraint
    bank.deposit(acct_id, 100)
    with pytest.raises(ValueError):
        bank.withdraw(acct_id, -10)

def test_constraint_insufficient_funds(bank):
    """Test CONST-002: Raise error if withdraw > balance [cite: 10]"""
    acct_id = bank.create_account("Eve")
    bank.deposit(acct_id, 50.0)
    
    with pytest.raises(BankError, match="Insufficient funds"):
        bank.withdraw(acct_id, 100.0)

def test_constraint_invalid_account(bank):
    """Test CONST-003: Raise error if account_id does not exist [cite: 11]"""
    invalid_id = 999
    
    with pytest.raises(BankError, match=f"Account {invalid_id} not found"):
        bank.deposit(invalid_id, 100)
        
    with pytest.raises(BankError):
        bank.balance(invalid_id)

if __name__ == "__main__":
    # Allows running the file directly to execute tests
    import sys
    sys.exit(pytest.main(["-v", __file__]))
