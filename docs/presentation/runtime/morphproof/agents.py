"""File-based coding-agent handoff with frozen acceptance inputs."""
import hashlib
import json
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(reference: Path, contract_path: Path, candidate: Path, output: Path) -> Path:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "acceptance"
    frozen.mkdir()
    shutil.copy2(reference, frozen / "reference.py")
    shutil.copy2(contract_path, frozen / "contract.json")
    manifest = {name:digest(frozen / name) for name in ("reference.py", "contract.json")}
    (output / "acceptance.sha256.json").write_text(json.dumps(manifest, indent=2))
    (output / "TASK.md").write_text(
        "# MORPHPROOF agent task\n\nImprove or repair the candidate at " + str(Path(candidate).resolve()) +
        ". Preserve the acceptance contract and reference in acceptance/. "
        "Do not edit the verifier, contract, reference, or recorded evidence. "
        "Use counterexamples from the failed report. Return source changes and explain tradeoffs. "
        "The independent verifier decides acceptance.\n\n"
        "Codex: run `codex exec` in the candidate directory with this task.\n"
        "Claude Code: open the candidate directory and provide this task.\n"
        "Neither integration needs a provider API key from MORPHPROOF. "
        "Your agent's own access terms and permissions apply.\n")
    return output


def check(output: Path) -> None:
    output = Path(output)
    manifest = json.loads((output / "acceptance.sha256.json").read_text())
    for name, expected in manifest.items():
        if digest(output / "acceptance" / name) != expected:
            raise ValueError("Acceptance input changed: " + name)
