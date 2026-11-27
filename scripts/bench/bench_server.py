#!/usr/bin/env python3
"""Serving-framework bench (SGLang Diffusion / vLLM-Omni) over the OpenAI images API.

RUN ON THE GPU INSTANCE with plain python3 (stdlib only). Starts the server itself so load time is measured:
  load  = `serve` process start -> GET /v1/models returns 200 (weights pre-downloaded)
  cold  = first POST /v1/images/generations after ready
  warm  = 6 sequential requests (median s/img; c1 throughput = 6 / wall)
  c4    = 8 requests, 4 in flight (throughput = 8 / wall; per-request latency recorded)
The server is started in its own process group and killed by that exact pgid at the end.

Usage: python3 bench_server.py --framework sglang --model qwen-turbo
       python3 bench_server.py --framework vllm-omni --model z-turbo --extra-args "--foo bar"
"""
import argparse, base64, json, os, shlex, signal, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as B

HOME = os.path.expanduser("~")
FW = {
    "sglang": {"port": 30000, "venv": f"{HOME}/venv-sglang",
               "cmd": "{venv}/bin/sglang serve --model-path {repo} --host 127.0.0.1 --port {port}",
               "ver": "import sglang,torch,diffusers;print(json.dumps({'sglang':sglang.__version__,'torch':torch.__version__,'torch_cuda':torch.version.cuda,'diffusers':diffusers.__version__}))"},
    "vllm-omni": {"port": 8000, "venv": f"{HOME}/venv-vllm",
                  "cmd": "{venv}/bin/vllm serve {repo} --omni --host 127.0.0.1 --port {port}",
                  "ver": "import vllm,torch,importlib.metadata as m;print(json.dumps({'vllm':vllm.__version__,'vllm_omni':m.version('vllm-omni'),'torch':torch.__version__,'torch_cuda':torch.version.cuda}))"},
}


def versions(venv, code):
    r = subprocess.run([f"{venv}/bin/python", "-c", "import json;" + code], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": (r.stderr or r.stdout)[-800:]}


def tail(path, n=60):
    try:
        return "".join(open(path, errors="replace").readlines()[-n:])
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--framework", required=True, choices=list(FW))
    ap.add_argument("--model", required=True, choices=list(B.MODELS))
    ap.add_argument("--prompts", default=f"{HOME}/prompts.jsonl")
    ap.add_argument("--out", default=f"{HOME}/bench/results")
    ap.add_argument("--extra-args", default="")
    ap.add_argument("--ready-timeout", type=int, default=1500)
    ap.add_argument("--req-timeout", type=int, default=900)
    a = ap.parse_args()
    fw, m = FW[a.framework], B.MODELS[a.model]
    out = os.path.join(a.out, a.model, a.framework); os.makedirs(out, exist_ok=True)
    base = f"http://127.0.0.1:{fw['port']}"
    cmd = fw["cmd"].format(venv=fw["venv"], repo=m["repo"], port=fw["port"]) + (" " + a.extra_args if a.extra_args else "")
    res = {"model": a.model, "framework": a.framework, "cmd": cmd, **B.gpu_info(),
           "versions": versions(fw["venv"], fw["ver"])}
    scenes = B.load_scenes(a.prompts)
    log = os.path.join(out, "server.log")
    sampler = B.GpuSampler(os.path.join(out, "vram.csv"))
    env = dict(os.environ, PATH=f"{fw['venv']}/bin:" + os.environ["PATH"])
    # DLAMI's /etc/profile.d/dlami.sh puts /usr/local/cuda(12.8)/lib64 on LD_LIBRARY_PATH; its cuDNN 9.10 then
    # shadows the cu130 wheel's bundled cuDNN 9.20 and vLLM-Omni dies with "cuDNN version incompatibility".
    # The py3.12 venvs ship every CUDA lib as wheels, so drop the system path for the servers.
    env.pop("LD_LIBRARY_PATH", None)
    t_start = time.time()
    proc = subprocess.Popen(shlex.split(cmd), stdout=open(log, "w"), stderr=subprocess.STDOUT,
                            env=env, start_new_session=True)

    def post(s, seed):
        body = {"prompt": s["prompt"], "size": f"{s['w']}x{s['h']}", "n": 1, "seed": seed,
                "num_inference_steps": m["steps"], "response_format": "b64_json", **m["extra"]}
        req = urllib.request.Request(base + "/v1/images/generations", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=a.req_timeout) as r:
            data = json.loads(r.read())
        dt = time.time() - t0
        png = base64.b64decode(data["data"][0]["b64_json"])
        return dt, png

    try:
        while True:  # ready poll
            if proc.poll() is not None:
                raise RuntimeError(f"server exited rc={proc.returncode} before ready")
            if time.time() - t_start > a.ready_timeout:
                raise RuntimeError(f"not ready after {a.ready_timeout}s")
            try:
                with urllib.request.urlopen(base + "/v1/models", timeout=5) as r:
                    if r.status == 200:
                        res["models_endpoint"] = json.loads(r.read()); break
            except Exception:
                pass
            time.sleep(2)
        res["load_s"] = round(time.time() - t_start, 1)

        dt, png = post(scenes[0], 11)
        open(os.path.join(out, f"cold_{scenes[0]['id']}_seed11.png"), "wb").write(png)
        res["cold_s"] = round(dt, 2); res["size"] = B.png_size(png)
        warm = []; t0 = time.time()
        for s, seed in B.warm_jobs(scenes):
            d, png = post(s, seed); warm.append(round(d, 2))
            open(os.path.join(out, f"warm_{s['id']}_seed{seed}.png"), "wb").write(png)
        res["warm_s"] = warm; res["warm_median_s"] = round(B.median(warm), 2)
        res["c1_img_per_s"] = round(len(warm) / (time.time() - t0), 3)

        jobs = B.c4_jobs(scenes); t0 = time.time()
        with ThreadPoolExecutor(B.C4_CONC) as ex:
            lat = [round(f.result()[0], 2) for f in [ex.submit(post, s, seed) for s, seed in jobs]]
        wall = time.time() - t0
        res["c4_latency_s"] = lat; res["c4_wall_s"] = round(wall, 1)
        res["c4_img_per_s"] = round(len(jobs) / wall, 3)
        res["status"] = "ok"
    except Exception as e:
        import traceback
        res["status"] = "error"; res["error"] = traceback.format_exc()[-1500:]
        res["server_log_tail"] = tail(log)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM); proc.wait(timeout=60)
        except Exception:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except Exception: pass
        time.sleep(5)
        res["peak_vram_mib"] = sampler.stop()
    B.write_json(os.path.join(out, "result.json"), res)
    print(a.framework, a.model, res["status"], res.get("load_s"), res.get("cold_s"), res.get("warm_median_s"),
          res.get("c4_img_per_s"), res["peak_vram_mib"], flush=True)


if __name__ == "__main__":
    main()
