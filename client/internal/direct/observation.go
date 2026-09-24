package direct

import (
	"context"
	"errors"
	"io"
	"strings"
	"time"

	"github.com/coder/websocket"
)

// Observation contains only bounded transport metadata. Never include frame
// contents, authentication URLs, keys, headers, or raw dependency errors.
type Observation struct {
	Event       string `json:"event"`
	Stage       string `json:"stage"`
	Mode        string `json:"mode,omitempty"`
	SessionID   string `json:"session_id,omitempty"`
	PeerNode    string `json:"peer_node"`
	PayloadSize int    `json:"payload_bytes,omitempty"`
	ElapsedMS   int64  `json:"elapsed_ms"`
	Outcome     string `json:"outcome"`
}

func transportOutcome(err error) string {
	switch {
	case err == nil:
		return "OK"
	case errors.Is(err, context.DeadlineExceeded):
		return "DEADLINE"
	case errors.Is(err, context.Canceled):
		return "CANCELED"
	case errors.Is(err, io.EOF), errors.Is(err, io.ErrUnexpectedEOF):
		return "EOF"
	case websocket.CloseStatus(err) != -1:
		return "PEER_CLOSED"
	default:
		// Fixed codes only: the rest of an error may contain private context.
		for _, code := range []string{"PROTOCOL_INVALID", "PROBE_LIMIT", "INCOMPATIBLE", "CLIENT_IDENTITY_INVALID", "HOST_IDENTITY_INVALID", "DEPENDENCY_UNAVAILABLE"} {
			if strings.HasPrefix(err.Error(), code) {
				return code
			}
		}
		return "TRANSPORT_ERROR"
	}
}

func (h *Host) observe(start time.Time, peer Peer, mode, session, stage string, size int, err error) {
	if h.Observe == nil {
		return
	}
	h.Observe(Observation{Event: "private_session", Stage: stage, Mode: mode,
		SessionID: session, PeerNode: peer.NodeID, PayloadSize: size,
		ElapsedMS: time.Since(start).Milliseconds(), Outcome: transportOutcome(err)})
}
