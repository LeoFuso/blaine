//go:build linux || darwin

package direct

import (
	"bytes"
	"context"
	"io"
	"testing"
	"time"

	"golang.org/x/sys/unix"
)

func TestBorrowedDescriptorsPreserveBytesEOFAndOwnership(t *testing.T) {
	r, w := blockingPipe(t)
	defer r.Close()
	defer w.Close()
	flags, e := unix.FcntlInt(r.Fd(), unix.F_GETFL, 0)
	if e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	in, e := borrowFile(ctx, r)
	if e != nil {
		t.Fatal(e)
	}
	defer in.Close()
	out, e := borrowFile(ctx, w)
	if e != nil {
		t.Fatal(e)
	}
	defer out.Close()
	payload := make([]byte, 1<<20)
	for i := range payload {
		payload[i] = byte(i)
	}
	done := make(chan error, 1)
	go func() {
		_, e := out.Write(payload)
		done <- e
	}()
	actual := make([]byte, len(payload))
	if _, e = io.ReadFull(in, actual); e != nil {
		t.Fatal(e)
	}
	if e = <-done; e != nil || !bytes.Equal(payload, actual) {
		t.Fatal("bytes changed", e)
	}
	if e = out.Close(); e != nil {
		t.Fatal(e)
	}
	// The original writer remains usable after releasing the duplicate.
	if _, e = w.Write([]byte{0xff}); e != nil {
		t.Fatal(e)
	}
	w.Close()
	b, e := io.ReadAll(in)
	if e != nil || !bytes.Equal(b, []byte{0xff}) {
		t.Fatal("EOF or ownership", b, e)
	}
	if e = in.Close(); e != nil {
		t.Fatal(e)
	}
	restored, e := unix.FcntlInt(r.Fd(), unix.F_GETFL, 0)
	if e != nil || restored != flags {
		t.Fatal("original flags not restored", restored, flags, e)
	}
	if _, e = r.Read(make([]byte, 1)); e != io.EOF {
		t.Fatal("original input was closed", e)
	}
}
