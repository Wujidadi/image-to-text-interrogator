"""Claude Code as a backend: `claude -p` reads the image with its Read tool.

Not an HTTP API, but the best-scoring route in the maintainer's evaluation
(Sonnet 5, no misreadings, 12 s) for a subscription that bills by quota
rather than per call. Each call carries 50k to 70k tokens of Claude Code's
own system prompt and tool definitions, so batches belong elsewhere"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from ..errors import ConfigError, OverloadedError, ProviderError
from ..prompt import build_user
from . import register
from .base import Provider

# Set inside a Claude Code session; a nested `claude -p` refuses to start
# while they are present
NESTED_SESSION_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
               "image/gif": ".gif"}


def _is_overloaded(text):
    return "529" in text or "overloaded" in text.lower()


@register
class ClaudeCodeProvider(Provider):
    """Settings: model (a Claude Code alias such as sonnet, default),
    command (the executable, default claude), extra_args (list appended to
    the command line), timeout"""

    type_name = "claude-code"
    default_model = "sonnet"

    def __init__(self, settings):
        super().__init__(settings)
        self.command = settings.get("command", "claude")
        self.extra_args = list(settings.get("extra_args") or [])
        self.last_usage = None

    def complete(self, system, prompt, image):
        if image.path is not None:
            return self._run(system, prompt, image.path)
        suffix = _EXTENSIONS[image.media_type]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(image.data)
        path = Path(handle.name)
        try:
            return self._run(system, prompt, path)
        finally:
            path.unlink()

    def _run(self, system, prompt, path):
        cmd = [self.command, "-p", "--model", self.model, "--output-format", "json",
               "--system-prompt", system, "--tools", "Read", "--allowedTools", "Read",
               *self.extra_args]
        env = {k: v for k, v in os.environ.items() if k not in NESTED_SESSION_VARS}
        try:
            completed = subprocess.run(cmd, input=build_user(path, prompt), capture_output=True,
                                       text=True, timeout=self.timeout, env=env)
        except FileNotFoundError as e:
            raise ConfigError(f'provider "{self.name}": claude executable not found '
                              f"({self.command})") from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"{self.describe()}: timed out after {self.timeout}s") from e
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[:500]
            message = f"{self.describe()}: exit status {completed.returncode}: {detail}"
            if _is_overloaded(detail):
                raise OverloadedError(message)
            raise ProviderError(message)
        return self._parse(completed.stdout)

    def _parse(self, stdout):
        try:
            reply = json.loads(stdout)
            result = reply.get("result")
        except (ValueError, AttributeError):
            reply, result = None, None
        if reply is None or not isinstance(result, (str, type(None))):
            raise ProviderError(f"{self.describe()}: unexpected output: {stdout[:200]}")
        if reply.get("is_error") or reply.get("subtype") != "success":
            detail = result or reply.get("subtype") or "error"
            message = f"{self.describe()}: {detail}"
            if _is_overloaded(detail):
                raise OverloadedError(message)
            raise ProviderError(message)
        self.last_usage = {"total_cost_usd": reply.get("total_cost_usd"),
                           "modelUsage": reply.get("modelUsage")}
        return result or ""
