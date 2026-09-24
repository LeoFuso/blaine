// Package connect implements only E0.B. Returning network readiness is the
// continuation boundary for E0.C, not completion of Blaine onboarding.
package connect

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"

	"blaine.local/client/internal/platform"
)

type Prerequisite interface {
	Inspect(context.Context) platform.Network
	Installation() platform.InstallPlan
	Install(context.Context, *os.File) error
	Authenticate(context.Context, *os.File, func(string)) error
}
type UI struct {
	In             *os.File
	Out            io.Writer
	Confirm        func(string) bool
	NonInteractive bool
}

func Run(ctx context.Context, p Prerequisite, ui UI) (code int) {
	output := &checkedWriter{writer: ui.Out}
	ui.Out = output
	defer func() {
		if output.err != nil {
			code = 1
		}
	}()
	fmt.Fprintln(ui.Out, "Checking workstation...")
	fmt.Fprintln(ui.Out, "✓ Blaine client\n✓ Platform detected")
	n := p.Inspect(ctx)
	if ctx.Err() != nil {
		return failure(ctx.Err(), ui.Out)
	}
	if n.Ready {
		return ready(ui.Out)
	}
	if n.Installed == "absent" {
		fmt.Fprintln(ui.Out, "! Tailscale is not installed")
		plan := p.Installation()
		fmt.Fprintln(ui.Out, plan.Guidance)
		if plan.Kind == "manual" || ui.NonInteractive {
			return 2
		}
		if !ui.Confirm(plan.Summary + "? [Y/n] ") {
			if ctx.Err() != nil {
				return failure(ctx.Err(), ui.Out)
			}
			fmt.Fprintln(ui.Out, "Installation declined. Run blaine connect when ready.")
			return 2
		}
		if err := p.Install(ctx, ui.In); err != nil {
			return failure(err, ui.Out)
		}
		n = p.Inspect(ctx)
	}
	if !n.WSL && (n.Code == "LOGIN_REQUIRED" || n.Code == "STOPPED") {
		if n.Code == "STOPPED" {
			fmt.Fprintln(ui.Out, "! Tailscale is disconnected")
		} else {
			fmt.Fprintln(ui.Out, "! Tailscale authentication required")
		}
		if ui.NonInteractive {
			fmt.Fprintln(ui.Out, "Run blaine connect interactively to sign in.")
			return 2
		}
		if !ui.Confirm("Connect Tailscale (browser/native login if needed)? [Y/n] ") {
			if ctx.Err() != nil {
				return failure(ctx.Err(), ui.Out)
			}
			fmt.Fprintln(ui.Out, "Authentication cancelled. Existing Tailscale state was preserved.")
			return 2
		}
		fmt.Fprintln(ui.Out, "Starting Tailscale authentication...")
		if err := p.Authenticate(ctx, ui.In, func(message string) { fmt.Fprintln(ui.Out, message) }); err != nil {
			return failure(err, ui.Out)
		}
		n = p.Inspect(ctx)
	}
	if ctx.Err() != nil {
		return failure(ctx.Err(), ui.Out)
	}
	if n.Ready {
		return ready(ui.Out)
	}
	fmt.Fprintf(ui.Out, "! %s\n%s\n", n.Code, n.Guidance)
	return 2
}
func ready(w io.Writer) int {
	fmt.Fprintln(w, "✓ Tailscale installed\n✓ Tailscale authenticated\n✓ Tailscale connected\n\nNetwork prerequisite ready.\nBlaine host connection will be configured in the next E0 stage.")
	return 0
}
func failure(err error, w io.Writer) int {
	if errors.Is(err, context.Canceled) {
		fmt.Fprintln(w, "Cancelled. Tailscale was not logged out; run blaine connect to check current state.")
		return 130
	}
	if errors.Is(err, context.DeadlineExceeded) {
		fmt.Fprintln(w, "Tailscale operation timed out. Run blaine doctor to check current state, then retry.")
		return 124
	}
	fmt.Fprintln(w, err.Error())
	return 2
}

type checkedWriter struct {
	writer io.Writer
	err    error
}

func (w *checkedWriter) Write(p []byte) (int, error) {
	if w.err != nil {
		return 0, w.err
	}
	n, err := w.writer.Write(p)
	if err == nil && n != len(p) {
		err = io.ErrShortWrite
	}
	w.err = err
	return n, err
}
