# ==============================================================================
# INSTALLER PROGRESS
# ==============================================================================
# PURPOSE:
# Present library acquisition operations without loading Core or dependencies.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Aligned terminal animation and final operation outcomes.
# Delegates: Operation execution and fallback decisions to callers.
# ==============================================================================

import sys

from threading import Event, Thread


class _Progress:

	_WIDTH    = 22
	_FRAMES   = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
	_INTERVAL = 0.1

	# ======================================================================
	# FRAMEWORK METHODS
	# ======================================================================

	# Capture the output stream and the active and successful descriptions.
	# ----------------------------------------------------------------------
	def __init__(self, name: str, active: str, done: str):
		self._name   = name
		self._active = active
		self._done   = done
		self._stream = sys.stderr
		self._tty    = self._stream.isatty()
		self._stop   = Event()
		self._thread = None
		self._warning = None

	# Animate only on a terminal; ordinary log streams receive final lines.
	# ----------------------------------------------------------------------
	def __enter__(self):
		if self._tty:
			self._thread = Thread(target=self._animate, daemon=True)
			self._thread.start()

		return self

	# Stop animation before writing the outcome; never suppress exceptions.
	# ----------------------------------------------------------------------
	def __exit__(self, exc_type, exc_value, traceback):
		if self._thread is not None:
			self._stop.set()
			self._thread.join()
			self._stream.write('\r\033[2K')

		if exc_type is not None:
			self._render('✘', f'{self._active} failed', '31')
		elif self._warning is not None:
			self._render('!', self._warning, '33')
		else:
			self._render('✔', self._done, '32')

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Keep library names aligned across all installer operations.
	# ----------------------------------------------------------------------
	def _line(self, status, text):
		return f'{status} {self._name:<{self._WIDTH}} {text}'

	# Replace the active terminal row until the operation completes.
	# ----------------------------------------------------------------------
	def _animate(self):
		index = 0

		while not self._stop.is_set():
			frame = self._FRAMES[index % len(self._FRAMES)]
			self._stream.write('\r\033[2K' + self._line(frame, self._active))
			self._stream.flush()
			index += 1
			self._stop.wait(self._INTERVAL)

	# Apply color only to the terminal status mark.
	# ----------------------------------------------------------------------
	def _render(self, status, text, color):
		if self._tty:
			status = f'\033[1;{color}m{status}\033[0m'

		print(self._line(status, text), file=self._stream, flush=True)

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Report a recoverable failure instead of a successful outcome.
	# ----------------------------------------------------------------------
	def warn(self, text: str):
		self._warning = text

	# Report a warning detected before an operation could begin.
	# ----------------------------------------------------------------------
	@classmethod
	def warning(cls, name: str, text: str):
		progress = cls(name, '', '')
		progress._render('!', text, '33')
