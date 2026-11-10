from decimal import Decimal, InvalidOperation


PIN = "1234"
MAX_PIN_ATTEMPTS = 3


def read_amount(prompt: str) -> Decimal:
    while True:
        try:
            amount = Decimal(input(prompt).strip())
            if not amount.is_finite() or amount <= 0:
                raise ValueError
            if amount != amount.quantize(Decimal("0.01")):
                print("Enter an amount with no more than two decimal places.")
                continue
            return amount
        except (InvalidOperation, ValueError):
            print("Enter a valid amount greater than zero.")


def authenticate() -> bool:
    for attempt in range(MAX_PIN_ATTEMPTS):
        entered_pin = input("Enter your PIN: ").strip()
        if entered_pin == PIN:
            return True

        attempts_left = MAX_PIN_ATTEMPTS - attempt - 1
        if attempts_left:
            print(f"Incorrect PIN. {attempts_left} attempt(s) remaining.")
    print("Too many incorrect attempts. Access denied.")
    return False


def main() -> None:
    balance = Decimal("0.00")

    print("Welcome to the ATM")
    if not authenticate():
        return

    while True:
        print("\nATM Menu")
        print("1. Check balance")
        print("2. Deposit money")
        print("3. Withdraw money")
        print("4. Exit")

        choice = input("Choose an option (1-4): ").strip()
        if choice == "1":
            print(f"Your balance is ${balance:.2f}")
        elif choice == "2":
            amount = read_amount("Enter deposit amount: ")
            balance += amount
            print(f"${amount:.2f} deposited. Your balance is ${balance:.2f}")
        elif choice == "3":
            amount = read_amount("Enter withdrawal amount: ")
            if amount > balance:
                print("Insufficient funds.")
            else:
                balance -= amount
                print(f"${amount:.2f} withdrawn. Your balance is ${balance:.2f}")
        elif choice == "4":
            print("Thank you for using the ATM.")
            return
        else:
            print("Invalid option. Choose a number from 1 to 4.")


if __name__ == "__main__":
    main()
