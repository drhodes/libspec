mod lib;
use lib::{BankAPI, BankLibrary};

fn main() {
    let mut bank = BankLibrary::new();
    println!("Bank API Version: {}", bank.version());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_constraints() {
        let mut bank = BankLibrary::new();
        let id = bank.create_account("User".into());

        // Test CONST-001
        assert!(bank.deposit(&id, -10.0).is_err());

        // Test CONST-002
        bank.deposit(&id, 50.0).unwrap();
        assert!(bank.withdraw(&id, 100.0).is_err());

        // Test CONST-003
        assert!(bank.balance("FAKE").is_err());
        
        // Test REQ-004
        assert_eq!(bank.balance(&id).unwrap(), 50.0);
    }
}
