// Package fixture is a deliberately bounded byte-relay acceptance helper, not ACP
// or a transport. The parent imposes a five-second deadline even on blocked I/O.
package fixture

import (
	"fmt"
	"io"
	"os"
	"time"
)

const Timeout = 5 * time.Second
const MaxBytes = 1 << 20

func Valid(mode string) bool { return mode == "echo" || mode == "exit-23" || mode == "wait" }
func Run(mode string, in, out, errOut *os.File) int {
	fmt.Fprintln(errOut, "blaine: fixture child diagnostic")
	switch mode {
	case "echo":
		n, err := io.Copy(out, io.LimitReader(in, MaxBytes+1))
		if n > MaxBytes {
			fmt.Fprintln(errOut, "blaine: fixture input limit exceeded")
			return 1
		}
		if err != nil {
			return 1
		}
		return 0
	case "exit-23":
		return 23
	case "wait":
		time.Sleep(Timeout * 2)
		return 0
	default:
		return 64
	}
}
