package cli

import (
	"blaine.local/client/internal/fixture"
	"os"
	"time"
)

// Also bound direct invocation of the private worker, including blocked I/O.
func timeLimit() func() {
	timer := time.AfterFunc(fixture.Timeout, func() { os.Exit(124) })
	return func() { timer.Stop() }
}
