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

import importlib.util
import keyword
import os
import re
import subprocess
import sys

from threading import RLock

from ._git import Git


class Libraries:

	_DEFAULT_GIT_BASE = 'https://github.com/WordWield'
	_DEFAULT_CACHE    = '~/.cache/almasi/libraries'
	_PULL_TIMEOUT     = 15

	_lock = RLock()

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Install the declared dependencies into the active Python environment.
	# ----------------------------------------------------------------------
	@classmethod
	def _install_requirements(cls, path, qualified):
		requirements = os.path.join(path, 'requirements.txt')

		if os.path.isfile(requirements):
			print(f'{qualified}: Installing dependencies', file=sys.stderr)

			subprocess.run(
				[sys.executable, '-m', 'pip', 'install', '-r', requirements],
				cwd            = path,
				capture_output = True,
				text           = True,
				check          = True
			)

	# Reuse a local checkout if an update is unavailable.
	# ----------------------------------------------------------------------
	@classmethod
	def _prepare(cls, name):
		path      = cls.get_path(name)
		qualified = f'almasi.{name}'

		if cls.is_cloned(name):
			try:
				if Git.is_repository(path):
					print(f'{qualified}: Checking for updates', file=sys.stderr)
					Git.pull(path, timeout=cls._PULL_TIMEOUT)
			except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
				details = getattr(error, 'stderr', None) or str(error)
				print(f'⚠️ {qualified}: using local version ({str(details).strip()})', file=sys.stderr)
		else:
			path = cls.clone(name)

		cls._install_requirements(path, qualified)

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
				print(f'almasi.{name}: Cloning library', file=sys.stderr)
				os.makedirs(os.path.dirname(destination), exist_ok=True)
				Git.clone(cls.get_url(name), destination)

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

	# Replace the launcher with the acquired standalone Python entry.
	# ----------------------------------------------------------------------
	@classmethod
	def run(cls, name: str, arguments: list[str]):
		with cls._lock:
			path  = cls._prepare(name)
			entry = cls._get_entry(name, path)

		os.execv(sys.executable, [sys.executable, entry, *arguments])
