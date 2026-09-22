package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"blaine.local/client/internal/cli"
	"blaine.local/client/internal/process"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	code := cli.Run(ctx, os.Args[1:], process.Streams{In: os.Stdin, Out: os.Stdout, Err: os.Stderr})
	cancel()
	os.Exit(code)
}
