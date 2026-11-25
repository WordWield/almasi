# Compare no-change update checks against real public GitHub repositories.
import json
import os
import random
import statistics
import subprocess
import tempfile
import time
import urllib.request


_REPOSITORIES = ('almasi.cli', 'almasi.hub', 'almasi.o')
_OWNER        = 'WordWield'
_ROUNDS       = 9
_TIMEOUT      = 15


# Run the same noninteractive Git commands used by the loader.
# ----------------------------------------------------------------------
def git(*arguments):
	return subprocess.run(
		['git', *arguments],
		capture_output = True,
		text           = True,
		timeout        = _TIMEOUT,
		check          = True
	).stdout.strip()


# Time one check, including local SHA resolution for the alternatives.
# ----------------------------------------------------------------------
def measure(method, directory, url, api, ref, expected):
	start = time.perf_counter()

	if method == 'pull':
		git('-C', directory, '--git-dir=.git', '--work-tree=.', 'pull', '--ff-only', '--quiet')
		milliseconds = (time.perf_counter() - start) * 1000
		actual = git('-C', directory, 'rev-parse', 'HEAD')
		assert actual == expected, 'Repository changed during benchmark'
	else:
		local = git('-C', directory, 'rev-parse', 'HEAD')

		if method == 'ls_remote':
			actual = git('ls-remote', '--exit-code', url, ref).split()[0]
		else:
			request = urllib.request.Request(api, headers={
				'User-Agent': 'Almasi-Benchmark',
				'Accept':     'application/vnd.github.sha'
			})

			with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
				actual = response.read().decode().strip()

		assert actual == local == expected, f'SHA mismatch: {actual!r}'
		milliseconds = (time.perf_counter() - start) * 1000

	return round(milliseconds, 2)


# Alternate method order and report every sample, not just the fastest.
# ----------------------------------------------------------------------
def benchmark():
	methods = ['pull', 'ls_remote', 'api']
	randomizer = random.Random(42)
	results = {}

	with tempfile.TemporaryDirectory() as home:
		for repository in _REPOSITORIES:
			url       = f'https://github.com/{_OWNER}/{repository}.git'
			directory = os.path.join(home, repository)

			git('clone', '--quiet', url, directory)

			branch   = git('-C', directory, 'branch', '--show-current')
			ref      = f'refs/heads/{branch}'
			expected = git('-C', directory, 'rev-parse', 'HEAD')
			api      = f'https://api.github.com/repos/{_OWNER}/{repository}/commits/{branch}'
			samples  = {method: [] for method in methods}

			for index in range(_ROUNDS + 1):
				order = randomizer.sample(methods, len(methods))

				for method in order:
					value = measure(method, directory, url, api, ref, expected)

					if index > 0:
						samples[method].append(value)

			results[repository] = samples
			print(repository, branch, expected, flush=True)

			for method, values in samples.items():
				print(f'{method}: median={statistics.median(values):.2f} ms, min={min(values):.2f}, max={max(values):.2f}', flush=True)

	print('BENCHMARK_RESULT=' + json.dumps(results), flush=True)


if __name__ == '__main__':
	benchmark()
