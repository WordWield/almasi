import sys

from ._libraries import _Libraries


_USAGE = 'Usage: almasi <library> [arguments ...]'


# Forward the remaining arguments unchanged to the selected library.
# ----------------------------------------------------------------------
def main():
	if len(sys.argv) > 1:
		name = sys.argv[1]

		if name in ('-h', '--help'):
			print(_USAGE)
		elif _Libraries.is_valid_name(name):
			_Libraries.run(name, sys.argv[2:])
		else:
			raise SystemExit(f'Invalid library name: {name!r}')
	else:
		raise SystemExit(_USAGE)


if __name__ == '__main__':
	main()
