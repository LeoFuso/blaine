package direct

import (
	"errors"
	"net"
	"os"
	"os/exec"
	"testing"

	"tailscale.com/net/tstun"
)

func TestMTUOnlyChangesMeasuredWSLRoute(t *testing.T) {
	for _, tc := range []struct {
		kind     string
		wire     int
		override string
		want     int
		writes   int
	}{
		{"wsl", 1280, "", 1200, 1}, {"wsl", 1500, "", 1280, 0},
		{"linux", 1280, "", 1280, 0}, {"darwin", 1280, "", 1280, 0},
		{"wsl", 1280, "1200", 1200, 0},
	} {
		calls, writes := 0, 0
		result, e := configureNetworkMTU(tc.kind, func() (*net.Interface, error) {
			calls++
			return &net.Interface{Name: "fixture-route", MTU: tc.wire, Flags: net.FlagUp}, nil
		}, func(string) string { return tc.override }, func(name, value string) error {
			if name != "TS_DEBUG_MTU" || value != "1200" {
				t.Fatal(name, value)
			}
			writes++
			return nil
		})
		if e != nil || result.Value != tc.want || writes != tc.writes {
			t.Fatal(tc, result, e, writes)
		}
		if (tc.kind != "wsl" || tc.override != "") && calls != 0 {
			t.Fatal("unnecessary route inspection")
		}
	}
}

func TestMTUInspectionAndOverrideFailClosed(t *testing.T) {
	for _, raw := range []string{"invalid", "-1", "0", "1199", "1281"} {
		_, e := configureNetworkMTU("wsl", nil, func(string) string { return raw }, nil)
		if e == nil {
			t.Fatal("accepted unsupported diagnostic override")
		}
	}
	for _, iface := range []*net.Interface{nil, {MTU: 1280}, {MTU: 1280, Flags: net.FlagUp | net.FlagLoopback}, {MTU: 0, Flags: net.FlagUp}} {
		_, e := configureNetworkMTU("wsl", func() (*net.Interface, error) { return iface, nil }, func(string) string { return "" }, nil)
		if e == nil {
			t.Fatal("accepted unknown/down interface")
		}
	}
	_, e := configureNetworkMTU("wsl", func() (*net.Interface, error) { return nil, errors.New("fixture failure") }, func(string) string { return "" }, nil)
	if e == nil {
		t.Fatal("ignored route failure")
	}
}

// Exercise the pinned SDK lookup in an isolated process: Go test peers may use
// other netstack defaults concurrently. No network, TUN or node is created.
func TestPinnedSDKConsumesAutomaticMTU(t *testing.T) {
	if os.Getenv("BLAINE_MTU_FIXTURE") == "1" {
		os.Unsetenv("TS_DEBUG_MTU")
		result, e := configureNetworkMTU("wsl", func() (*net.Interface, error) { return &net.Interface{MTU: 1280, Flags: net.FlagUp}, nil }, os.Getenv, os.Setenv)
		if e != nil || result.Source != "wsl-default-route" || tstun.DefaultTUNMTU() != 1200 {
			t.Fatal(result, e)
		}
		return
	}
	cmd := exec.Command(os.Args[0], "-test.run=^TestPinnedSDKConsumesAutomaticMTU$")
	cmd.Env = append(os.Environ(), "BLAINE_MTU_FIXTURE=1")
	if output, e := cmd.CombinedOutput(); e != nil {
		t.Fatal(e, string(output))
	}
}
