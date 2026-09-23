package direct

import (
	"errors"
	"net"
	"os"
	"strconv"

	"blaine.local/client/internal/platform"
	"tailscale.com/net/netmon"
)

type networkMTU struct {
	Value  int
	Source string
}

func prepareNetworkMTU() (networkMTU, error) {
	p, e := platform.Current()
	if e != nil {
		return networkMTU{}, e
	}
	return configureNetworkMTU(p.Kind, func() (*net.Interface, error) {
		name, e := netmon.DefaultRouteInterface()
		if e != nil {
			return nil, e
		}
		return net.InterfaceByName(name)
	}, os.Getenv, os.Setenv)
}

// tsnet v1.102.4 has no per-Server MTU field. Its netstack uses
// tstun.DefaultTUNMTU, which reads TS_DEBUG_MTU with os.Getenv at startup (not a
// registered cached knob). Keep this pinned-SDK compatibility bridge here, before
// Server.Start. One CLI process owns one embedded installation. It never edits an
// OS interface, route, persisted credential or machine-wide environment.
// Revisit this bridge on SDK upgrades. Native IPv6-only paths below 1280 remain
// outside measured acceptance; this handles the designated WSL -> IPv4 Hub path.
func configureNetworkMTU(kind string, route func() (*net.Interface, error), getenv func(string) string, setenv func(string, string) error) (networkMTU, error) {
	result := networkMTU{1280, "tsnet-default"}
	if raw := getenv("TS_DEBUG_MTU"); raw != "" {
		n, e := strconv.Atoi(raw)
		if e != nil || n < 1200 || n > 1280 {
			return result, errors.New("LOCAL_INVALID: diagnostic MTU must be between 1200 and 1280")
		}
		return networkMTU{n, "diagnostic-override"}, nil
	}
	if kind != "wsl" {
		return result, nil
	}
	iface, e := route()
	if e != nil || iface == nil || iface.MTU <= 0 || iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
		return result, errors.New("NETWORK_UNAVAILABLE: WSL default-route MTU cannot be inspected")
	}
	if iface.MTU != 1280 {
		return result, nil
	}
	// 1200 + the upstream worst-case 80-byte WireGuard envelope fits the
	// measured WSL interface. TCP still carries the full 1 MiB application frame.
	if e = setenv("TS_DEBUG_MTU", "1200"); e != nil {
		return result, errors.New("LOCAL_INVALID: embedded MTU configuration unavailable")
	}
	return networkMTU{1200, "wsl-default-route"}, nil
}
