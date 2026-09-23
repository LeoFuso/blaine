package direct

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"testing"
	"time"
)

func TestTransportObservationRedactsErrors(t *testing.T) {
	for _, tc := range []struct {
		err  error
		want string
	}{
		{nil, "OK"},
		{fmt.Errorf("private-fixture-detail: %w", context.DeadlineExceeded), "DEADLINE"},
		{context.Canceled, "CANCELED"},
		{errors.New("PROTOCOL_INVALID: private-fixture-detail"), "PROTOCOL_INVALID"},
		{errors.New("private-fixture-detail"), "TRANSPORT_ERROR"},
	} {
		if got := transportOutcome(tc.err); got != tc.want {
			t.Fatal(got, tc.want)
		}
	}
}

func TestProbeReportsStagesWithoutPayload(t *testing.T) {
	h, url, key := testHost(t)
	events := make(chan Observation, 64)
	h.Observe = func(event Observation) { events <- event }
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "probe")
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	if _, _, e = s.Receive(ctx); e != nil {
		t.Fatal(e)
	}
	payload := []byte("private-fixture-payload")
	if e = s.Send(ctx, Data, payload); e != nil {
		t.Fatal(e)
	}
	if kind, b, e := s.Receive(ctx); e != nil || kind != Data || !bytes.Equal(b, payload) {
		t.Fatal(kind, e)
	}
	if e = s.Send(ctx, Cancel, nil); e != nil {
		t.Fatal(e)
	}
	if kind, _, e := s.Receive(ctx); e != nil || kind != Exit {
		t.Fatal(kind, e)
	}
	stages := map[string]Observation{}
	for {
		select {
		case event := <-events:
			encoded, _ := json.Marshal(event)
			if strings.Contains(string(encoded), string(payload)) {
				t.Fatal("payload in diagnostics")
			}
			stages[event.Stage] = event
			if event.Stage == "session_finished" {
				for _, name := range []string{"handshake_start", "handshake_complete", "probe_greeting_complete", "probe_receive_start", "probe_echo_start", "probe_echo_complete"} {
					if stages[name].Stage != name || stages[name].Outcome != "OK" {
						t.Fatal("missing stage", name)
					}
				}
				if stages["probe_echo_complete"].PayloadSize != len(payload) {
					t.Fatal("incorrect byte count")
				}
				return
			}
		case <-ctx.Done():
			t.Fatal("missing terminal observation")
		}
	}
}
