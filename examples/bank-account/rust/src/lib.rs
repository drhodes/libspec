use std::collections::HashMap;

pub type Result<T> = std::result::Result<T, String>;

pub trait BankAPI {
    fn version(&self) -> String;
    fn create_account(&mut self, owner: String) -> String;
    fn deposit(&mut self, account_id: &str, amount: f64) -> Result<()>;
    fn withdraw(&mut self, account_id: &str, amount: f64) -> Result<()>;
    fn balance(&self, account_id: &str) -> Result<f64>;
    fn transactions(&self, account_id: &str) -> Result<Vec<f64>>;
}

struct Account {
    balance: f64,
    history: Vec<f64>,
}

pub struct BankLibrary {
    accounts: HashMap<String, Account>,
}

impl BankLibrary {
    pub fn new() -> Self {
        Self { accounts: HashMap::new() }
    }
}

impl BankAPI for BankLibrary {
    fn version(&self) -> String { "1".to_string() }

    fn create_account(&mut self, owner: String) -> String {
        let id = format!("ACC-{}", self.accounts.len() + 1);
        self.accounts.insert(id.clone(), Account { balance: 0.0, history: Vec::new() });
        id
    }

    fn deposit(&mut self, account_id: &str, amount: f64) -> Result<()> {
        let acc = self.accounts.get_mut(account_id).ok_or("CONST-003: Invalid ID")?;
        if amount <= 0.0 { return Err("CONST-001: Must be positive".into()); }
        acc.balance += amount;
        acc.history.push(amount);
        Ok(())
    }

    fn withdraw(&mut self, account_id: &str, amount: f64) -> Result<()> {
        let acc = self.accounts.get_mut(account_id).ok_or("CONST-003: Invalid ID")?;
        if amount <= 0.0 { return Err("CONST-001: Must be positive".into()); }
        if amount > acc.balance { return Err("CONST-002: Insufficient funds".into()); }
        acc.balance -= amount;
        acc.history.push(-amount);
        Ok(())
    }

    fn balance(&self, account_id: &str) -> Result<f64> {
        self.accounts.get(account_id).map(|a| a.balance).ok_or("CONST-003: Invalid ID".into())
    }

    fn transactions(&self, account_id: &str) -> Result<Vec<f64>> {
        self.accounts.get(account_id).map(|a| a.history.clone()).ok_or("CONST-003: Invalid ID".into())
    }
}
