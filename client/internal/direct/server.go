package direct

import (
	"context"
	"crypto/ed25519"
	"errors"
	"net/http"
	"time"

	"blaine.local/client/internal/buildinfo"
	"github.com/coder/websocket"
)

// Host dependencies are injected by the host entrypoint, never by a request.
// Peer must derive from the accepted TCP socket, not forwarding headers/JSON.
type Host struct {
	Bootstrap Bootstrap
	Key       ed25519.PrivateKey
	Peer      func(context.Context, string) (Peer, error)
	Readiness func(context.Context) map[string]string
	ACP       func(context.Context, *Session) error
	Slots     chan struct{}
}

func ServerHandshake(ctx context.Context, c *websocket.Conn, h *Host, peer Peer) (*Session, Hello, error) {
	bounded, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	c.SetReadLimit(65536)
	var hello Hello
	if e := readControl(bounded, c, &hello); e != nil {
		return nil, hello, e
	}
	if e := validateHello(hello, h.Bootstrap); e != nil {
		return nil, hello, e
	}
	if Public(h.Key) != h.Bootstrap.ServerKey || keyID("hub-", h.Key.Public().(ed25519.PublicKey)) != h.Bootstrap.ServerID {
		return nil, hello, errors.New("HOST_IDENTITY_INVALID")
	}
	challenge := Challenge{Schema: 1, Protocol: 1, ServerID: h.Bootstrap.ServerID, Version: buildinfo.Current().ClientVersion, PublicKey: h.Bootstrap.ServerKey, SessionID: RandomID(), Nonce: RandomID(), Peer: peer, Readiness: h.Readiness(bounded), Registration: "not-implemented"}
	challenge.Signature = sign(h.Key, transcript(hello, challenge))
	if e := writeControl(bounded, c, challenge); e != nil {
		return nil, hello, e
	}
	// Even a modified client cannot bypass the host's dependency gate.
	for _, name := range []string{"runtime", "restate", "mirix", "generation", "embeddings"} {
		if challenge.Readiness[name] != "PASS" {
			return nil, hello, errors.New("DEPENDENCY_UNAVAILABLE")
		}
	}
	var proof Proof
	if e := readControl(bounded, c, &proof); e != nil {
		return nil, hello, e
	}
	key, _ := decodeKey(hello.PublicKey)
	if !verify(key, proofTranscript(hello, challenge), proof.Signature) {
		return nil, hello, errors.New("CLIENT_IDENTITY_INVALID")
	}
	if e := writeControl(bounded, c, Ready{challenge.SessionID, "CONNECTED"}); e != nil {
		return nil, hello, e
	}
	return NewSession(ctx, c, challenge.SessionID), hello, nil
}
func (h *Host) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" || r.URL.Path != "/v1/session" || r.URL.RawQuery != "" || r.Header.Get("Origin") != "" {
		http.Error(w, "request denied", 400)
		return
	}
	if h.Slots == nil {
		http.Error(w, "host not configured", 503)
		return
	}
	select {
	case h.Slots <- struct{}{}:
		defer func() { <-h.Slots }()
	default:
		http.Error(w, "session capacity", 503)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Minute)
	defer cancel()
	peer, e := h.Peer(ctx, r.RemoteAddr)
	if e != nil || peer.NodeID == "" || peer.PrincipalID == "" {
		http.Error(w, "peer denied", 403)
		return
	}
	c, e := websocket.Accept(w, r, &websocket.AcceptOptions{Subprotocols: []string{Subprotocol}, CompressionMode: websocket.CompressionDisabled})
	if e != nil {
		return
	}
	defer c.CloseNow()
	if c.Subprotocol() != Subprotocol {
		return
	}
	s, hello, e := ServerHandshake(ctx, c, h, peer)
	if e != nil {
		c.Close(websocket.StatusPolicyViolation, "Blaine handshake rejected")
		return
	}
	stop := context.AfterFunc(ctx, func() { c.CloseNow() })
	defer stop()
	if hello.Mode == "acp" {
		go func() {
			ticker := time.NewTicker(15 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-ctx.Done():
					return
				case <-ticker.C:
					bounded, stop := context.WithTimeout(ctx, 5*time.Second)
					current, err := h.Peer(bounded, r.RemoteAddr)
					if err == nil && current == peer {
						err = c.Ping(bounded)
					} else {
						err = errors.New("peer changed")
					}
					stop()
					if err != nil {
						cancel()
						return
					}
				}
			}
		}()
	}
	switch hello.Mode {
	case "handshake":
		_ = s.Send(ctx, Exit, []byte{0})
	case "probe":
		_ = serveProbe(ctx, s)
	case "acp":
		if h.ACP != nil {
			_ = h.ACP(ctx, s)
		}
	}
}

// Authenticated bounded diagnostic; no filesystem, model, workspace or Task.
// The same framing primitive carries ACP, while probe bytes span all 256 values.
func serveProbe(ctx context.Context, s *Session) error {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	if e := s.Send(ctx, Data, []byte{0, 1, 13, 10, 127, 128, 255}); e != nil {
		return e
	}
	total := 0
	for {
		kind, b, e := s.Receive(ctx)
		if e != nil {
			return e
		}
		switch kind {
		case Data:
			total += len(b)
			if total > 4<<20 {
				return errors.New("PROBE_LIMIT")
			}
			if e = s.Send(ctx, Data, b); e != nil {
				return e
			}
		case End:
			if len(b) != 0 {
				return errors.New("PROTOCOL_INVALID")
			}
			return s.Send(ctx, Exit, []byte{0})
		case Cancel:
			if len(b) != 0 {
				return errors.New("PROTOCOL_INVALID")
			}
			return s.Send(ctx, Exit, []byte{130})
		default:
			return errors.New("PROTOCOL_INVALID")
		}
	}
}
