"""
Orchestrator script to execute all CP7 benchmarks locally:
1. Start Agent v1 (port 8001) & Agent v2 (port 8002)
2. Run eval v1 & eval v2
3. Run load tests: concurrency 1, 10, 50, 100
4. Run load tests: slow rates 0, 0.03, 0.1
5. Fix knowledge base
6. Restart v2 and run eval v2 fixed (quality gate 100%)
7. Collect all JSON outputs
"""
import os
import sys
import time
import json
import urllib.request
import subprocess

CWD = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

def wait_for_server(port, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception as e:
            pass
        time.sleep(0.5)
    return False

def start_agent(version, port, extra_env=None):
    env = os.environ.copy()
    env["AGENT_VERSION"] = version
    env["PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen([PYTHON, "app.py"], cwd=CWD, env=env)
    if not wait_for_server(port):
        proc.kill()
        raise RuntimeError(f"Agent {version} on port {port} failed to start")
    print(f"✅ Agent {version} running on port {port} (PID: {proc.pid})")
    return proc

def run_cmd(args):
    print(f"▶️ Running: {' '.join(args)}")
    res = subprocess.run([PYTHON] + args, cwd=CWD, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return res

def main():
    os.makedirs(os.path.join(CWD, "reports"), exist_ok=True)
    
    # 1. Start v1 and v2
    v1_proc = start_agent("v1", 8001)
    v2_proc = start_agent("v2", 8002)

    try:
        # 2. Eval v1 and v2
        print("\n--- 2. Running Eval v1 ---")
        run_cmd(["eval/run_eval.py", "--url", "http://127.0.0.1:8001", "--out", "reports/eval_v1.json"])

        print("\n--- 3. Running Eval v2 (comparing with v1) ---")
        run_cmd(["eval/run_eval.py", "--url", "http://127.0.0.1:8002", "--baseline", "reports/eval_v1.json", "--out", "reports/eval_v2.json"])

        # 3. Load test concurrency
        print("\n--- 4. Running Load Tests for Concurrency 1, 10, 50, 100 ---")
        for c in [1, 10, 50, 100]:
            print(f"--> Concurrency {c}")
            run_cmd(["load_test.py", "--url", "http://127.0.0.1:8002", "--requests", "300", "--concurrency", str(c), "--out", f"reports/load_v2_c{c}.json"])

        # 4. Tail latency test with different slow rates
        print("\n--- 5. Running Tail Latency Tests (slow rates) ---")
        for slow_rate in ["0", "0.03", "0.1"]:
            print(f"--> MOCK_SLOW_RATE={slow_rate}")
            v2_proc.terminate()
            v2_proc.wait(5)
            v2_proc = start_agent("v2", 8002, extra_env={"MOCK_SLOW_RATE": slow_rate})
            run_cmd(["load_test.py", "--url", "http://127.0.0.1:8002", "--requests", "300", "--concurrency", "20", "--out", f"reports/load_v2_slow_{slow_rate}.json"])

    finally:
        v1_proc.terminate()
        v2_proc.terminate()
        v1_proc.wait(5)
        v2_proc.wait(5)

    print("\n✅ Baseline tests finished!")

if __name__ == "__main__":
    main()
