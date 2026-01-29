package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	// Define flags
	namePtr := flag.String("name", "", "Description: provide a name to greet")
	shortNamePtr := flag.String("n", "", "Description: provide a name to greet (shorthand)")
	
	repeatPtr := flag.Int("repeat", 1, "Description: repeat word N times.")
	shortRepeatPtr := flag.Int("r", 1, "Description: repeat word N times. (shorthand)")

	// Custom help description
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage of %s:\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  -h, --help      Description: show this help dialog\n")
		fmt.Fprintf(os.Stderr, "  -n, --name      Description: provide a name to greet\n")
		fmt.Fprintf(os.Stderr, "  -r, --repeat    Description: repeat word N times.\n")
	}

	flag.Parse()

	// Consolidate shorthand and long-form flags
	name := *namePtr
	if name == "" {
		name = *shortNamePtr
	}

	repeat := *repeatPtr
	if repeat == 1 && *shortRepeatPtr != 1 {
		repeat = *shortRepeatPtr
	}

	// Logic execution
	greeting := "Hello"
	if name != "" {
		greeting = fmt.Sprintf("Hello, %s", name)
	}

	for i := 0; i < repeat; i++ {
		fmt.Println(greeting)
	}
}
