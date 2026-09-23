package wire

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"strconv"
	"sync"
)

// Session tracks JSON-RPC correlation only, never durable Task state.
type Session struct {
	mu      sync.Mutex
	pending [2]map[string]bool
}

func NewSession() *Session { return &Session{pending: [2]map[string]bool{{}, {}}} }
func (s *Session) Pending() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.pending[0]) + len(s.pending[1])
}
func (s *Session) Validate(data []byte, from int) error {
	if from != 0 && from != 1 {
		return errors.New("ACP_INVALID: invalid direction")
	}
	var m map[string]json.RawMessage
	if e := Decode(data, &m); e != nil {
		return errors.New("ACP_INVALID: malformed JSON-RPC frame")
	}
	var version, method string
	if json.Unmarshal(m["jsonrpc"], &version) != nil || version != "2.0" {
		return errors.New("ACP_INVALID: expected JSON-RPC 2.0")
	}
	id, hasID := m["id"]
	_, hasMethod := m["method"]
	_, result := m["result"]
	_, failure := m["error"]
	var key string
	if hasID {
		var v any
		d := json.NewDecoder(bytes.NewReader(id))
		d.UseNumber()
		if d.Decode(&v) != nil {
			return errors.New("ACP_INVALID: invalid id")
		}
		switch v.(type) {
		case string:
			b, _ := json.Marshal(v)
			key = string(b)
		case json.Number:
			n, e := strconv.ParseInt(string(v.(json.Number)), 10, 64)
			if e != nil {
				return errors.New("ACP_INVALID: id must be a string or integer")
			}
			key = strconv.FormatInt(n, 10)
		default:
			return errors.New("ACP_INVALID: invalid id")
		}
	}
	if hasMethod {
		if json.Unmarshal(m["method"], &method) != nil || method == "" || result || failure {
			return errors.New("ACP_INVALID: invalid request")
		}
		if p, ok := m["params"]; ok {
			var params map[string]json.RawMessage
			if json.Unmarshal(p, &params) != nil || params == nil {
				return errors.New("ACP_INVALID: parameters must be an object")
			}
		}
		// E0 grants no client capabilities. Only passive session updates may flow
		// from host to IDE; future effects need E1's separately authorized guard.
		if from == 1 && (hasID || method != "session/update") {
			return errors.New("ACP_DENIED: host client capabilities require a later E slice")
		}
		if from == 0 && (method == "initialize" || method == "session/new" || method == "session/load") {
			var params map[string]json.RawMessage
			if json.Unmarshal(m["params"], &params) != nil || params == nil {
				return errors.New("ACP_INVALID: missing parameters")
			}
			if raw, ok := params["mcpServers"]; ok {
				var servers []any
				if json.Unmarshal(raw, &servers) != nil || len(servers) > 0 {
					return errors.New("ACP_DENIED: MCP forwarding is disabled")
				}
			}
		}
	} else if !hasID || result == failure {
		return errors.New("ACP_INVALID: invalid response")
	}
	if failure {
		var errBody struct {
			Code    int             `json:"code"`
			Message string          `json:"message"`
			Data    json.RawMessage `json:"data"`
		}
		if Decode(m["error"], &errBody) != nil || errBody.Message == "" {
			return errors.New("ACP_INVALID: malformed RPC error")
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if hasMethod && hasID {
		if len(s.pending[from]) >= 1024 || s.pending[from][key] {
			return errors.New("ACP_INVALID: duplicate or excessive pending requests")
		}
		s.pending[from][key] = true
	}
	if !hasMethod {
		if !s.pending[1-from][key] {
			return errors.New("ACP_INVALID: unmatched response")
		}
		delete(s.pending[1-from], key)
	}
	return nil
}
func (s *Session) Forward(r io.Reader, w io.Writer, from int) error {
	reader := bufio.NewReaderSize(r, Limit+1)
	for {
		line, e := reader.ReadSlice('\n')
		if e == io.EOF && len(line) == 0 {
			return nil
		}
		if e != nil {
			if errors.Is(e, os.ErrClosed) {
				return e
			}
			return errors.New("ACP_INVALID: truncated or oversized frame")
		}
		if e = s.Validate(line, from); e != nil {
			return e
		}
		// Strip capabilities before initialization reaches the existing D2 server.
		// All other validated frames retain their original bytes and request IDs.
		var m map[string]json.RawMessage
		_ = json.Unmarshal(line, &m)
		var method string
		_ = json.Unmarshal(m["method"], &method)
		if from == 0 && method == "initialize" {
			var p map[string]json.RawMessage
			_ = json.Unmarshal(m["params"], &p)
			p["clientCapabilities"] = json.RawMessage(`{}`)
			m["params"], _ = json.Marshal(p)
			line, _ = json.Marshal(m)
			line = append(line, '\n')
		}
		if n, e := w.Write(line); e != nil {
			return e
		} else if n != len(line) {
			return io.ErrShortWrite
		}
	}
}
