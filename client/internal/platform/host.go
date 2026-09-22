package platform

import (
	"context"
	"encoding/json"
	"errors"
	"regexp"
	"strings"

	"blaine.local/client/internal/wire"
)

var dnsName = regexp.MustCompile(`^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$`)

// HostName qualifies an explicit short name from native tailnet metadata, never
// peer enumeration or an OS search suffix (which may resolve to local hosts).
func (t *Tailscale) HostName(ctx context.Context, name string) (string, error) {
	name = strings.ToLower(strings.TrimSuffix(name, "."))
	if !dnsName.MatchString(name) || len(name) > 253 {
		return "", errors.New("LOCAL_INVALID: invalid MagicDNS host name")
	}
	if strings.Contains(name, ".") {
		return name, nil
	}
	cli := t.cli()
	if cli == "" {
		return "", errors.New("REMOTE_UNAVAILABLE: native Tailscale DNS metadata unavailable")
	}
	data, code, e := t.command(ctx, cli, "status", "--json")
	if e != nil || code != 0 {
		return "", errors.New("REMOTE_UNAVAILABLE: native Tailscale DNS metadata unavailable")
	}
	return QualifyHost(name, data)
}
func QualifyHost(name string, data []byte) (string, error) {
	var raw map[string]json.RawMessage
	if wire.Decode(data, &raw) != nil {
		return "", errors.New("REMOTE_UNAVAILABLE: invalid native Tailscale DNS metadata")
	}
	var tailnet struct{ MagicDNSSuffix string }
	if json.Unmarshal(raw["CurrentTailnet"], &tailnet) != nil {
		return "", errors.New("REMOTE_UNAVAILABLE: native MagicDNS suffix unavailable")
	}
	suffix := strings.ToLower(strings.TrimSuffix(tailnet.MagicDNSSuffix, "."))
	host := name + "." + suffix
	if !strings.Contains(suffix, ".") || !dnsName.MatchString(host) || len(host) > 253 {
		return "", errors.New("REMOTE_UNAVAILABLE: native MagicDNS suffix invalid")
	}
	return host, nil
}
