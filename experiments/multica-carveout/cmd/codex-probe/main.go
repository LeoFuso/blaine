// codex-probe exercises Multica's public API. It is not a Blaine runtime adapter.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/multica-ai/multica/server/pkg/agent"
)

// Only the probe's private home receives this configuration. In particular,
// never point Config.Env["CODEX_HOME"] at the user's real Codex home: Multica
// can rewrite config.toml there, even when McpConfig is nil.
const probeConfig = `approval_policy = "never"
sandbox_mode = "read-only"
cli_auth_credentials_store = "file"
web_search = "disabled"

[features]
shell_tool = false
apps = false
plugins = false
multi_agent = false
browser_use = false
computer_use = false
image_generation = false
`

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "probe:", err)
		os.Exit(1)
	}
}

func run() error {
	binary := flag.String("codex", "codex", "existing Codex executable (name on PATH or full path)")
	model := flag.String("model", "", "optional model override; empty uses Codex's default")
	resume := flag.String("resume", "", "session ID returned by a previous invocation")
	stateDir := flag.String("state-dir", "", "private directory printed by the previous invocation (required with -resume)")
	prompt := flag.String("prompt", "", "optional harmless prompt; defaults to a two-turn memory check")
	budget := flag.Duration("timeout", 2*time.Minute, "total execution deadline, excluding process cleanup")
	flag.Parse()
	if flag.NArg() != 0 || *budget <= 0 {
		return errors.New("use named flags and a positive -timeout")
	}
	if (*resume == "") != (*stateDir == "") {
		return errors.New("-resume and -state-dir must be supplied together")
	}
	executable, err := exec.LookPath(*binary)
	if err != nil {
		return fmt.Errorf("locate Codex: %w", err)
	}
	executable, err = filepath.Abs(executable)
	if err != nil {
		return err
	}
	root, err := prepareState(*stateDir)
	if err != nil {
		return err
	}
	probeHome, workDir := filepath.Join(root, "codex-home"), filepath.Join(root, "work")
	cleanupAuth, err := copyAuth(probeHome)
	if err != nil {
		return err
	}
	defer cleanupAuth()

	interruptCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	ctx, cancel := context.WithTimeout(interruptCtx, *budget)
	defer cancel()
	versionCmd := exec.CommandContext(ctx, executable, "--version")
	versionCmd.Dir = workDir
	versionCmd.Env = append(os.Environ(), "CODEX_HOME="+probeHome)
	versionOutput, err := versionCmd.Output()
	if err != nil {
		return fmt.Errorf("Codex version: %w", err)
	}
	version := strings.TrimSpace(string(versionOutput))
	backend, err := agent.New("codex", agent.Config{
		ExecutablePath: executable,
		Env:            map[string]string{"CODEX_HOME": probeHome},
		Logger:         slog.New(slog.NewJSONHandler(os.Stderr, nil)),
		CLIVersion:     version,
		CodexVersion:   version,
		BuiltinRuntime: true,
	})
	if err != nil {
		return err
	}
	if *prompt == "" {
		*prompt = "Remember this marker for our next turn: CARVEOUT-7c91. Reply only PROBE_OK."
		if *resume != "" {
			*prompt = "What marker did I ask you to remember in the previous turn? Reply with only that marker, or UNKNOWN if unavailable."
		}
	}
	boundedPrompt := "This is a connectivity probe. Do not use tools, run commands, read or write files, browse, or delegate. " + *prompt
	encoder := json.NewEncoder(os.Stdout)
	if err := encoder.Encode(map[string]any{
		"kind": "setup", "executable": executable, "codex_version": version,
		"state_dir": root, "cwd": workDir, "requested_session_id": *resume, "model": *model,
	}); err != nil {
		return err
	}
	session, err := backend.Execute(ctx, boundedPrompt, agent.ExecOptions{
		Cwd:                    workDir,
		Model:                  *model,
		Timeout:                *budget,
		ResumeSessionID:        *resume,
		ResumeExpected:         *resume != "",
		ResumeContinuityNotice: "The requested prior session could not be restored. Do not claim to remember its contents.\n\n",
	})
	if err != nil {
		return fmt.Errorf("Execute: %w", err)
	}
	// Drain BOTH channels. The outer Codex wrapper uses blocking sends for
	// messages, so treating the transcript as optional can stall a verbose run.
	var result agent.Result
	var resultCount int
	var printErr error
	messages, results := session.Messages, session.Result
	for messages != nil || results != nil {
		select {
		case message, ok := <-messages:
			if !ok {
				messages = nil
				continue
			}
			if printErr == nil {
				printErr = encoder.Encode(map[string]any{"kind": "message", "message": message})
				if printErr != nil {
					cancel() // still drain so the backend can finish cleanup
				}
			}
		case value, ok := <-results:
			if !ok {
				results = nil
				continue
			}
			result, resultCount = value, resultCount+1
		}
	}
	if printErr != nil {
		return printErr
	}
	if resultCount != 1 {
		return fmt.Errorf("expected exactly one Result, received %d", resultCount)
	}
	if err := encoder.Encode(map[string]any{
		"kind": "result", "result": result, "requested_session_id": *resume,
		"resume_matched": *resume != "" && result.SessionID == *resume,
	}); err != nil {
		return err
	}
	if result.Status != "completed" {
		return fmt.Errorf("backend status %q: %s", result.Status, result.Error)
	}
	if result.SessionID == "" || (*resume != "" && result.SessionID != *resume) {
		return errors.New("missing or changed session ID; completed output alone does not prove resume")
	}
	return nil
}

