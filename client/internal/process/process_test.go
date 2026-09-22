//go:build linux || darwin

package process

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

func TestHelperProcess(t *testing.T) {
	index := -1
	for i, arg := range os.Args {
		if arg == "--process-helper" {
			index = i + 1
			break
		}
	}
	if index < 0 {
		return
	}
	switch os.Args[index] {
	case "foreground-parent", "foreground-cancel":
		before, e := terminalGroup(os.Stdin)
		if e != nil {
			os.Exit(10)
		}
		child := helperSpec("tty-read")
		child.Foreground = true
		ctx := context.Background()
		if os.Args[index] == "foreground-cancel" {
			var cancel context.CancelFunc
			ctx, cancel = context.WithTimeout(ctx, 100*time.Millisecond)
			defer cancel()
			child = helperSpec("stubborn")
			child.Foreground = true
		}
		data, code, err := Capture(ctx, child, os.Stdin, nil)
		after, e := terminalGroup(os.Stdin)
		success := err == nil && code == 0 && string(data) == "accepted\n"
		if os.Args[index] == "foreground-cancel" {
			success = ctx.Err() == context.DeadlineExceeded && code == 130
		}
		if !success || e != nil || before != after {
			fmt.Println("FAIL", code, err, before, after, string(data))
			os.Exit(11)
		}
		fmt.Println("FOREGROUND_PASS")
		os.Exit(0)
	case "tty-read":
		tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
		if err != nil {
			os.Exit(12)
		}
		fmt.Fprintln(tty, "TTY_PROMPT")
		b := make([]byte, 64)
		n, err := tty.Read(b)
		if err != nil || string(b[:n]) != "fixture-answer\n" {
			os.Exit(13)
		}
		fmt.Println("accepted")
		os.Exit(0)
	case "echo":
		fmt.Fprintln(os.Stderr, "helper diagnostic")
		_, err := io.Copy(os.Stdout, os.Stdin)
		if err != nil {
			os.Exit(1)
		}
		os.Exit(0)
	case "exit":
		os.Exit(23)
	case "signal":
		syscall.Kill(os.Getpid(), syscall.SIGKILL)
	case "environment":
		fmt.Println(os.Getenv("BLAINE_TEST_CHILD_MODE"))
		os.Exit(0)
	case "argv":
		for _, arg := range os.Args[index+1:] {
			fmt.Fprintln(os.Stdout, arg)
		}
		os.Exit(0)
	case "tree", "tree-exit":
		child := exec.Command(os.Args[0], "-test.run=TestHelperProcess", "--", "--process-helper", "stubborn")
		if err := child.Start(); err != nil {
			os.Exit(9)
		}
		if err := os.WriteFile(os.Args[index+1], []byte(fmt.Sprintf("%d %d", os.Getpid(), child.Process.Pid)), 0600); err != nil {
			os.Exit(9)
		}
		if os.Args[index] == "tree-exit" {
			os.Exit(0)
		}
		_ = child.Wait()
		os.Exit(0)
	case "stubborn":
		signal.Ignore(syscall.SIGTERM, syscall.SIGINT)
		time.Sleep(30 * time.Second)
		os.Exit(0)
	}
	os.Exit(9)
}
func helperSpec(mode string, args ...string) Spec {
	return Spec{Executable: os.Args[0], Args: append([]string{"-test.run=TestHelperProcess", "--", "--process-helper", mode}, args...)}
}
func files(t *testing.T, data []byte) Streams {
	t.Helper()
	root := t.TempDir()
	open := func(name string) *os.File {
		f, err := os.Create(filepath.Join(root, name))
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { f.Close() })
		return f
	}
	s := Streams{open("stdin"), open("stdout"), open("stderr")}
	if _, err := s.In.Write(data); err != nil {
		t.Fatal(err)
	}
	s.In.Seek(0, 0)
	return s
}
func contents(t *testing.T, f *os.File) []byte {
	t.Helper()
	b, err := os.ReadFile(f.Name())
	if err != nil {
		t.Fatal(err)
	}
	return b
}
func TestBytePurityAndStderr(t *testing.T) {
	data := bytes.Repeat([]byte("{\"jsonrpc\":\"2.0\"}\r\n\x00\xffλ"), 10000)
	s := files(t, data)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	code, err := Run(ctx, helperSpec("echo"), s)
	if err != nil || code != 0 || !bytes.Equal(contents(t, s.Out), data) {
		t.Fatalf("%d %v: protocol mutation", code, err)
	}
	if string(contents(t, s.Err)) != "helper diagnostic\n" {
		t.Fatal("stderr not isolated")
	}
}
func TestStatusAndArgv(t *testing.T) {
	for _, tc := range []struct {
		mode string
		code int
	}{{"exit", 23}, {"signal", 137}} {
		s := files(t, nil)
		code, err := Run(context.Background(), helperSpec(tc.mode), s)
		if code != tc.code || err != nil {
			t.Fatalf("%s: %d %v", tc.mode, code, err)
		}
	}
	args := []string{"space in arg", "$(touch should-not-exist)", "; echo bad", "C:\\Users\\A B\\λ", "--literal"}
	s := files(t, nil)
	if code, err := Run(context.Background(), helperSpec("argv", args...), s); code != 0 || err != nil {
		t.Fatal(code, err)
	}
	if string(contents(t, s.Out)) != strings.Join(args, "\n")+"\n" {
		t.Fatal("argv mutation")
	}
}
func TestEarlyExitWithOpenStdin(t *testing.T) {
	s := files(t, nil)
	read, write, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer read.Close()
	defer write.Close()
	s.In = read
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if code, err := Run(ctx, helperSpec("exit"), s); code != 23 || err != nil {
		t.Fatal(code, err)
	}
}
func TestStartFailureAndPreCancelled(t *testing.T) {
	s := files(t, nil)
	for _, spec := range []Spec{{Executable: "relative"}, {Executable: "/nonexistent/blaine-fixture"}} {
		if code, err := Run(context.Background(), spec, s); code != 1 || err == nil {
			t.Fatal(code, err)
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if code, err := Run(ctx, helperSpec("echo"), s); code != 130 || err == nil {
		t.Fatal(code, err)
	}
}
func TestCancellationAndDescendantCleanup(t *testing.T) {
	for _, mode := range []string{"tree", "tree-exit"} {
		t.Run(mode, func(t *testing.T) {
			s := files(t, nil)
			pidFile := filepath.Join(t.TempDir(), "pids")
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			done := make(chan int, 1)
			go func() { code, _ := Run(ctx, helperSpec(mode, pidFile), s); done <- code }()
			var pids []int
			deadline := time.Now().Add(3 * time.Second)
			for time.Now().Before(deadline) {
				raw, _ := os.ReadFile(pidFile)
				fields := strings.Fields(string(raw))
				if len(fields) == 2 {
					for _, f := range fields {
						pid, _ := strconv.Atoi(f)
						pids = append(pids, pid)
					}
					break
				}
				time.Sleep(5 * time.Millisecond)
			}
			if len(pids) != 2 {
				cancel()
				t.Fatal("helper did not become ready")
			}
			t.Cleanup(func() {
				for _, pid := range pids {
					syscall.Kill(pid, syscall.SIGKILL)
				}
			})
			if mode == "tree" {
				cancel()
			}
			select {
			case code := <-done:
				if mode == "tree" && code != 130 {
					t.Fatal(code)
				}
			case <-time.After(3 * time.Second):
				t.Fatal("process wait leaked")
			}
			for _, pid := range pids {
				deadline = time.Now().Add(2 * time.Second)
				for processLive(pid) && time.Now().Before(deadline) {
					time.Sleep(5 * time.Millisecond)
				}
				if processLive(pid) {
					t.Fatalf("live descendant %d remains", pid)
				}
			}
		})
	}
}
func processLive(pid int) bool {
	if err := syscall.Kill(pid, 0); err == syscall.ESRCH {
		return false
	}
	// Linux init/container reaping is external to the proxy. A zombie is terminated,
	// cannot execute or retain protocol descriptors, and is not a surviving helper.
	raw, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err == nil {
		end := strings.LastIndex(string(raw), ")")
		return !strings.HasPrefix(string(raw)[end+1:], " Z")
	}
	// macOS has no procfs; ps is only a test observation, never a client dependency.
	raw, err = exec.Command("ps", "-o", "stat=", "-p", strconv.Itoa(pid)).Output()
	return err == nil && !strings.HasPrefix(strings.TrimSpace(string(raw)), "Z")
}

func TestCancellationWithBlockedStreams(t *testing.T) {
	for _, mode := range []string{"input", "output"} {
		t.Run(mode, func(t *testing.T) {
			data := []byte(nil)
			if mode == "output" {
				data = bytes.Repeat([]byte("x"), 1<<20)
			}
			s := files(t, data)
			read, write, err := os.Pipe()
			if err != nil {
				t.Fatal(err)
			}
			defer read.Close()
			defer write.Close()
			if mode == "input" {
				s.In = read
			} else {
				s.Out = write
			}
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			done := make(chan int, 1)
			go func() { code, _ := Run(ctx, helperSpec("echo"), s); done <- code }()
			// Wait for the child diagnostic, emitted before entering the blocking copy.
			deadline := time.Now().Add(3 * time.Second)
			for len(contents(t, s.Err)) == 0 && time.Now().Before(deadline) {
				time.Sleep(5 * time.Millisecond)
			}
			if len(contents(t, s.Err)) == 0 {
				t.Fatal("helper did not become ready")
			}
			cancel()
			select {
			case code := <-done:
				if code != 130 {
					t.Fatal(code)
				}
			case <-time.After(3 * time.Second):
				t.Fatal("blocked stream prevented cancellation")
			}
		})
	}
}
