package connect

import (
	"bytes"
	"context"
	"errors"
	"os"
	"strings"
	"testing"

	"blaine.local/client/internal/platform"
)

type fake struct {
	states                 []platform.Network
	installs, auths, reads int
	installErr, authErr    error
	kind                   string
}

func (f *fake) Inspect(context.Context) platform.Network {
	i := f.reads
	f.reads++
	if i >= len(f.states) {
		i = len(f.states) - 1
	}
	return f.states[i]
}
func (f *fake) Installation() platform.InstallPlan {
	return platform.InstallPlan{Kind: f.kind, Summary: "Install Tailscale"}
}
func (f *fake) Install(context.Context, *os.File) error { f.installs++; return f.installErr }
func (f *fake) Authenticate(context.Context, *os.File, func(string)) error {
	f.auths++
	return f.authErr
}
func TestStateMachine(t *testing.T) {
	missing := platform.Network{Installed: "absent", Code: "INSTALL_REQUIRED"}
	login := platform.Network{Installed: "present", Auth: "required", Code: "LOGIN_REQUIRED"}
	readyState := platform.Network{Installed: "present", Auth: "authenticated", Ready: true}
	for _, tc := range []struct {
		name                    string
		states                  []platform.Network
		confirm, noninteractive bool
		installErr, authErr     error
		want, installs, auths   int
	}{
		{"already ready", []platform.Network{readyState}, true, false, nil, nil, 0, 0, 0},
		{"install login ready", []platform.Network{missing, login, readyState}, true, false, nil, nil, 0, 1, 1},
		{"install ready", []platform.Network{missing, readyState}, true, false, nil, nil, 0, 1, 0},
		{"install declined", []platform.Network{missing}, false, false, nil, nil, 2, 0, 0},
		{"installation failure", []platform.Network{missing}, true, false, errors.New("install failed"), nil, 2, 1, 0},
		{"auth required", []platform.Network{login, readyState}, true, false, nil, nil, 0, 0, 1},
		{"auth decline", []platform.Network{login}, false, false, nil, nil, 2, 0, 0},
		{"auth cancellation", []platform.Network{login}, true, false, nil, context.Canceled, 130, 0, 1},
		{"auth timeout", []platform.Network{login}, true, false, nil, context.DeadlineExceeded, 124, 0, 1},
		{"auth failure", []platform.Network{login}, true, false, nil, errors.New("login failed"), 2, 0, 1},
		{"successful exit is not readiness", []platform.Network{login, login}, true, false, nil, nil, 2, 0, 1},
		{"stopped reconnect", []platform.Network{{Installed: "present", Code: "STOPPED"}, readyState}, true, false, nil, nil, 0, 0, 1},
		{"daemon unavailable", []platform.Network{{Installed: "present", Code: "DAEMON_UNAVAILABLE"}}, true, false, nil, nil, 2, 0, 0},
		{"malformed", []platform.Network{{Installed: "present", Code: "MALFORMED_STATUS"}}, true, false, nil, nil, 2, 0, 0},
		{"windows unavailable", []platform.Network{{WSL: true, Installed: "unknown", Code: "WINDOWS_HOST_UNAVAILABLE"}}, true, false, nil, nil, 2, 0, 0},
		{"windows logged out", []platform.Network{{WSL: true, Installed: "present", Auth: "required", Code: "LOGIN_REQUIRED"}}, true, false, nil, nil, 2, 0, 0},
		{"native authorization", []platform.Network{{Installed: "app-present", Code: "NATIVE_AUTHORIZATION_REQUIRED"}}, true, false, nil, nil, 2, 0, 0},
		{"noninteractive missing", []platform.Network{missing}, true, true, nil, nil, 2, 0, 0},
		{"noninteractive login", []platform.Network{login}, true, true, nil, nil, 2, 0, 0},
	} {
		t.Run(tc.name, func(t *testing.T) {
			f := &fake{states: tc.states, kind: "apt", installErr: tc.installErr, authErr: tc.authErr}
			var out bytes.Buffer
			code := Run(context.Background(), f, UI{Out: &out, Confirm: func(string) bool { return tc.confirm }, NonInteractive: tc.noninteractive})
			if code != tc.want || f.installs != tc.installs || f.auths != tc.auths {
				t.Fatal(code, f, out.String())
			}
			if strings.Contains(out.String(), "Network prerequisite ready.") != (code == 0) {
				t.Fatal(out.String())
			}
		})
	}
}
func TestRepeatedReadyNeverMutates(t *testing.T) {
	f := &fake{states: []platform.Network{{Ready: true}}}
	for i := 0; i < 2; i++ {
		if Run(context.Background(), f, UI{Out: &bytes.Buffer{}, Confirm: func(string) bool { t.Fatal("prompt on ready"); return false }}) != 0 {
			t.Fatal("not ready")
		}
	}
	if f.installs+f.auths != 0 {
		t.Fatal(f)
	}
}

type failingWriter struct{}

func (failingWriter) Write([]byte) (int, error) { return 0, errors.New("closed output") }
func TestOutputFailure(t *testing.T) {
	f := &fake{states: []platform.Network{{Ready: true}}}
	if code := Run(context.Background(), f, UI{Out: failingWriter{}}); code != 1 {
		t.Fatal(code)
	}
}
