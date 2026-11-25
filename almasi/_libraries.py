# ==============================================================================
# LIBRARIES
# ==============================================================================
# PURPOSE:
# Prepare and import independent libraries from their canonical Git checkouts.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Source selection, acquisition policy and initial module publication.
# Delegates: Git operations to Git, dependencies to pip and execution to Python.
# ==============================================================================

import hashlib
import importlib.util
import keyword
import os
import re
import subprocess
import sys
import tempfile

from contextlib import suppress
from threading  import RLock

from ._git      import _Git
from ._progress import _Progress


class _Libraries:

	_DEFAULT_GIT_BASE   = 'https://github.com/WordWield'
	_DEFAULT_CACHE      = '~/.cache/almasi/libraries'
	_PULL_TIMEOUT       = 15
	_REQUIREMENTS_CACHE = '.almasi'

	_lock = RLock()

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Publish a successful installation record without exposing partial writes.
	# ----------------------------------------------------------------------
	@staticmethod
	def _save_requirements_digest(record, digest):
		directory = os.path.dirname(record)
		os.makedirs(directory, exist_ok=True)

		with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
			try:
				stream.write(digest)
				stream.close()
				os.replace(stream.name, record)
			finally:
				with suppress(FileNotFoundError):
					os.unlink(stream.name)

	# Install only when the current environment has no matching success record.
	# ----------------------------------------------------------------------
	@classmethod
	def _install_requirements(cls, path, qualified, progress):
		requirements = os.path.join(path, 'requirements.txt')

		if os.path.isfile(requirements):
			record = os.path.join(sys.prefix, cls._REQUIREMENTS_CACHE, qualified + '.sha256')

			with open(requirements, 'rb') as stream:
				digest = hashlib.file_digest(stream, 'sha256').hexdigest().encode('ascii')

			try:
				with open(record, 'rb') as stream:
					installed = stream.read()
			except FileNotFoundError:
				installed = None

			if installed != digest:
				with suppress(FileNotFoundError):
					os.unlink(record)

				progress.update('Installing dependencies')
				subprocess.run(
					[sys.executable, '-m', 'pip', 'install', '-r', requirements],
					cwd            = path,
					capture_output = True,
					text           = True,
					check          = True
				)
				cls._save_requirements_digest(record, digest)
				progress.update('Installed dependencies')

	# Clone into the selected checkout without owning progress presentation.
	# ----------------------------------------------------------------------
	@classmethod
	def _clone(cls, name, destination):
		os.makedirs(os.path.dirname(destination), exist_ok=True)
		_Git.clone(cls.get_url(name), destination)

	# Prepare a library as one visible operation, even when it has many steps.
	# ----------------------------------------------------------------------
	@classmethod
	def _prepare(cls, name):
		path      = cls.get_path(name)
		qualified = f'almasi.{name}'

		with _Progress(qualified, 'Preparing library') as progress:
			if cls.is_cloned(name):
				try:
					if _Git.is_repository(path):
						progress.update('Checking for updates')
						_Git.pull(path, timeout=cls._PULL_TIMEOUT)
						progress.update('Checked for updates')
				except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
					progress.warn(f'Using local version ({error})', error)
			else:
				progress.update('Cloning library')
				cls._clone(name, path)
				progress.update('Cloned library')

			cls._install_requirements(path, qualified, progress)
			progress.update('Up to date')

		return path

	# Resolve the common entry point for imports and standalone execution.
	# ----------------------------------------------------------------------
	@staticmethod
	def _get_entry(name, path):
		entry = os.path.join(path, name + '.py')

		if not os.path.isfile(entry):
			entry = os.path.join(path, 'almasi', name + '.py')

		return entry

	# Execute the entry once, allowing it to publish its own library object.
	# ----------------------------------------------------------------------
	@classmethod
	def _load(cls, name, path):
		qualified = f'almasi.{name}'
		entry     = cls._get_entry(name, path)

		spec   = importlib.util.spec_from_file_location(qualified, entry, submodule_search_locations=[path])
		module = importlib.util.module_from_spec(spec)

		sys.modules[qualified] = module

		try:
			spec.loader.exec_module(module)
		except BaseException:
			for key in tuple(sys.modules):
				if key == qualified or key.startswith(qualified + '.'):
					sys.modules.pop(key, None)

			raise

		return sys.modules[qualified]

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Accept public canonical snake_case library names.
	# ----------------------------------------------------------------------
	@staticmethod
	def is_valid_name(name: str) -> bool:
		return isinstance(name, str) and re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*', name) is not None and not keyword.iskeyword(name)

	# Derive the source checkout path from the configured library directory.
	# ----------------------------------------------------------------------
	@classmethod
	def get_path(cls, name: str) -> str:
		if cls.is_valid_name(name):
			directory = os.environ.get('ALMASI_PATH') or os.path.expanduser(cls._DEFAULT_CACHE)
			result    = os.path.join(os.path.abspath(directory), 'almasi.' + name)
		else:
			raise ValueError(f'Invalid library name: {name!r}')

		return result

	# Derive a trusted remote from the configured organization or local origin.
	# ----------------------------------------------------------------------
	@classmethod
	def get_url(cls, name: str) -> str:
		if cls.is_valid_name(name):
			base   = os.environ.get('ALMASI_GIT_BASE', cls._DEFAULT_GIT_BASE).rstrip('/')
			result = f'{base}/almasi.{name}.git'
		else:
			raise ValueError(f'Invalid library name: {name!r}')

		return result

	# Recognize a local source tree without network access.
	# ----------------------------------------------------------------------
	@classmethod
	def is_cloned(cls, name: str) -> bool:
		return os.path.isdir(cls.get_path(name))

	# Clone a missing checkout, leaving local development trees untouched.
	# ----------------------------------------------------------------------
	@classmethod
	def clone(cls, name: str) -> str:
		destination = cls.get_path(name)

		with cls._lock:
			if not cls.is_cloned(name):
				with _Progress(f'almasi.{name}', 'Cloning library') as progress:
					cls._clone(name, destination)
					progress.update('Cloned library')

		return destination

	# Acquire only on first use and preserve the published identity thereafter.
	# ----------------------------------------------------------------------
	@classmethod
	def imp(cls, name: str):
		if cls.is_valid_name(name):
			qualified = f'almasi.{name}'

			with cls._lock:
				library = sys.modules.get(qualified)

				if library is None:
					path    = cls._prepare(name)
					library = cls._load(name, path)
		else:
			raise ValueError(f'Invalid library name: {name!r}')

		return library

	# Replace the launcher with an acquired library entry.
	# ----------------------------------------------------------------------
	@classmethod
	def run(
		cls,
		name      : str,
		arguments : list[str],
		entry     : str | None = None,
		cwd       : str | None = None
	):
		with cls._lock:
			path   = cls._prepare(name)
			script = cls._get_entry(name, path) if entry is None else os.path.join(path, entry)

		if os.path.isfile(script):
			if cwd is not None:
				os.chdir(cwd)

			os.execv(sys.executable, [sys.executable, script, *arguments])
		else:
			raise FileNotFoundError(f'Library {name!r} has no entry at {script}')
