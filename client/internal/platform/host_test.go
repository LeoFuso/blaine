package platform

import "testing"

func TestMagicDNSQualification(t *testing.T) {
	name, e := QualifyHost("blaine", []byte(`{"CurrentTailnet":{"MagicDNSSuffix":"tail-example.ts.net"},"Peer":{"unrelated":"ignored"}}`))
	if e != nil || name != "blaine.tail-example.ts.net" {
		t.Fatal(name, e)
	}
	for _, data := range []string{`{}`, `{"CurrentTailnet":{"MagicDNSSuffix":"localhost"}}`, `{"CurrentTailnet":{"MagicDNSSuffix":"evil;command"}}`, `{"CurrentTailnet":{"MagicDNSSuffix":"one.ts.net","MagicDNSSuffix":"two.ts.net"}}`} {
		if _, e := QualifyHost("blaine", []byte(data)); e == nil {
			t.Fatal("accepted invalid metadata")
		}
	}
}
