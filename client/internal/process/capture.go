package process

import (
	"context"
	"errors"
	"io"
	"os"
)

// Capture uses Run's lifecycle with bounded in-memory pipes. It never writes
// child output to disk. notify receives merged stdout/stderr chunks on a reader goroutine
// and must return promptly. ACP continues to use the unchanged direct-fd Run path.
func Capture(ctx context.Context, spec Spec, in *os.File, notify func([]byte)) ([]byte, int, error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	if in == nil {
		var err error
		in, err = os.Open(os.DevNull)
		if err != nil {
			return nil, 1, errors.New("process input unavailable")
		}
		defer in.Close()
	}
	r, w, err := os.Pipe()
	if err != nil {
		return nil, 1, errors.New("process output unavailable")
	}
	defer r.Close()
	defer w.Close()
	// Merge output only for non-protocol commands; parsers reject non-JSON noise.
	type result struct {
		data []byte
		err  error
	}
	done := make(chan result, 1)
	go func() {
		data := make([]byte, 0, 4096)
		buf := make([]byte, 4096)
		for {
			n, e := r.Read(buf)
			if n > 0 {
				if len(data)+n > 1<<20 {
					cancel()
					done <- result{nil, errors.New("process output limit exceeded")}
					return
				}
				data = append(data, buf[:n]...)
				if notify != nil {
					notify(buf[:n])
				}
			}
			if e != nil {
				if e == io.EOF {
					e = nil
				}
				done <- result{data, e}
				return
			}
		}
	}()
	code, runErr := Run(ctx, spec, Streams{in, w, w})
	w.Close()
	var captured result
	select {
	case captured = <-done:
	case <-ctx.Done():
		// Windows interop or an escaped helper may retain an inherited descriptor.
		// Closing the read side prevents that from defeating a command deadline.
		r.Close()
		captured = <-done
	}
	if runErr != nil {
		return nil, code, runErr
	}
	if captured.err != nil {
		return nil, 1, errors.New("process output unavailable or too large")
	}
	return captured.data, code, runErr
}
