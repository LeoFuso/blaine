package direct

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"sync"
	"time"

	"blaine.local/client/internal/process"
	"blaine.local/client/internal/wire"
)

type sessionWriter struct {
	ctx context.Context
	s   *Session
}

func (w sessionWriter) Write(b []byte) (int, error) {
	ctx, cancel := context.WithTimeout(w.ctx, 15*time.Second)
	defer cancel()
	if e := w.s.Send(ctx, Data, b); e != nil {
		return 0, e
	}
	return len(b), nil
}

type sessionReader struct {
	ctx    context.Context
	s      *Session
	buf    []byte
	cancel context.CancelFunc
}

func (r *sessionReader) Read(b []byte) (int, error) {
	for len(r.buf) == 0 {
		kind, data, e := r.s.Receive(r.ctx)
		if e != nil {
			return 0, e
		}
		switch kind {
		case Data:
			r.buf = data
		case End:
			if len(data) != 0 {
				return 0, errors.New("PROTOCOL_INVALID: end")
			}
			return 0, io.EOF
		case Cancel:
			if len(data) != 0 {
				return 0, errors.New("PROTOCOL_INVALID: cancel")
			}
			r.cancel()
			return 0, context.Canceled
		default:
			return 0, errors.New("PROTOCOL_INVALID: unexpected stream frame")
		}
	}
	n := copy(b, r.buf)
	r.buf = r.buf[n:]
	return n, nil
}

// RelayHost owns only the ACP subprocess group. EOF/cancel/disconnect never
// invokes Task cancellation or stops the durable runtime/Restate services.
func RelayHost(parent context.Context, s *Session, spec process.Spec, diagnostics *os.File) error {
	ctx, cancel := context.WithCancel(parent)
	defer cancel()
	inR, inW, e := os.Pipe()
	if e != nil {
		return e
	}
	defer inR.Close()
	defer inW.Close()
	outR, outW, e := os.Pipe()
	if e != nil {
		return e
	}
	defer outR.Close()
	defer outW.Close()
	done := make(chan int, 1)
	incoming := make(chan error, 1)
	outgoing := make(chan error, 1)
	guard := wire.NewSession()
	stop := context.AfterFunc(ctx, func() { s.Close(); inW.Close(); outR.Close() })
	defer stop()
	go func() {
		code, _ := process.Run(ctx, spec, process.Streams{In: inR, Out: outW, Err: diagnostics})
		outW.Close()
		done <- code
	}()
	go func() {
		e := guard.Forward(&sessionReader{ctx: ctx, s: s, cancel: cancel}, inW, 0)
		inW.Close()
		incoming <- e
	}()
	go func() { outgoing <- guard.Forward(outR, sessionWriter{ctx, s}, 1) }()
	var code int
	childDone, outputDone := false, false
	for !childDone || !outputDone {
		select {
		case code = <-done:
			childDone = true
			done = nil
		case e = <-incoming:
			incoming = nil
			if e != nil {
				cancel()
				if !childDone {
					<-done
				}
				return e
			}
			// EOF requests graceful close; its deadline applies only to this subprocess.
			timer := time.AfterFunc(5*time.Second, cancel)
			defer timer.Stop()
		case e = <-outgoing:
			outputDone = true
			outgoing = nil
			if e != nil {
				cancel()
				if !childDone {
					<-done
				}
				return e
			}
		case <-ctx.Done():
			cancel()
			if !childDone {
				<-done
			}
			return ctx.Err()
		}
	}

	return s.Send(ctx, Exit, []byte{byte(code)})
}

// RelayClient accepts inherited stdio files. Closing a session interrupts reads
// without waiting for the IDE to produce another byte; no shell or text codec.
func RelayClient(parent context.Context, s *Session, streams process.Streams) error {
	return relayClient(parent, s, streams, streams.In)
}
func relayClient(parent context.Context, s *Session, streams process.Streams, input io.Reader) error {
	ctx, cancel := context.WithCancel(parent)
	var wg sync.WaitGroup
	defer func() { cancel(); s.Close(); streams.In.Close(); streams.Out.Close(); wg.Wait() }()
	stop := context.AfterFunc(ctx, func() { s.Close(); streams.In.Close(); streams.Out.Close() })
	defer stop()
	sent := make(chan error, 1)
	received := make(chan error, 1)
	guard := wire.NewSession()
	wg.Add(2)
	go func() {
		defer wg.Done()
		e := guard.Forward(input, sessionWriter{ctx, s}, 0)
		if e == nil {
			e = s.Send(ctx, End, nil)
		}
		sent <- e
	}()
	go func() {
		defer wg.Done()
		for {
			kind, b, e := s.Receive(ctx)
			if e != nil {
				received <- e
				return
			}
			if kind == Exit {
				if len(b) != 1 || b[0] != 0 {
					received <- errors.New("REMOTE_EXIT: ACP session failed")
				} else if guard.Pending() != 0 {
					received <- errors.New("ACP_INVALID: responses missing at exit")
				} else {
					received <- nil
				}
				return
			}
			if kind != Data {
				received <- errors.New("PROTOCOL_INVALID: expected ACP data")
				return
			}
			// A frame may contain multiple complete ACP lines; partial text cannot cross
			// frame boundaries here. Binary diagnostics use the separate probe mode.
			if e = guard.Forward(bytes.NewReader(b), streams.Out, 1); e != nil {
				received <- e
				return
			}
		}
	}()
	select {
	case e := <-sent:
		if e != nil {
			return e
		}
		select {
		case e = <-received:
			return e
		case <-ctx.Done():
			return ctx.Err()
		}
	case e := <-received:
		return e
	case <-ctx.Done():
		return ctx.Err()
	}
}
