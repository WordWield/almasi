# ==============================================================================
# ALMASI LOADER
# ==============================================================================
# Resolve the library family without importing its architecture on startup.
# ==============================================================================

from ._libraries import _Libraries


# Resolve public library names on first use; Python owns module identity.
# ----------------------------------------------------------------------
def __getattr__(name):
	if _Libraries.is_valid_name(name):
		result = _Libraries.imp(name)
	else:
		raise AttributeError(f'Almasi has no attribute `{name}`')

	return result
