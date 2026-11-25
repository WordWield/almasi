# Compare no-change update checks against real public GitHub repositories.
import http.client
import json
import os
import platform
import random
import statistics
import subprocess
import tempfile
import time


_REPOSITORIES = ('almasi.cli', 'almasi.a', 'almasi.o')
_OWNER        = 'WordWield'
_API_HOST     = 'api.github.com'
_ROUNDS       = 9
_TIMEOUT      = 15
_METHODS      = ('pull', 'ls_remote', 'http_cold', 'http_warm')


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


# Fetch the remote SHA and verify whether the existing socket was reused.
# ----------------------------------------------------------------------
def fetch_sha(connection, api, headers):
	socket = connection.sock

	connection.request('GET', api, headers=headers)
	reused   = socket is not None and connection.sock is socket
	response = connection.getresponse()
	body     = response.read().decode().strip()

	if response.status == 200:
		result = body, reused
	else:
		raise RuntimeError(
			f'GitHub API HTTP {response.status}: {body}; '
			f'rate remaining={response.getheader("X-RateLimit-Remaining")}'
		)

	return result


# Time one check, including local SHA resolution for both alternatives.
# ----------------------------------------------------------------------
def measure(method, checkout, connection, headers):
	directory, url, ref, api, expected = checkout
	start = time.perf_counter()
	reused = False

	if method == 'pull':
		git('-C', directory, '--git-dir=.git', '--work-tree=.', 'pull', '--ff-only', '--quiet')
		milliseconds = (time.perf_counter() - start) * 1000

		assert git('-C', directory, 'rev-parse', 'HEAD') == expected, 'Repository changed during benchmark'
	else:
		local = git('-C', directory, 'rev-parse', 'HEAD')

		if method == 'ls_remote':
			actual = git('ls-remote', '--exit-code', url, ref).split()[0]
		else:
			actual, reused = fetch_sha(connection, api, headers)

		milliseconds = (time.perf_counter() - start) * 1000

		assert actual == local == expected, f'SHA mismatch: {actual!r}'

	return round(milliseconds, 2), reused


# Clone each repository once and resolve its actual default branch.
# ----------------------------------------------------------------------
def prepare(home):
	checkouts = {}

	for repository in _REPOSITORIES:
		url       = f'https://github.com/{_OWNER}/{repository}.git'
		directory = os.path.join(home, repository)

		git('clone', '--quiet', url, directory)

		branch   = git('-C', directory, 'branch', '--show-current')
		ref      = f'refs/heads/{branch}'
		api      = f'/repos/{_OWNER}/{repository}/commits/{branch}'
		expected = git('-C', directory, 'rev-parse', 'HEAD')

		checkouts[repository] = directory, url, ref, api, expected
		print(repository, branch, expected, flush=True)

	return checkouts


# Report all samples and exclude connection startups from warm statistics.
# ----------------------------------------------------------------------
def report(results, warm_startups, reconnects):
	for repository, samples in results.items():
		print(repository, flush=True)

		for method, values in samples.items():
			if values:
				print(
					f'{method}: median={statistics.median(values):.2f} ms, '
					f'min={min(values):.2f}, max={max(values):.2f}, n={len(values)}',
					flush=True
				)
			else:
				print(f'{method}: no valid samples', flush=True)

	print(f'Warm batch startups: {warm_startups}', flush=True)
	print(f'Unexpected reconnects: {reconnects}', flush=True)
	print('BENCHMARK_RESULT=' + json.dumps(results), flush=True)


# Interleave methods and rotate batch order to balance warm samples.
# ----------------------------------------------------------------------
def benchmark():
	token   = os.environ.get('GITHUB_TOKEN')
	headers = {
		'User-Agent': 'Almasi-Benchmark',
		'Accept':     'application/vnd.github.sha'
	}

	if token:
		headers['Authorization'] = 'Bearer ' + token

	print(f'Platform: {platform.platform()}', flush=True)
	print(f'API authentication: {bool(token)}', flush=True)

	randomizer    = random.Random(42)
	results       = {repository: {method: [] for method in _METHODS} for repository in _REPOSITORIES}
	warm_startups = []
	reconnects    = []
	api_error     = None
	repositories  = randomizer.sample(_REPOSITORIES, len(_REPOSITORIES))

	with tempfile.TemporaryDirectory() as home:
		checkouts = prepare(home)

		for index in range(_ROUNDS):
			offset = index % len(repositories)
			batch  = repositories[offset:] + repositories[:offset]

			for method in randomizer.sample(_METHODS, len(_METHODS)):
				is_http = method.startswith('http_')

				if not is_http or api_error is None:
					connection = http.client.HTTPSConnection(_API_HOST, timeout=_TIMEOUT) if is_http else None

					try:
						for position, repository in enumerate(batch):
							if method == 'http_cold':
								connection.close()

							try:
								value, reused = measure(method, checkouts[repository], connection, headers)

								if method == 'http_warm' and not reused:
									if position == 0:
										warm_startups.append(value)
									else:
										reconnects.append(value)
								else:
									results[repository][method].append(value)
							except (OSError, http.client.HTTPException, RuntimeError) as error:
								if is_http:
									api_error = str(error)
									print(f'API benchmark interrupted: {api_error}', flush=True)
									break
								else:
									raise
					finally:
						if connection is not None:
							connection.close()

	report(results, warm_startups, reconnects)

	if api_error is not None:
		print('API results are incomplete; Git measurements remain valid.', flush=True)


if __name__ == '__main__':
	benchmark()
