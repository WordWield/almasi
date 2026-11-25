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

import hashlib
import io
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
import venv

from contextlib         import redirect_stderr
from importlib.metadata import version
from unittest.mock     import patch

import almasi
from almasi._libraries import _Libraries
from almasi._progress  import _Progress


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

	# Keep implementation names outside the public library namespace.
	# ----------------------------------------------------------------------
	def test_private_loader_namespace(self):
		self.assertFalse([name for name in vars(almasi) if not name.startswith('_')])
		self.assertFalse(hasattr(almasi, 'Git'))
		self.assertFalse(hasattr(almasi, 'Libraries'))
		self.assertEqual(_Libraries.__name__, '_Libraries')

	# Captured progress emits one plain outcome and preserves failures.
	# ----------------------------------------------------------------------
	def test_progress(self):
		output = io.StringIO()

		with redirect_stderr(output):
			with _Progress('almasi.a', 'Checking') as progress:
				progress.update('Checked')

			with self.assertRaisesRegex(RuntimeError, 'fixture'):
				with _Progress('almasi.web', 'Installing'):
					raise RuntimeError('fixture')

		self.assertEqual(output.getvalue().splitlines(), [
			'✔ almasi.a:          Checked',
			'❌ almasi.web:        Installing'
		])

	# Preserve both captured subprocess streams when an operation fails.
	# ----------------------------------------------------------------------
	def test_progress_diagnostics(self):
		output = io.StringIO()
		error  = subprocess.CalledProcessError(1, ['fixture'], output='stdout detail', stderr='stderr detail')

		with redirect_stderr(output), self.assertRaises(subprocess.CalledProcessError) as failure:
			with _Progress('almasi.a', 'Installing dependencies'):
				raise error

		self.assertIs(failure.exception, error)
		self.assertEqual(output.getvalue().splitlines()[1:], ['stdout detail', 'stderr detail'])

	# Read installed metadata without acquiring a library or creating a cache.
	# ----------------------------------------------------------------------
	def test_version(self):
		with tempfile.TemporaryDirectory() as home:
			cache       = os.path.join(home, 'cache')
			environment = dict(os.environ, ALMASI_PATH=cache, ALMASI_GIT_BASE=home)

			for command in ([sys.executable, '-m', 'almasi'], [os.path.join(sysconfig.get_path('scripts'), 'almasi')]):
				process = subprocess.run(
					[*command, '--version'],
					cwd            = home,
					env            = environment,
					capture_output = True,
					text           = True
				)
				self.assertEqual(process.returncode, 0, process.stderr)
				self.assertEqual(process.stdout.strip(), 'almasi ' + version('almasi'))
				self.assertEqual(process.stderr, '')
				self.assertFalse(os.path.exists(cache))

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
					library = _Libraries.imp('example')
					self.assertEqual(library.value, 1)

					with open(entry, 'w') as stream:
						stream.write('value = 200\n')

					self._commit(origin)
					self.assertIs(_Libraries.imp('example'), library)
					self.assertEqual(library.value, 1)

				with patch.dict(sys.modules):
					self.assertEqual(_Libraries.imp('example').value, 200)

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
					_Libraries.imp('broken')

				self.assertNotIn('almasi.broken', sys.modules)

	# Reject invalid names without invoking Git or constructing unsafe paths.
	# ----------------------------------------------------------------------
	def test_invalid_name(self):
		with self.assertRaises(ValueError):
			_Libraries.imp('../outside')

	# Reuse only a matching successful installation in the active environment.
	# ----------------------------------------------------------------------
	def test_requirements_digest(self):
		with tempfile.TemporaryDirectory() as home:
			path         = os.path.join(home, 'source')
			environment  = os.path.join(home, 'venv')
			requirements = os.path.join(path, 'requirements.txt')
			record       = os.path.join(environment, '.almasi', 'almasi.example.sha256')
			os.makedirs(path)

			with patch.object(sys, 'prefix', environment), patch('almasi._libraries.subprocess.run') as install:
				_Libraries._install_requirements(path, 'almasi.example')
				install.assert_not_called()

				with open(requirements, 'wb') as stream:
					stream.write(b'pip\n')

				_Libraries._install_requirements(path, 'almasi.example')
				install.assert_called_once_with(
					[sys.executable, '-m', 'pip', 'install', '-r', requirements],
					cwd            = path,
					capture_output = True,
					text           = True,
					check          = True
				)

				with open(record, 'rb') as stream:
					self.assertEqual(stream.read(), hashlib.sha256(b'pip\n').hexdigest().encode('ascii'))

				_Libraries._install_requirements(path, 'almasi.example')
				self.assertEqual(install.call_count, 1)

				with patch.object(sys, 'prefix', os.path.join(home, 'other')):
					_Libraries._install_requirements(path, 'almasi.example')

				self.assertEqual(install.call_count, 2)

				_Libraries._install_requirements(path, 'almasi.other')
				self.assertEqual(install.call_count, 3)

				with open(requirements, 'wb') as stream:
					stream.write(b'pip>=1\n')

				install.side_effect = subprocess.CalledProcessError(1, ['pip'])

				with self.assertRaises(subprocess.CalledProcessError):
					_Libraries._install_requirements(path, 'almasi.example')

				self.assertFalse(os.path.exists(record))
				install.side_effect = None

				_Libraries._install_requirements(path, 'almasi.example')
				self.assertEqual(install.call_count, 5)

				with open(record, 'rb') as stream:
					self.assertEqual(stream.read(), hashlib.sha256(b'pip>=1\n').hexdigest().encode('ascii'))

				os.unlink(record)
				_Libraries._install_requirements(path, 'almasi.example')
				self.assertEqual(install.call_count, 6)

				self.assertEqual(sorted(os.listdir(os.path.dirname(record))), [
					'almasi.example.sha256', 'almasi.other.sha256'
				])

	# Exercise actual pip in an isolated environment without network access.
	# ----------------------------------------------------------------------
	def test_requirements_installation(self):
		with tempfile.TemporaryDirectory() as home:
			environment  = os.path.join(home, 'venv')
			requirements = os.path.join(home, 'requirements.txt')
			record       = os.path.join(environment, '.almasi', 'almasi.example.sha256')

			venv.EnvBuilder(with_pip=True).create(environment)
			python = os.path.join(environment, 'bin', 'python')

			with open(requirements, 'w') as stream:
				stream.write('pip\n')

			with patch.object(sys, 'prefix', environment), patch.object(sys, 'executable', python):
				with patch.dict(os.environ, {'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}):
					output = io.StringIO()

					with redirect_stderr(output):
						_Libraries._install_requirements(home, 'almasi.example')
						_Libraries._install_requirements(home, 'almasi.example')

					self.assertEqual(output.getvalue().splitlines(), [
						'✔ almasi.example:    Installed dependencies'
					])
					self.assertTrue(os.path.isfile(record))

					with open(requirements, 'w') as stream:
						stream.write('invalid requirement syntax\n')

					with redirect_stderr(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
						_Libraries._install_requirements(home, 'almasi.example')

					self.assertFalse(os.path.exists(record))

	# Exercise both installed CLI entry forms using a real Git checkout.
	# ----------------------------------------------------------------------
	def test_cli(self):
		with tempfile.TemporaryDirectory() as home:
			origin     = os.path.join(home, 'almasi.example.git')
			cli_origin = os.path.join(home, 'almasi.cli.git')
			cache      = os.path.join(home, 'cache')
			os.makedirs(os.path.join(origin, 'root'))
			os.makedirs(cli_origin)

			for repository in (origin, cli_origin):
				subprocess.run(['git', 'init', '-q', repository], check=True)

			shutil.copytree(
				os.environ['ALMASI_CLI_SOURCE'],
				cli_origin,
				ignore        = shutil.ignore_patterns('.git'),
				dirs_exist_ok = True
			)
			self._commit(cli_origin)

			with open(os.path.join(origin, 'example.py'), 'w') as stream:
				stream.write('''import os
import sys

if __name__ == '__main__':
	print(os.getcwd())
	print(repr(sys.argv[1:]))
	sys.exit(7)
''')

			shutil.copyfile(os.path.join(origin, 'example.py'), os.path.join(origin, 'root', 'test.py'))
			self._commit(origin)

			environment = dict(os.environ, ALMASI_PATH=cache, ALMASI_GIT_BASE=home)
			commands    = [
				[sys.executable, '-m', 'almasi'],
				[os.path.join(sysconfig.get_path('scripts'), 'almasi')]
			]

			for index, command in enumerate(commands):
				with self.subTest(command=command):
					process = subprocess.run(
						[*command, 'run', 'example', 'demo', 'Word Wield', '--flag'],
						cwd            = home,
						env            = environment,
						capture_output = True,
						text           = True
					)

					self.assertEqual(process.returncode, 7, process.stderr)
					self.assertEqual(process.stderr.splitlines(), [
						'✔ almasi.cli:        Cloned library' if index == 0 else '✔ almasi.cli:        Checked for updates',
						'✔ almasi.example:    Cloned library' if index == 0 else '✔ almasi.example:    Checked for updates'
					])
					self.assertEqual(process.stdout.splitlines(), [
						os.path.realpath(home),
						repr(['demo', 'Word Wield', '--flag'])
					])
					self.assertTrue(os.path.isdir(os.path.join(cache, 'almasi.example', '.git')))

			process = subprocess.run(
				[*commands[0], 'test', 'example', '--flag'],
				cwd            = home,
				env            = environment,
				capture_output = True,
				text           = True
			)
			self.assertEqual(process.returncode, 7, process.stderr)
			self.assertEqual(process.stdout.splitlines(), [
				os.path.realpath(os.path.join(cache, 'almasi.example')),
				repr(['--flag'])
			])

			process = subprocess.run(
				[*commands[0], '--help'],
				cwd            = home,
				env            = environment,
				capture_output = True,
				text           = True
			)
			self.assertEqual(process.returncode, 0, process.stderr)
			self.assertIn('{run,test}', process.stdout)

			process = subprocess.run(
				[*commands[0], '_dispatch', 'example'],
				cwd            = home,
				env            = environment,
				capture_output = True,
				text           = True
			)
			self.assertEqual(process.returncode, 2)
			self.assertIn('invalid choice', process.stderr)

			process = subprocess.run(
				[*commands[0], 'test', 'cli'],
				cwd            = home,
				env            = environment,
				capture_output = True,
				text           = True
			)
			self.assertEqual(process.returncode, 0, process.stderr)
			self.assertIn('Ran 5 tests', process.stderr)
