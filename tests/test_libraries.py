# ==============================================================================
# TEST LIBRARIES
# ==============================================================================
# PURPOSE:
# Verify acquisition and identity independently of the Core architecture.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Local Git fixtures and loader contract checks.
# Delegates: Repository operations to Git and Python identity to the loader.
# ==============================================================================

import os
import subprocess
import sys
import tempfile
import unittest

from unittest.mock import patch

import almasi
from almasi import Libraries


class TestLibraries(unittest.TestCase):

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Commit changes to a local fixture without user-specific Git settings.
	# ----------------------------------------------------------------------
	def _commit(self, directory):
		subprocess.run(['git', '-C', directory, 'add', '.'], check=True)
		subprocess.run([
			'git', '-C', directory,
			'-c', 'user.name=Almasi Test',
			'-c', 'user.email=test@example.test',
			'-c', 'commit.gpgSign=false',
			'-c', f'core.hooksPath={os.devnull}',
			'commit', '-qm', 'Fixture'
		], check=True)

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Load a library without acquiring Core or changing the loader identity.
	# ----------------------------------------------------------------------
	def test_independent_import(self):
		with tempfile.TemporaryDirectory() as home:
			path = os.path.join(home, 'almasi.example')
			os.makedirs(path)

			with open(os.path.join(path, 'example.py'), 'w') as stream:
				stream.write('value = 7\n')

			with patch.dict(os.environ, {'ALMASI_PATH': home}), patch.dict(sys.modules):
				library = almasi.example

				self.assertEqual(library.value, 7)
				self.assertIs(library, almasi.example)
				self.assertIs(library, sys.modules['almasi.example'])
				self.assertIs(almasi, sys.modules['almasi'])
				self.assertNotIn('almasi.a', sys.modules)

	# Update before a new import but never replace a loaded module.
	# ----------------------------------------------------------------------
	def test_git_update(self):
		with tempfile.TemporaryDirectory() as home:
			origin = os.path.join(home, 'almasi.example.git')
			cache  = os.path.join(home, 'cache')
			os.makedirs(origin)

			subprocess.run(['git', 'init', '-q', origin], check=True)

			entry = os.path.join(origin, 'example.py')

			with open(entry, 'w') as stream:
				stream.write('value = 1\n')

			self._commit(origin)

			with patch.dict(os.environ, {'ALMASI_PATH': cache, 'ALMASI_GIT_BASE': home}):
				with patch.dict(sys.modules):
					library = Libraries.imp('example')
					self.assertEqual(library.value, 1)

					with open(entry, 'w') as stream:
						stream.write('value = 200\n')

					self._commit(origin)
					self.assertIs(Libraries.imp('example'), library)
					self.assertEqual(library.value, 1)

				with patch.dict(sys.modules):
					self.assertEqual(Libraries.imp('example').value, 200)

	# A failed entry must not leave an apparently imported library.
	# ----------------------------------------------------------------------
	def test_failed_entry(self):
		with tempfile.TemporaryDirectory() as home:
			path = os.path.join(home, 'almasi.broken')
			os.makedirs(path)

			with open(os.path.join(path, 'broken.py'), 'w') as stream:
				stream.write('raise RuntimeError("broken")\n')

			with patch.dict(os.environ, {'ALMASI_PATH': home}):
				with self.assertRaisesRegex(RuntimeError, 'broken'):
					Libraries.imp('broken')

				self.assertNotIn('almasi.broken', sys.modules)

	# Reject invalid names without invoking Git or constructing unsafe paths.
	# ----------------------------------------------------------------------
	def test_invalid_name(self):
		with self.assertRaises(ValueError):
			Libraries.imp('../outside')
