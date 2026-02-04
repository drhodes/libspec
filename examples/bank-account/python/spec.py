from libspec import (
    DataSchema,
    Requirement,
    Feature,
    Constraint,
    SystemRequirement,
    LibraryAPI,
)
from inspect import signature, cleandoc, isfunction

DATE = "2026-01-28"

## --- DATA SCHEMA ---
class Account(DataSchema):
    """Represents a bank account with balance and transaction history"""
    account_id: str
    owner: str
    balance: float
    transactions: list[dict]  # {"type": "deposit"|"withdraw", "amount": float}


class TransactionRequest(DataSchema):
    """Represents a request to deposit or withdraw money"""
    account_id: str
    amount: float


## --- REQUIREMENTS ---
class CreateAccount(Requirement):
    def req_id(self): return "REQ-001"
    def title(self): return "Create Bank Account"
    def actor(self): return "user"
    def action(self): return "request a new bank account"
    def benefit(self): return "have an account to manage funds"


class DepositMoney(Requirement):
    def req_id(self): return "REQ-002"
    def title(self): return "Deposit Money"
    def actor(self): return "user"
    def action(self): return "deposit money into account"
    def benefit(self): return "increase account balance"


class WithdrawMoney(Requirement):
    def req_id(self): return "REQ-003"
    def title(self): return "Withdraw Money"
    def actor(self): return "user"
    def action(self): return "withdraw money from account without overdrawing"
    def benefit(self): return "access cash while respecting balance"


class CheckBalance(Requirement):
    def req_id(self): return "REQ-004"
    def title(self): return "Check Balance"
    def actor(self): return "user"
    def action(self): return "view current account balance"
    def benefit(self): return "know available funds"

### System Requirements

class TestSuite(SystemRequirement):
    def req_id(self): return "REQ-005"
    def title(self): return "Test Suite"
    def actor(self): return "system"
    def action(self): return "build pytest tests for all endpoints"
    def benefit(self): return "ensure API behaves as expected"


class SingleFile(SystemRequirement):
    def req_id(self):  return "REQ-006"
    def title(self):   return "one-source-file"
    def actor(self):   return "LLM"
    def action(self):  return "generate API spec in a single source file"
    def benefit(self): return "simplifies example and makes it self contained"

class ProgrammingLanguage(SystemRequirement):
    def req_id(self):  return "REQ-007"
    def title(self):   return "specifies programming languages"
    def actor(self):   return "LLM"
    def action(self):  return "Uses the Python programming langauge"
    def benefit(self): return "tells the LLM which programming languages to use"


## --- FEATURES ---
class BankFeatures(Feature):
    def feature_name(self): return "bank-api-features"
    def date(self): return DATE
    def description(self): return (
        "Provides endpoints to create accounts, deposit, withdraw, "
        "check balance, and list transactions."
    )

## --- CONSTRAINTS ---
class PositiveTransaction(Constraint):
    def constraint_id(self): return "CONST-001"
    def description(self): return "Transactions must be positive numbers."
    def enforcement_logic(self):
        return "Raise an error if transaction amount <= 0"


class CannotOverdraw(Constraint):
    def constraint_id(self):
        return "CONST-002"
    def description(self):
        return "Cannot withdraw more than current balance."
    def enforcement_logic(self):
        return "Raise an error if withdraw amount > account.balance"


class ValidAccountId(Constraint):
    def constraint_id(self): return "CONST-003"
    def description(self): return "All operations require a valid account ID."
    def enforcement_logic(self):
        return "Raise an error if account_id does not exist"

    
## -- API --
class BankAPI(LibraryAPI):
    """Bank Account API spec: all endpoints are abstract."""
    def version(self):
        """Return the version of this API."""
        return 1
    
    def create_account(self, owner: str):
        """Create a new account for the given owner."""
          
    def deposit(self, account_id: str, amount: float):
        """Deposit money into the specified account."""

    def withdraw(self, account_id: str, amount: float):
        """Withdraw money if balance allows."""

    def balance(self, account_id: str) -> float:
        """Return current account balance."""

    def transactions(self, account_id: str) -> list[dict]:
        """Return the transaction history."""

    
## --- SPEC ---
class BankSpec:
    def __init__(self):
        self.components = [
            ProgrammingLanguage(),
            CheckBalance(),
            TestSuite(),
            SingleFile(),
            BankFeatures(),
            PositiveTransaction(),
            CannotOverdraw(),
            ValidAccountId(),
            BankAPI(),
        ]

    def generate_full_spec(self):
        return ("\n" + (80 * '-') + "\n").join(c.render() for c in self.components)

if __name__ == "__main__":
    spec_doc = BankSpec().generate_full_spec()
    print(spec_doc)

    
# if __name__ == "__main__":
#     api = BankAPI()
#     print("=== DEBUG: Checking what methods() returns ===")
#     methods = api.methods()
#     print(f"Number of methods found: {len(methods)}")
#     for m in methods:
#         print(f"  {m}")
    
#     print("\n=== DEBUG: Checking __dict__ ===")
#     for name, attr in BankAPI.__dict__.items():
#         print(f"  {name}: isfunction={isfunction(attr)}")
    
#     print("\n=== FULL SPEC ===")
#     spec_doc = BankSpec().generate_full_spec()
#     print(spec_doc)
