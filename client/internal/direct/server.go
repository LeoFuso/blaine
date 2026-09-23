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
	Observe   func(Observation)
	// Register runs only after valid key proof. It returns a server-owned ID.
	Register   func(context.Context, Peer, Hello, string) (string, error)
	Touch      func(context.Context, string) error
	Disconnect func(context.Context, string) error
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
	if hello.Max >= 2 {
		challenge.Protocol = 2
		challenge.Registration = "automatic"
	}
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
	var workstation string
	if h.Register != nil {
		var err error
		workstation, err = h.Register(bounded, peer, hello, challenge.SessionID)
		if err != nil || !validWorkstationID(workstation) {
			return nil, hello, errors.New("REGISTRY_UNAVAILABLE")
		}
	} else if challenge.Protocol == 2 {
		return nil, hello, errors.New("REGISTRY_UNAVAILABLE")
	}
	ack := Ready{SessionID: challenge.SessionID, Status: "CONNECTED"}
	if challenge.Protocol == 2 {
		ack.WorkstationID = workstation
		ack.Signature = sign(h.Key, receiptTranscript(hello, challenge, ack))
	}
	if e := writeControl(bounded, c, ack); e != nil {
		h.disconnected(challenge.SessionID)
		return nil, hello, e
	}
	s := NewSession(ctx, c, challenge.SessionID)
	s.WorkstationID = workstation
	return s, hello, nil
}
func (h *Host) disconnected(id string) {
	if h.Disconnect != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = h.Disconnect(ctx, id)
	}
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
	start := time.Now()
	h.observe(start, peer, "", "", "handshake_start", 0, nil)
	s, hello, e := ServerHandshake(ctx, c, h, peer)
	if e != nil {
		h.observe(start, peer, "", "", "handshake_failed", 0, e)
		c.Close(websocket.StatusPolicyViolation, "Blaine handshake rejected")
		return
	}
	h.observe(start, peer, hello.Mode, s.ID, "handshake_complete", 0, nil)
	defer h.disconnected(s.ID)
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
					if err == nil && current.NodeID == peer.NodeID && current.PrincipalID == peer.PrincipalID {
						err = c.Ping(bounded)
					} else {
						err = errors.New("peer changed")
					}
					if err == nil && h.Touch != nil {
						err = h.Touch(bounded, s.ID)
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
		e = s.Send(ctx, Exit, []byte{0})
	case "probe":
		observationsLeft := 32
		e = serveProbeObserved(ctx, s, func(stage string, size int, err error) {
			if observationsLeft > 0 {
				observationsLeft--
				h.observe(start, peer, hello.Mode, s.ID, stage, size, err)
			}
		})
	case "acp":
		if h.ACP != nil {
			e = h.ACP(ctx, s)
		}
	}
	h.observe(start, peer, hello.Mode, s.ID, "session_finished", 0, e)
}

// Authenticated bounded diagnostic; no filesystem, model, workspace or Task.
// The same framing primitive carries ACP, while probe bytes span all 256 values.
func serveProbe(ctx context.Context, s *Session) error {
	return serveProbeObserved(ctx, s, func(string, int, error) {})
}
func serveProbeObserved(ctx context.Context, s *Session, observe func(string, int, error)) error {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	observe("probe_greeting_start", 7, nil)
	e := s.Send(ctx, Data, []byte{0, 1, 13, 10, 127, 128, 255})
	observe("probe_greeting_complete", 7, e)
	if e != nil {
		return e
	}
	total := 0
	for {
		observe("probe_receive_start", 0, nil)
		kind, b, e := s.Receive(ctx)
		observe("probe_receive_complete", len(b), e)
		if e != nil {
			return e
		}
		switch kind {
		case Data:
			total += len(b)
			if total > 4<<20 {
				return errors.New("PROBE_LIMIT")
			}
			observe("probe_echo_start", len(b), nil)
			e = s.Send(ctx, Data, b)
			observe("probe_echo_complete", len(b), e)
			if e != nil {
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
