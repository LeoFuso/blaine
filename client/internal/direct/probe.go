package direct

import (
	"blaine.local/client/internal/wire"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"time"
)

// VerifyTransport is opt-in, bounded and effect-free. It exercises the production
// authentication/framing path but cannot grant or test workspace capabilities.
func VerifyTransport(parent context.Context, n *Network) (map[string]any, error) {
	ctx, cancel := context.WithTimeout(parent, 45*time.Second)
	defer cancel()
	result := map[string]any{"scope": "E0.C private transport; no registration or workspace effects"}
	s, hello, e := n.Connect(ctx, "probe")
	if e != nil {
		return result, e
	}
	defer s.Close()
	kind, data, e := s.Receive(ctx)
	if e != nil || kind != Data || !bytes.Equal(data, []byte{0, 1, 13, 10, 127, 128, 255}) {
		return result, errors.New("PROBE_FAILED: server-initiated binary data")
	}
	payload := make([]byte, 1<<20)
	for i := range payload {
		payload[i] = byte(i)
	}
	if e = s.Send(ctx, Data, payload); e != nil {
		return result, e
	}
	kind, data, e = s.Receive(ctx)
	if e != nil || kind != Data || !bytes.Equal(data, payload) {
		return result, errors.New("PROBE_FAILED: byte mismatch")
	}
	digest := sha256.Sum256(data)
	result["binary_bytes"] = len(data)
	result["binary_sha256"] = hex.EncodeToString(digest[:])
	result["bidirectional"] = true
	if e = s.Send(ctx, Cancel, nil); e != nil {
		return result, e
	}
	kind, data, e = s.Receive(ctx)
	if e != nil || kind != Exit || !bytes.Equal(data, []byte{130}) {
		return result, errors.New("PROBE_FAILED: cancellation acknowledgement")
	}
	result["cancellation"] = true
	if _, _, e = s.Receive(ctx); e == nil {
		return result, errors.New("PROBE_FAILED: remote disconnect")
	}
	result["remote_disconnect"] = true
	again, challenge, e := n.Connect(ctx, "probe")
	if e != nil {
		return result, e
	}
	defer again.Close()
	if challenge.SessionID == hello.SessionID {
		return result, errors.New("PROBE_FAILED: session reuse")
	}
	kind, _, e = again.Receive(ctx)
	if e != nil || kind != Data {
		return result, errors.New("PROBE_FAILED: reconnect")
	}
	result["reconnect"] = true
	deadline, stop := context.WithTimeout(ctx, 50*time.Millisecond)
	_, _, e = again.Receive(deadline)
	stop()
	if e == nil || deadline.Err() == nil {
		return result, errors.New("PROBE_FAILED: read deadline")
	}
	result["deadline"] = true
	acp, _, e := n.Connect(ctx, "acp")
	if e != nil {
		return result, e
	}
	defer acp.Close()
	requests := []string{
		`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{"fs":{"readTextFile":true}}}}`,
		`{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/e0c-no-workspace-access","mcpServers":[]}}`,
	}
	guard := wire.NewSession()
	for index, request := range requests {
		line := []byte(request + "\n")
		if e = guard.Validate(line, 0); e != nil {
			return result, e
		}
		if e = acp.Send(ctx, Data, line); e != nil {
			return result, e
		}
		kind, response, e := acp.Receive(ctx)
		if e != nil || kind != Data {
			return result, errors.New("PROBE_FAILED: live ACP response")
		}
		if e = guard.Validate(response, 1); e != nil {
			return result, e
		}
		var r map[string]json.RawMessage
		if json.Unmarshal(response, &r) != nil || r["error"] != nil {
			return result, errors.New("PROBE_FAILED: ACP initialization/session")
		}
		var body struct {
			Protocol int    `json:"protocolVersion"`
			Session  string `json:"sessionId"`
		}
		if json.Unmarshal(r["result"], &body) != nil || (index == 0 && body.Protocol != 1) || (index == 1 && body.Session == "") {
			return result, errors.New("PROBE_FAILED: incomplete ACP result")
		}

	}
	if e = acp.Send(ctx, End, nil); e != nil {
		return result, e
	}
	kind, data, e = acp.Receive(ctx)
	if e != nil || kind != Exit || !bytes.Equal(data, []byte{0}) {
		return result, errors.New("PROBE_FAILED: ACP exit")
	}
	result["remote_acp_session"] = true
	result["acp_clean_exit"] = true
	result["status"] = "PASS"
	return result, nil
}
