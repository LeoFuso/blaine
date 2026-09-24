package direct

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"time"

	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/process"
	"blaine.local/client/internal/wire"
)

// ACP presents the standard agent-owned authentication method. It deliberately
// advertises no workstation capabilities. Registration grants no workspace capabilities.
func ACP(parent context.Context, root string, streams process.Streams) error {
	ctx, cancel := context.WithCancel(parent)
	defer cancel()
	stdio, e := borrowStdio(ctx, streams)
	if e != nil {
		return errors.New("LOCAL_INVALID: ACP stdio cannot be made interruptible")
	}
	defer stdio.Close()
	reader := bufio.NewReaderSize(stdio.In, wire.Limit+1)
	guard := wire.NewSession()
	var n *Network
	var session *Session
	var init json.RawMessage
	defer func() {
		if session != nil {
			session.Close()
		}
		if n != nil {
			n.Close()
		}
	}()
	connect := func(interactive bool) error {
		if session != nil {
			return nil
		}
		if !interactive {
			if _, e := os.Lstat(filepath.Join(root, "direct-v1", "node-id")); e != nil {
				return errors.New("AUTH_REQUIRED")
			}
		}
		var e error
		n, e = OpenNetwork(ctx, root, Deployment(), interactive, streams.Err)
		if e != nil {
			return e
		}
		session, _, e = n.Connect(ctx, "acp")
		if e != nil {
			n.Close()
			n = nil
			return e
		}
		initialized := false
		defer func() {
			if !initialized {
				session.Close()
				session = nil
				n.Close()
				n = nil
			}
		}()
		bounded, cancel := context.WithTimeout(ctx, 10*time.Second)
		defer cancel()
		// Initialize the existing host ACP adapter before handing it the IDE session.
		request := map[string]any{"jsonrpc": "2.0", "id": "blaine-private-initialize", "method": "initialize", "params": init}
		b, _ := json.Marshal(request)
		b = append(b, '\n')
		if e = session.Send(bounded, Data, b); e != nil {
			return e
		}
		kind, response, e := session.Receive(bounded)
		if e != nil || kind != Data {
			return errors.New("ACP_INVALID: remote initialization")
		}
		var result struct {
			JSONRPC string `json:"jsonrpc"`
			ID      string `json:"id"`
			Result  struct {
				Protocol     int             `json:"protocolVersion"`
				Capabilities json.RawMessage `json:"agentCapabilities"`
				Info         json.RawMessage `json:"agentInfo"`
				Auth         json.RawMessage `json:"authMethods"`
			} `json:"result"`
		}
		if wire.Decode(response, &result) != nil || result.JSONRPC != "2.0" || result.ID != "blaine-private-initialize" || result.Result.Protocol != 1 {
			return errors.New("INCOMPATIBLE: remote ACP initialization")
		}
		initialized = true
		return nil
	}
	for {
		line, e := reader.ReadSlice('\n')
		if e == io.EOF && len(line) == 0 {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			return nil
		}
		if e != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			return errors.New("ACP_INVALID: truncated/oversized input")
		}
		if e = guard.Validate(line, 0); e != nil {
			return e
		}
		var request struct {
			// Some Kotlin ACP serializers emit a class discriminator alongside
			// JSON-RPC. It carries no authority: dispatch/correlation still use
			// the method/id validated by the guard, never this auxiliary field.
			Type    string          `json:"type,omitempty"`
			JSONRPC string          `json:"jsonrpc"`
			ID      json.RawMessage `json:"id"`
			Method  string          `json:"method"`
			Params  json.RawMessage `json:"params"`
		}
		if e = wire.Decode(line, &request); e != nil {
			return e
		}
		if len(request.ID) == 0 {
			continue
		}
		var result any = map[string]any{}
		var fault any
		switch request.Method {
		case "initialize":
			if init != nil {
				return errors.New("ACP_INVALID: duplicate initialization")
			}
			var p map[string]json.RawMessage
			_ = json.Unmarshal(request.Params, &p)
			var version int
			if json.Unmarshal(p["protocolVersion"], &version) != nil || version != 1 {
				return errors.New("INCOMPATIBLE: ACP protocol")
			}
			p["clientCapabilities"] = json.RawMessage(`{}`)
			init, _ = json.Marshal(p)
			result = map[string]any{"protocolVersion": 1, "agentInfo": map[string]string{"name": "blaine", "version": buildinfo.Current().ClientVersion}, "agentCapabilities": map[string]any{}, "authMethods": []any{map[string]string{"id": "tailscale", "name": "Connect Blaine", "description": "Authenticate this Blaine installation to its private tailnet. An admitted installation is registered automatically."}}}
		case "authenticate":
			var p struct {
				Method string `json:"methodId"`
			}
			if init == nil || wire.Decode(request.Params, &p) != nil || p.Method != "tailscale" {
				fault = map[string]any{"code": -32602, "message": "Initialize first and select the Blaine authentication method"}
				break
			}
			if e = connect(true); e != nil {
				fault = map[string]any{"code": -32000, "message": e.Error()}
			}
		case "session/new":
			if init == nil {
				return errors.New("ACP_INVALID: initialize first")
			}
			if e = connect(false); e != nil {
				fault = map[string]any{"code": -32000, "message": e.Error()}
				break
			}
			// Reader may already contain the next request: preserve all buffered bytes.
			return relayClient(ctx, cancel, session, io.MultiReader(bytes.NewReader(append([]byte(nil), line...)), reader), stdio.Out)
		default:
			fault = map[string]any{"code": -32601, "message": "Method unavailable before the authenticated session"}
		}
		response := map[string]any{"jsonrpc": "2.0", "id": request.ID}
		if fault != nil {
			response["error"] = fault
		} else {
			response["result"] = result
		}
		data, _ := json.Marshal(response)
		data = append(data, '\n')
		if e = guard.Validate(data, 1); e != nil {
			return e
		}
		if _, e = stdio.Out.Write(data); e != nil {
			return e
		}
	}
}
