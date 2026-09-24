"""Contains the data analysis of control runs (profile and data viewer).

A dataset is the data behind one number of the Results page: the records a
run fetched from a side, or the records it saved to its result table. The
server resolves it to SQL (datasets), and a spawned worker process holding the
fetched sample answers the profile and viewer requests (worker, profile,
frame), managed by the server's session manager (sessions).
"""

import warnings

# The Oracle client, initialized before numpy is imported, changes the x87
# precision, so numpy's probe of `longdouble` warns on import. The profile
# never uses that type.
warnings.filterwarnings('ignore', message='Signature .*numpy.longdouble',
                        category=UserWarning)
