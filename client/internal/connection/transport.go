package connection

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/netip"
	"os"
	"os/exec"
	"strings"
	"time"

	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/process"
	"blaine.local/client/internal/wire"
)

type Transport interface {
	Handshake(context.Context, Profile) (Response, error)
	ACP(context.Context, Profile, process.Streams) (int, error)
}
type SSH struct{ Platform platform.Platform }

func Private(address string) bool {
	a, e := netip.ParseAddr(address)
	if e != nil {
		return false
	}
	return netip.MustParsePrefix("100.64.0.0/10").Contains(a) || netip.MustParsePrefix("fd7a:115c:a1e0::/48").Contains(a)
}
func (s SSH) command(ctx context.Context, p Profile, operation string) (process.Spec, error) {
	if operation != "handshake" && operation != "acp" {
		return process.Spec{}, errors.New("LOCAL_INVALID: unsupported host operation")
	}
	if e := p.Validate(false); e != nil {
		return process.Spec{}, e
	}
	if s.Platform.Kind == "wsl" {
		return process.Spec{}, errors.New("WSL_UNVERIFIED: guest route and transport identity require live acceptance")
	}
	ssh, e := exec.LookPath("ssh")
	if e != nil {
		return process.Spec{}, errors.New("LOCAL_INVALID: install native OpenSSH")
	}
	canonical, e := s.Platform.Tailscale().HostName(ctx, p.Host)
	if e != nil {
		return process.Spec{}, e
	}
	p.Host = canonical
	addresses, e := net.DefaultResolver.LookupHost(ctx, p.Host)
	if e != nil || len(addresses) == 0 {
		return process.Spec{}, errors.New("REMOTE_UNAVAILABLE: MagicDNS resolution failed")
	}
	for _, a := range addresses {
		if !Private(a) {
			return process.Spec{}, errors.New("IDENTITY_MISMATCH: host resolved outside the private Tailscale address space")
		}
	}
	// Pin the resolved address for this invocation, eliminating a second DNS lookup.
	// Native SSH trust remains authoritative; this command never writes known_hosts.
	return process.Spec{Executable: ssh, Args: SSHArgs(p, addresses[0], operation)}, nil
}
func SSHArgs(p Profile, address, operation string) []string {
	return []string{"-F", "/dev/null", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no", "-o", "GlobalKnownHostsFile=/dev/null", "-o", "HostKeyAlias=" + p.Host, "-o", "PreferredAuthentications=none", "-o", "PubkeyAuthentication=no", "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no", "-o", "ConnectTimeout=5", "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=1", "-o", "ForwardAgent=no", "-o", "ClearAllForwardings=yes", "-o", "PermitLocalCommand=no", "-o", "ControlMaster=no", "-o", "ControlPath=none", "-l", p.User, address, `exec "$HOME/.local/bin/blaine-host-connection" ` + operation}
}
func (s SSH) Handshake(ctx context.Context, p Profile) (Response, error) {
	bounded, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	spec, e := s.command(bounded, p, "handshake")
	if e != nil {
		return Response{}, e
	}
	return handshake(bounded, p, spec)
}
func handshake(ctx context.Context, p Profile, spec process.Spec) (Response, error) {
	data, _ := json.Marshal(Hello(p))
	data = append(data, '\n')
	out, code, e := control(ctx, spec, data)
	if e != nil || code != 0 {
		return Response{}, errors.New("REMOTE_UNAVAILABLE: verified SSH/control failed; check host trust, access, check-mode reauthentication in a terminal, and installed host entrypoint with the operator; no fallback")
	}
	return Validate(out, p)
}

// Control stdout and diagnostics have distinct pipes, hard bounds and deadline.
// Raw SSH/server diagnostics are deliberately not reflected into exported output.
func control(ctx context.Context, spec process.Spec, data []byte) ([]byte, int, error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	in, iw, e := os.Pipe()
	if e != nil {
		return nil, 1, e
	}
	defer in.Close()
	defer iw.Close()
	out, ow, e := os.Pipe()
	if e != nil {
		return nil, 1, e
	}
	defer out.Close()
	defer ow.Close()
	errFile, e := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if e != nil {
		return nil, 1, e
	}
	defer errFile.Close()
	sent := make(chan struct{})
	go func() { defer close(sent); _, _ = iw.Write(data); iw.Close() }()
	type captured struct {
		data []byte
		err  error
	}
	done := make(chan captured, 1)
	go func() {
		b, e := io.ReadAll(io.LimitReader(out, wire.Limit+1))
		if len(b) > wire.Limit {
			cancel()
			e = errors.New("control output limit")
		}
		done <- captured{b, e}
	}()
	code, e := process.Run(ctx, spec, process.Streams{In: in, Out: ow, Err: errFile})
	ow.Close()
	iw.Close()
	// An escaped writer cannot extend the bounded control invocation.
	select {
	case r := <-done:
		<-sent
		if e == nil {
			e = r.err
		}
		return r.data, code, e
	case <-ctx.Done():
		out.Close()
		<-done
		<-sent
		return nil, code, ctx.Err()
	}
}
func (s SSH) ACP(ctx context.Context, p Profile, streams process.Streams) (int, error) {
	if _, e := s.Handshake(ctx, p); e != nil {
		return Exit(e), e
	}
	bounded, cancel := context.WithTimeout(ctx, 5*time.Second)
	spec, e := s.command(bounded, p, "acp")
	cancel()
	if e != nil {
		return 3, e
	}
	return Framed(ctx, spec, streams)
}
func Framed(ctx context.Context, spec process.Spec, streams process.Streams) (int, error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	input, send, e := os.Pipe()
	if e != nil {
		return 1, e
	}
	defer input.Close()
	defer send.Close()
	receive, output, e := os.Pipe()
	if e != nil {
		return 1, e
	}
	defer receive.Close()
	defer output.Close()
	session := wire.NewSession()
	done := make(chan error, 2)
	go func() {
		e := session.Forward(streams.In, send, 0)
		send.Close()
		if e != nil {
			cancel()
		} else {
			// EOF ends this connection even if the remote ignores its stdin.
			time.AfterFunc(time.Second, cancel)
		}
		done <- e
	}()
	go func() {
		e := session.Forward(receive, streams.Out, 1)
		if e != nil {
			cancel()
		}
		done <- e
	}()
	code, runErr := process.Run(ctx, spec, process.Streams{In: input, Out: output, Err: streams.Err})
	output.Close()
	// ACP owns its stdio for this launch. Close blocked input/output on completion
	// or cancellation, so neither peer can retain the transport through backpressure.
	streams.In.Close()
	if ctx.Err() != nil {
		receive.Close()
		streams.Out.Close()
	}
	timer := time.NewTimer(time.Second)
	defer timer.Stop()
	for i := 0; i < 2; {
		select {
		case e := <-done:
			i++
			if e != nil && !errors.Is(e, os.ErrClosed) {
				runErr = e
			}
		case <-timer.C:
			receive.Close()
			streams.Out.Close()
			runErr = errors.New("ACP drain deadline")
		}
	}
	if code == 0 && session.Pending() != 0 {
		runErr = errors.New("ACP ended with unanswered requests")
	}
	if runErr != nil {
		return 1, errors.New("ACP_INVALID_OR_LOST: transport closed; inspect the existing Task after reconnecting")
	}
	return code, nil
}
func Exit(err error) int {
	if err == nil {
		return 0
	}
	s := err.Error()
	if strings.HasPrefix(s, "INCOMPATIBLE") {
		return 4
	}
	if strings.HasPrefix(s, "REMOTE_") {
		return 3
	}
	return 2
}
