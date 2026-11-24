# ==============================================================================
# TEST PROGRESS
# ==============================================================================
# PURPOSE:
# Verify private installer progress on terminals and redirected streams.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Outcome, alignment and terminal lifecycle assertions.
# Delegates: Actual terminal presentation to the progress context.
# ==============================================================================

import io
import unittest

from contextlib    import redirect_stderr
from unittest.mock import patch

from almasi._progress import _Progress


class TestProgress(unittest.TestCase):

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Log completed operations once, with aligned names and no escape codes.
	# ----------------------------------------------------------------------
	def test_redirected_output(self):
		stream = io.StringIO()

		with redirect_stderr(stream):
			with _Progress('almasi.a', 'Updating', 'Updated'):
				self.assertEqual(stream.getvalue(), '')

			with _Progress('almasi.example', 'Cloning', 'Cloned'):
				self.assertNotIn('Cloning', stream.getvalue())

			with _Progress('almasi.a', 'Installing dependencies', 'Dependencies installed'):
				self.assertNotIn('Installing dependencies', stream.getvalue())

		lines = stream.getvalue().splitlines()
		self.assertEqual(lines, [
			f'✔ {"almasi.a":<22} Updated',
			f'✔ {"almasi.example":<22} Cloned',
			f'✔ {"almasi.a":<22} Dependencies installed'
		])

	# Preserve exceptions and distinguish recoverable warnings from success.
	# ----------------------------------------------------------------------
	def test_outcomes(self):
		stream = io.StringIO()

		with redirect_stderr(stream):
			with self.assertRaisesRegex(ValueError, 'broken'):
				with _Progress('almasi.a', 'Cloning', 'Cloned'):
					int('broken')

			with _Progress('almasi.a', 'Updating', 'Updated') as progress:
				progress.warn('Using local version (offline)')

			_Progress.warning('almasi.o', 'Using local version (offline)')

		lines = stream.getvalue().splitlines()
		self.assertEqual(lines, [
			f'✘ {"almasi.a":<22} Cloning failed',
			f'! {"almasi.a":<22} Using local version (offline)',
			f'! {"almasi.o":<22} Using local version (offline)'
		])

	# Join the terminal animation before rendering the final colored outcome.
	# ----------------------------------------------------------------------
	def test_terminal(self):
		stream = io.StringIO()

		with redirect_stderr(stream), patch.object(stream, 'isatty', return_value=True):
			with _Progress('almasi.a', 'Updating', 'Updated') as progress:
				self.assertTrue(progress._thread.is_alive())

			self.assertFalse(progress._thread.is_alive())

		output = stream.getvalue()
		self.assertIn('\033[1;32m✔\033[0m', output)
		self.assertTrue(output.endswith(f' {"almasi.a":<22} Updated\n'))
