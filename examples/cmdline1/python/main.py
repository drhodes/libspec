import argparse
import sys

def main():
    # REQ-007: Uses Python programming language
    # REQ-006: Single source file
    parser = argparse.ArgumentParser(description="Description: show this help dialog")
    
    # -n --name
    parser.add_argument("-n", "--name", type=str, help="Description: provide a name to greet")
    
    # -r --repeat (N:int)
    parser.add_argument("-r", "--repeat", type=int, help="Description: repeat word N times.")

    args = parser.parse_args()

    # Logic to handle name and repeat
    word_to_print = f"Hello, {args.name}" if args.name else "Hello"
    
    count = args.repeat if args.repeat is not None else 1

    # If no arguments provided (other than help implicit), show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    for _ in range(count):
        print(word_to_print)

if __name__ == "__main__":
    main()
