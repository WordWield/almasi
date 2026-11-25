# ==============================================================================
# PROGRESS
# ==============================================================================
# PURPOSE:
# Present library acquisition progress before Core becomes available.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Library-level terminal and redirected-stream progress rendering.
# Delegates: Terminal animation to yaspin; operation and error policy to callers.
# ==============================================================================

import subprocess
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
		self._warning = None
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

		status = ('⚠️' if self._warning is not None else '✔') if exc_type is None else '❌'

		if exc_type is None and self._warning is None and self._spinner is not None:
			status = '\033[1;32m✔\033[0m'

		if exc_type is None and self._warning is not None:
			self._text = self._warning

		print(f'{status} {self._format()}', file=self._stream, flush=True)

		self._report_error(exc_value)

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Preserve subprocess diagnostics for failures and recoverable Git errors.
	# ----------------------------------------------------------------------
	def _report_error(self, error):
		if isinstance(error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
			for output in (error.stdout, error.stderr):
				if output:
					if isinstance(output, bytes):
						output = output.decode('utf-8', errors='replace')

					print(output.rstrip(), file=self._stream, flush=True)

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

	# Retain a recoverable warning instead of claiming the library is current.
	# ----------------------------------------------------------------------
	def warn(self, text: str, error: BaseException) -> None:
		self._warning = text

		if self._spinner is not None:
			self._spinner.stop()

		self._report_error(error)

		if self._spinner is not None:
			self._spinner.start()
