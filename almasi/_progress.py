# ==============================================================================
# PROGRESS
# ==============================================================================
# PURPOSE:
# Present library acquisition progress before Core becomes available.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Single-operation terminal and redirected-stream progress rendering.
# Delegates: Terminal animation to yaspin; operation and error policy to callers.
# ==============================================================================

import sys

from yaspin import yaspin


class _Progress:

	_NAME_WIDTH = 18

	# ======================================================================
	# FRAMEWORK METHODS
	# ======================================================================

	# Keep redirected streams free of animation and terminal control codes.
	# ----------------------------------------------------------------------
	def __init__(self, name: str, text: str):
		self._stream  = sys.stderr
		self._name    = name + ':'
		self._text    = text
		self._spinner = yaspin(text=self._format(), stream=self._stream) if self._stream.isatty() else None

	# Expose the operation's progress rather than its animation.
	# ----------------------------------------------------------------------
	def __enter__(self):
		if self._spinner is not None:
			self._spinner.__enter__()

		return self

	# Render the operation's outcome without suppressing its exception.
	# ----------------------------------------------------------------------
	def __exit__(self, exc_type, exc_value, traceback):
		if self._spinner is not None:
			self._spinner.__exit__(exc_type, exc_value, traceback)

		status = '✔' if exc_type is None else '❌'

		if exc_type is None and self._spinner is not None:
			status = '\033[1;32m✔\033[0m'

		print(f'{status} {self._format()}', file=self._stream, flush=True)

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Align operation descriptions without truncating long library names.
	# ----------------------------------------------------------------------
	def _format(self):
		return f'{self._name:<{self._NAME_WIDTH}} {self._text}'

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Replace the active description with the operation's completed outcome.
	# ----------------------------------------------------------------------
	def update(self, text: str) -> None:
		self._text = text

		if self._spinner is not None:
			self._spinner.text = self._format()
