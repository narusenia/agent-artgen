"""Modal で GPU が借りられるかの疎通確認。mise run art:check で動かす。"""

import modal

app = modal.App("artgen-smoke")


@app.function(gpu="T4", timeout=120)
def gpu_info() -> str:
    import subprocess

    return subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, check=True).stdout


@app.local_entrypoint()
def main():
    out = gpu_info.remote()
    assert "GPU" in out, out
    print(out.strip())
