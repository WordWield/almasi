# ==============================================================================
# ALMASI LOADER
# ==============================================================================
# Resolve the library family without importing its architecture on startup.
# ==============================================================================

from ._git       import Git
from ._libraries import Libraries


# Resolve public library names on first use; Python owns module identity.
# ----------------------------------------------------------------------
def __getattr__(name):
	if Libraries.is_valid_name(name):
		result = Libraries.imp(name)
	else:
		raise AttributeError(f'Almasi has no attribute `{name}`')

	return result
