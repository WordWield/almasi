import sys
from importlib.metadata import version

from ._libraries import _Libraries


# Keep the offline loader version local and delegate all other commands.
# ----------------------------------------------------------------------
def main():
	if sys.argv[1:] == ['--version']:
		print('almasi', version('almasi'))
	else:
		_Libraries.run('cli', sys.argv[1:])


if __name__ == '__main__':
	main()
