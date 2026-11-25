# Measure repeated dependency preparation in an isolated Python environment.
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import venv


_OWNER        = 'WordWield'
_REPOSITORIES = ('almasi.a', 'almasi.o')
_ROUNDS       = 7
_TIMEOUT      = 120


# Execute preparation and measurement commands with visible failure details.
# ----------------------------------------------------------------------
def execute(command, directory):
	start   = time.perf_counter()
	process = subprocess.run(
		command,
		cwd            = directory,
		capture_output = True,
		text           = True,
		timeout        = _TIMEOUT
	)
	elapsed = (time.perf_counter() - start) * 1000

	if process.returncode == 0:
		result = round(elapsed, 2)
	else:
		raise RuntimeError(process.stdout + process.stderr)

	return result


# Prepare all requirements before measuring already-satisfied installations.
# ----------------------------------------------------------------------
def prepare(home, python):
	checkouts = {}

	for repository in _REPOSITORIES:
		directory = os.path.join(home, repository)
		url       = f'https://github.com/{_OWNER}/{repository}.git'

		execute(['git', 'clone', '--quiet', url, directory], home)

		requirements = os.path.join(directory, 'requirements.txt')

		execute([python, '-m', 'pip', 'install', '-r', requirements], directory)

		checkouts[repository] = directory, requirements

	execute([python, '-m', 'pip', 'check'], home)

	return checkouts


# Compare the current command against no version check, dry run and uv.
# ----------------------------------------------------------------------
def benchmark():
	print(f'Platform: {platform.platform()}', flush=True)
	print(f'Python: {sys.version}', flush=True)

	uv         = shutil.which('uv')
	randomizer = random.Random(42)
	results    = {}

	with tempfile.TemporaryDirectory() as home:
		environment = os.path.join(home, 'venv')

		venv.EnvBuilder(with_pip=True).create(environment)

		python    = os.path.join(environment, 'bin', 'python')
		checkouts = prepare(home, python)

		for repository, checkout in checkouts.items():
			directory, requirements = checkout
			install = ['install', '-r', requirements]

			methods = {
				'pip'         : [python, '-m', 'pip', *install],
				'pip_no_check': [python, '-m', 'pip', '--disable-pip-version-check', *install],
				'pip_dry_run' : [python, '-m', 'pip', '--disable-pip-version-check', *install, '--dry-run']
			}

			if uv:
				methods['uv'] = [uv, 'pip', 'install', '--python', python, '-r', requirements]

			samples = {method: [] for method in methods}

			for index in range(_ROUNDS):
				for method in randomizer.sample(list(methods), len(methods)):
					value = execute(methods[method], directory)
					samples[method].append(value)

			results[repository] = samples
			print(repository, flush=True)

			for method, values in samples.items():
				print(
					f'{method}: median={statistics.median(values):.2f} ms, '
					f'min={min(values):.2f}, max={max(values):.2f}, n={len(values)}',
					flush=True
				)

		execute([python, '-m', 'pip', 'check'], home)

	print('BENCHMARK_RESULT=' + json.dumps(results), flush=True)


if __name__ == '__main__':
	benchmark()