func prepareState(previous string) (string, error) {
	if previous != "" {
		root, err := filepath.Abs(previous)
		if err != nil {
			return "", err
		}
		// Refuse arbitrary/global homes and symlinked probe directories.
		for _, path := range []string{root, filepath.Join(root, "codex-home"), filepath.Join(root, "work")} {
			info, err := os.Lstat(path)
			if err != nil || !info.IsDir() || info.Mode().Perm()&0077 != 0 {
				return "", fmt.Errorf("not a private probe directory: %s", path)
			}
		}
		data, err := os.ReadFile(filepath.Join(root, "codex-home", "config.toml"))
		if err != nil || string(data) != probeConfig {
			return "", errors.New("state-dir does not contain the unchanged probe configuration")
		}
		return root, nil
	}
	root, err := os.MkdirTemp("", "blaine-codex-probe-")
	if err != nil {
		return "", err
	}
	for _, name := range []string{"codex-home", "work"} {
		if err := os.Mkdir(filepath.Join(root, name), 0700); err != nil {
			return "", err
		}
	}
	err = os.WriteFile(filepath.Join(root, "codex-home", "config.toml"), []byte(probeConfig), 0600)
	return root, err
}

func copyAuth(probeHome string) (func(), error) {
	sourceHome := os.Getenv("CODEX_HOME")
	if sourceHome == "" {
		userHome, err := os.UserHomeDir()
		if err != nil {
			return nil, err
		}
		sourceHome = filepath.Join(userHome, ".codex")
	}
	source, err := os.Open(filepath.Join(sourceHome, "auth.json"))
	if err != nil {
		return nil, fmt.Errorf("read existing Codex file authentication (keyring-only auth is outside this probe): %w", err)
	}
	defer source.Close()
	path := filepath.Join(probeHome, "auth.json")
	destination, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return nil, fmt.Errorf("create private auth copy (concurrent runs in one state-dir are unsupported): %w", err)
	}
	cleanup := func() {
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			fmt.Fprintln(os.Stderr, "probe: remove private auth copy:", err)
		}
	}
	_, copyErr := io.Copy(destination, source)
	closeErr := destination.Close()
	if err := errors.Join(copyErr, closeErr); err != nil {
		cleanup()
		return nil, err
	}
	return cleanup, nil
}
