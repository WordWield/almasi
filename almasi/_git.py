# ==============================================================================
# GIT
# ==============================================================================
# PURPOSE:
# Acquire and update local Git working checkouts independently of their use.
#
# RESPONSIBILITY BOUNDARIES:
# Owns: Git command construction and local checkout recognition.
# Delegates: Authentication and repository operations to the Git executable.
# Callers own repository selection, update policy and progress presentation.
# ==============================================================================

import os
import subprocess


class _Git:

	# ======================================================================
	# PRIVATE METHODS
	# ======================================================================

	# Execute Git directly, preserving diagnostics and native failure types.
	# ----------------------------------------------------------------------
	@classmethod
	def _run(
		cls,
		arguments,
		timeout = None,
		check   = True
	):
		return subprocess.run(
			['git', *arguments],
			capture_output = True,
			text           = True,
			timeout        = timeout,
			check          = check
		)

	# ======================================================================
	# PUBLIC METHODS
	# ======================================================================

	# Clone a trusted remote into an explicitly selected local directory.
	# ----------------------------------------------------------------------
	@classmethod
	def clone(cls, url: str, directory: str, timeout: float | None = None) -> str:
		cls._run(['clone', '--quiet', '--', url, directory], timeout=timeout)

		return directory

	# Update this checkout without merging or implicitly using a parent repo.
	# ----------------------------------------------------------------------
	@classmethod
	def pull(cls, directory: str, timeout: float | None = None) -> None:
		cls._run(
			['-C', directory, '--git-dir=.git', '--work-tree=.', 'pull', '--ff-only', '--quiet'],
			timeout=timeout
		)

	# Recognize working checkout roots, including linked Git worktrees.
	# ----------------------------------------------------------------------
	@classmethod
	def is_repository(cls, directory: str) -> bool:
		result = False

		if os.path.exists(os.path.join(directory, '.git')):
			probe = cls._run(
				['-C', directory, '--git-dir=.git', '--work-tree=.', 'rev-parse', '--is-inside-work-tree'],
				check=False
			)
			result = probe.returncode == 0 and probe.stdout.strip() == 'true'

		return result
